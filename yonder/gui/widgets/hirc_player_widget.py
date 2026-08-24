from typing import Any, TYPE_CHECKING
from dearpygui import dearpygui as dpg

from yonder import Soundbank, HIRCNode, lookup_name, calc_hash
from yonder.audio.hirc_player import HIRCPlayer
from yonder.gui import style
from yonder.gui.config import get_config
from yonder.gui.icons import Icons
from yonder.gui.localization import µ
from .dpg_item import DpgItem
from .equalizer_widget import add_equalizer

if TYPE_CHECKING:
    from yonder.audio.stream_source import StreamSource


class add_hirc_player(DpgItem):
    def __init__(
        self,
        *,
        tag: str = 0,
        parent: str = 0,
    ) -> None:
        super().__init__(tag)
        self._player: HIRCPlayer = None
        self._equalizer: add_equalizer = None
        self._rtpcs: dict[int, float] = {}
        self._states: dict[int, int] = {}
        self._distance: float = 0.0
        self._setup_content(parent)
        self.set_enabled(False)

    def set_enabled(self, enabled: bool) -> None:
        # TODO
        pass

    def load(self, bnk: Soundbank, entrypoint: HIRCNode) -> None:
        self.set_enabled(False)

        if self._player:
            self._player.stop()

        # Removing pyo objects from a running pyo server tends to cause segfaults, so better
        # to recreate the player each time the structure changes. Closing the server takes a
        # few ms, but we can let this be handled by the GC in the background.

        cfg = get_config()
        self._player = HIRCPlayer(
            bnk,
            entrypoint,
            cfg.locate_vgmstream(),
            cfg.bankdirs,
        )
        self._player.set_equalizer(self._equalizer.values)

        dpg.configure_item(self._t("btn_play"), texture_tag=Icons.play)
        self.regenerate()
        self.set_enabled(True)

    def regenerate(self) -> None:
        dpg.delete_item(self._t("voice_settings"), children_only=True)
        dpg.delete_item(self._t("popup_states"), children_only=True)

        grad1 = style.RGBA.create_gradient(
            style.light_blue.but(a=162), style.light_orange.but(a=162), 10
        )
        grad2 = style.RGBA.create_gradient(
            style.pink.but(a=162), style.light_red.but(a=162), 10
        )

        # TODO UI for states and rtpcs
        voices = self._player.collect_voices(True)

        dpg.push_container_stack(self._t("voice_settings"))
        for idx, voice in enumerate(voices):
            with dpg.group(horizontal=True):
                dpg.add_checkbox(
                    default_value=True,
                    callback=self._toggle_voice,
                    user_data=voice.id,
                    tag=self._t(f"voice_toggle_{voice.id}"),
                )
                dpg.add_slider_float(
                    label=voice.id,
                    callback=self._on_set_volume_voice,
                    default_value=1.0,
                    min_value=0.0,
                    max_value=2.0,
                    clamped=True,
                    no_input=True,
                    width=280,
                    user_data=voice.id,
                    tag=self._t(f"voice_volume_{voice.id}"),
                )

                color = grad1[idx % 10] if idx % 2 == 0 else grad2[idx % 10]
                theme = style.themes.make_slider_theme(color)
                dpg.bind_item_theme(self._t(f"voice_volume_{voice.id}"), theme)

        dpg.pop_container_stack()

        # TODO enable/disable attenuation

        all_rtpcs, all_states = self._player.collect_control_states(False)
        active_rtpcs, active_states = self._player.collect_control_states(True)

        if all_rtpcs:
            with dpg.tree_node(label=µ("RTPC"), default_open=True):
                for rtpc in all_rtpcs:
                    self._player.ctx.rtpcs.setdefault(rtpc, 0.0)

                    dpg.add_slider_double(
                        label=rtpc,
                        default_value=0.0,
                        height=15,
                        callback=self._on_set_rtpc,
                        user_data=rtpc,
                    )
                    # TODO adjust theme if not active
        
        if all_states:
            with dpg.tree_node(label=µ("States"), default_open=True):
                for group, states in all_states.items():
                    group_name = lookup_name(group, f"#{group}")
                    state_names = sorted(lookup_name(s, f"#{s}") for s in states)
                    self._player.ctx.states[group, calc_hash(state_names[0])]

                    dpg.add_combo(
                        state_names,
                        default_value=state_names[0],
                        label=group_name,
                        callback=self._on_set_state,
                        user_data=group,
                    )
                    # TODO adjust theme if not active

        dpg.push_container_stack(self._t("popup_states"))

        if not all_rtpcs and not all_states:
            dpg.add_text(µ("(no RTPCs/states)"), color=style.light_grey)

        dpg.pop_container_stack()

    def _on_ctrl_seek_zero(self) -> None:
        if self._player:
            self._player.seek(0)

    def _on_ctrl_stop(self) -> None:
        if not self._player:
            return

        self._player.stop()
        self._player.seek(0)
        dpg.configure_item(self._t("btn_play"), texture_tag=Icons.play)

    def _on_ctrl_play_pause(self) -> None:
        if not self._player:
            return

        if self._player.playing:
            self._player.stop()
            dpg.configure_item(self._t("btn_play"), texture_tag=Icons.play)
        else:
            self._player.play()
            dpg.configure_item(self._t("btn_play"), texture_tag=Icons.pause)

    def _on_ctrl_forward_10s(self) -> None:
        if self._player:
            self._player.seek(self._player.pos + 10.0)

    def _on_ctrl_forward_30s(self) -> None:
        if self._player:
            self._player.seek(self._player.pos + 30.0)

    def _open_ctrl_popup(self, sender: str, app_data: str, tag: Any) -> None:
        pos = dpg.get_item_rect_min(sender)
        size = tuple(dpg.get_item_rect_size(tag))
        dpg.set_item_pos(tag, (pos[0], pos[1] - size[1] - 6))
        dpg.show_item(tag)

        # Fix for dpg needing to render the popup once to be able to measure it
        dpg.render_dearpygui_frame()
        size = tuple(dpg.get_item_rect_size(tag))
        dpg.set_item_pos(tag, (pos[0], pos[1] - size[1] - 6))

    def _on_set_rtpc(self, sender: str, value: float, rtpc: str) -> None:
        h = int(rtpc[1:]) if rtpc.startswith("#") else calc_hash(rtpc)
        self._rtpcs[h] = value

        if self._player:
            # TODO maintain our own play context to persist values across player instances
            self._player.ctx.rtpcs[h] = value
            self._player.apply_context()

    def _on_set_state(self, sender: str, state: str, group: str) -> None:
        g = int(group[1:]) if group.startswith("#") else calc_hash(group)
        s = int(state[1:]) if state.startswith("#") else calc_hash(state)
        self._states[g] = s

        if self._player:
            self._player.ctx.states[g] = s
            self._player.apply_context()

    def _on_eqboost_changed(
        self, sender: str, values: list[float], user_data: Any
    ) -> None:
        if self._player:
            self._player.set_equalizer(values)

    def _on_set_volume(self, sender: str, amp: float, user_data: Any) -> None:
        if not self._player:
            return

        if amp == 0.0:
            self._player.set_muted(True)
        else:
            self._player.set_muted(False)
            self._player.set_master_volume(amp)

    def _on_set_speed(self, sender: str, speed: float, user_data: Any) -> None:
        if self._player:
            self._player.set_speed(speed)

    def _on_set_volume_voice(self, sender: str, amp: float, voice_id: int) -> None:
        if self._player:
            node = self._player.bnk.get(voice_id)
            stream: StreamSource = node.pyo(ctx)
            stream.volume = amp

    def _toggle_voice(self, sender: str, enabled: bool, voice_id: int) -> None:
        if not self._player:
            return

        tag = self._t(f"voice_volume_{voice_id}")
        node = self._player.bnk.get(voice_id)
        stream: StreamSource = node.pyo(ctx)

        if enabled:
            dpg.enable_item(tag)
            amp = dpg.get_value(tag)
            stream.volume = amp
        else:
            dpg.disable_item(tag)
            stream.volume = 0.0

    def _setup_content(
        self,
        parent: str,
    ) -> None:
        with dpg.child_window(
            autosize_x=True,
            autosize_y=True,
            no_scrollbar=True,
            no_scroll_with_mouse=True,
            border=False,
            tag=self._tag,
            parent=parent,
        ):
            with dpg.group(horizontal=True):
                dpg.add_image_button(
                    Icons.seek_zero,
                    callback=self._on_ctrl_seek_zero,
                    tint_color=style.light_blue,
                )
                dpg.add_image_button(
                    Icons.stop,
                    callback=self._on_ctrl_stop,
                    tint_color=style.white,
                )
                dpg.add_image_button(
                    Icons.play,
                    callback=self._on_ctrl_play_pause,
                    tint_color=style.white,
                    tag=self._t("btn_play"),
                )
                dpg.add_image_button(
                    Icons.forward_10s,
                    callback=self._on_ctrl_forward_10s,
                    tint_color=style.purple.mix(style.white),
                )
                dpg.add_image_button(
                    Icons.forward_30s,
                    callback=self._on_ctrl_forward_30s,
                    tint_color=style.pink.mix(style.white),
                )

                dpg.add_text("|")

                dpg.add_image_button(
                    Icons.states,
                    callback=self._open_ctrl_popup,
                    tint_color=style.light_grey,
                    user_data=self._t("popup_states"),
                )
                # TODO
                #dpg.add_image_button(
                #    Icons.attenuation,
                #    callback=self._open_ctrl_popup,
                #    tint_color=style.light_grey,
                #    user_data=self._t("popup_attenuation"),
                #)
                dpg.add_image_button(
                    Icons.equalizer,
                    callback=self._open_ctrl_popup,
                    tint_color=style.light_grey,
                    user_data=self._t("popup_equalizer"),
                )
                dpg.add_image_button(
                    Icons.sliders,
                    callback=self._open_ctrl_popup,
                    tint_color=style.light_grey,
                    user_data=self._t("popup_voices"),
                )

        dpg.add_window(
            popup=True,
            min_size=(100, 20),
            show=False,
            tag=self._t("popup_states"),
        )

        with dpg.window(
            popup=True,
            min_size=(200, 200),
            show=False,
            tag=self._t("popup_attenuation"),
        ):
            # TODO attenuation plot
            pass

        with dpg.window(
            popup=True,
            show=False,
            tag=self._t("popup_equalizer"),
        ):
            self._equalizer = add_equalizer(self._on_eqboost_changed)

        with dpg.window(
            popup=True,
            min_size=(100, 20),
            show=False,
            tag=self._t("popup_voices"),
        ):
            dpg.add_slider_float(
                label=µ("Volume"),
                callback=self._on_set_volume,
                default_value=1.0,
                min_value=0.1,
                max_value=2.0,
                clamped=True,
                width=280,
            )
            dpg.add_slider_float(
                label=µ("Speed"),
                callback=self._on_set_speed,
                default_value=1.0,
                min_value=0.0,
                max_value=2.0,
                clamped=True,
                width=280,
            )
            dpg.add_separator(label=µ("Voices"))
            dpg.add_group(tag=self._t("voice_settings"))

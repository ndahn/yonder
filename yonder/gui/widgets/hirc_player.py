from typing import Any
from dearpygui import dearpygui as dpg

from yonder import Soundbank, HIRCNode, lookup_name, calc_hash
from yonder.audio import Player
from yonder.gui import style
from yonder.gui.config import get_config
from yonder.gui.icons import Icons
from yonder.gui.localization import µ
from .dpg_item import DpgItem
from .equalizer_widget import add_equalizer


class add_hirc_player(DpgItem):
    def __init__(
        self,
        *,
        tag: str = 0,
        parent: str = 0,
    ) -> None:
        super().__init__(tag)
        self._player: Player = None
        self._rtpcs: dict[int, float] = {}
        self._states: dict[int, int] = {}
        self._distance: float = 0.0
        self._setup_content(parent)
        self.set_enabled(False)

    def set_enabled(self, enabled: bool) -> None:
        # TODO
        pass

    def load(
        self, bnk: Soundbank, entrypoint: HIRCNode, full_tree: bool = False
    ) -> None:
        self.set_enabled(False)

        if self._player:
            self._player.stop()

        # Removing pyo objects from a running pyo server tends to cause segfaults, so better
        # to recreate the player each time the structure changes. Closing the server takes a
        # few ms, but we can let this be handled by the GC in the background.

        cfg = get_config()
        self._player = Player(
            bnk,
            entrypoint,
            cfg.locate_vgmstream(),
            cfg.bankdirs,
            full_tree,
        )
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

        dpg.push_container_stack(self._t("voice_settings"))
        for idx, (vid, voice) in enumerate(self._player.voices.items()):
            with dpg.group(horizontal=True):
                dpg.add_checkbox(
                    default_value=True,
                    callback=self._toggle_voice,
                    user_data=vid,
                    tag=self._t(f"voice_toggle_{vid}"),
                )
                dpg.add_slider_float(
                    label=voice.src.path.stem,
                    callback=self._on_set_volume_voice,
                    default_value=1.0,
                    min_value=0.0,
                    max_value=2.0,
                    clamped=True,
                    no_input=True,
                    width=280,
                    user_data=vid,
                    tag=self._t(f"voice_volume_{vid}"),
                )

                color = grad1[idx % 10] if idx % 2 == 0 else grad2[idx % 10]
                theme = style.themes.make_slider_theme(color)
                dpg.bind_item_theme(self._t(f"voice_volume_{vid}"), theme)

        dpg.pop_container_stack()

        rtpcs, states = self._player.collect_control_variables()
        self._rtpcs = {r: 0.0 for r in rtpcs}
        self._states = {g: next(s) for g, s in states.items()}

        rtpcs = sorted(lookup_name(r, f"#{r}") for r in rtpcs)
        states = {
            lookup_name(g, f"#{g}"): sorted(lookup_name(s, f"#{s}"))
            for g, vals in states.items()
            for s in vals
        }

        dpg.push_container_stack(self._t("popup_states"))
        
        if rtpcs:
            with dpg.tree_node(label=µ("RTPC"), default_open=True):
                for r in rtpcs:
                    dpg.add_slider_double(
                        label=r,
                        default_value=0.0,
                        height=15,
                        callback=self._on_set_rtpc,
                        user_data=r,
                    )

        if states:
            with dpg.tree_node(label=µ("States"), default_open=True):
                for group, values in states.items():
                    dpg.add_combo(
                        values,
                        default_value=values[0],
                        label=group,
                        callback=self._on_set_state,
                        user_data=group,
                    )

        if not rtpcs and not states:
            dpg.add_text(µ("(no RTPCs/states)"), color=style.light_grey)

        dpg.pop_container_stack()

    def _on_ctrl_seek_zero(self) -> None:
        self._player.seek(0)

    def _on_ctrl_stop(self) -> None:
        self._player.stop()
        self._player.seek(0)
        dpg.configure_item(self._t("btn_play"), texture_tag=Icons.play)

    def _on_ctrl_play_pause(self) -> None:
        if self._player.playing:
            self._player.stop()
            dpg.configure_item(self._t("btn_play"), texture_tag=Icons.play)
        else:
            self._player.play()
            dpg.configure_item(self._t("btn_play"), texture_tag=Icons.pause)

    def _on_ctrl_forward_10s(self) -> None:
        self._player.seek(self._player.pos + 10.0)

    def _on_ctrl_forward_30s(self) -> None:
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
        self._player.set_state_params(self._rtpcs, self._states, self._distance)

    def _on_set_state(self, sender: str, state: str, group: str) -> None:
        g = int(group[1:]) if group.startswith("#") else calc_hash(group)
        s = int(state[1:]) if state.startswith("#") else calc_hash(state)
        self._states[g] = s
        self._player.set_state_params(self._rtpcs, self._states, self._distance)

    def _on_eqboost_changed(
        self, sender: str, values: list[float], user_data: Any
    ) -> None:
        self._player.set_equalizer(values)

    def _on_set_volume(self, sender: str, amp: float, user_data: Any) -> None:
        if amp == 0.0:
            self._player.set_muted(True)
        else:
            self._player.set_muted(False)
            self._player.set_volume(amp)

    def _on_set_speed(self, sender: str, speed: float, user_data: Any) -> None:
        self._player.set_speed(speed)

    def _on_set_volume_voice(self, sender: str, amp: float, voice_id: int) -> None:
        self._player.voices[voice_id].volume = amp

    def _toggle_voice(self, sender: str, enabled: bool, voice_id: int) -> None:
        tag = self._t(f"voice_volume_{voice_id}")
        if enabled:
            dpg.enable_item(tag)
            amp = dpg.get_value(tag)
            self._player.voices[voice_id].volume = amp
        else:
            dpg.disable_item(tag)
            self._player.voices[voice_id].volume = 0.0

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
            show=False,
            tag=self._t("popup_equalizer"),
        ):
            add_equalizer(self._on_eqboost_changed)

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

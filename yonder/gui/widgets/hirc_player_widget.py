from typing import Any, TYPE_CHECKING
from dearpygui import dearpygui as dpg

from yonder import Soundbank, HIRCNode, lookup_name, calc_hash
from yonder.audio.hirc_player import HIRCPlayer
from yonder.audio.play_context import PlayContext
from yonder.gui import style
from yonder.gui.config import get_config
from yonder.gui.icons import Icons
from yonder.gui.localization import µ
from .dpg_item import DpgItem
from .equalizer_widget import add_equalizer
from .attenuation_plot import add_attenuation_plot

if TYPE_CHECKING:
    from yonder.audio.multi_track_stream import MultiTrackStream


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
        self._attenuation_plot: add_attenuation_plot = None
        self._rtpcs: dict[int, float] = {}
        self._states: dict[int, int] = {}
        self._distance: float = 0.0
        self._angle: float = 0.0
        self._setup_content(parent)
        self.set_enabled(False)

    def set_enabled(self, enabled: bool) -> None:
        # TODO
        pass

    def load(self, bnk: Soundbank, entrypoint: HIRCNode) -> None:
        self.set_enabled(False)

        if self._player:
            self._player.close()

        # Removing pyo objects from a running pyo server tends to cause segfaults, so better
        # to recreate the player each time the structure changes. Closing the server takes a
        # few ms, but we can let this be handled by the GC in the background.

        # TODO what to do when this fails?
        cfg = get_config()
        vgmstream = cfg.locate_vgmstream()

        ctx = PlayContext(
            bnk,
            vgmstream,
            cfg.bankdirs,
            rtpcs=dict(self._rtpcs),
            states=dict(self._states),
            distance=self._distance,
            angle=self._angle,
        )

        self._player = HIRCPlayer(bnk, entrypoint, ctx)
        self._player.set_equalizer(self._equalizer.values)

        dpg.configure_item(self._t("btn_play"), texture_tag=Icons.play)
        self.regenerate()
        self.set_enabled(True)

    @property
    def player(self) -> HIRCPlayer:
        return self._player

    def play(self) -> None:
        if self._player:
            self._player.play()

    def stop(self) -> None:
        if self._player:
            self._player.stop()

    def update_context(self) -> None:
        if self._player:
            self._player.apply_context(None)

    def regenerate(self) -> None:
        dpg.delete_item(self._t("voice_settings"), children_only=True)
        dpg.delete_item(self._t("popup_states"), children_only=True)
        self._attenuation_plot.clear_attenuations()

        grad1 = style.RGBA.create_gradient(
            style.light_blue.but(a=162), style.light_orange.but(a=162), 10
        )
        grad2 = style.RGBA.create_gradient(
            style.pink.but(a=162), style.light_red.but(a=162), 10
        )

        # Individual voice settings
        dpg.push_container_stack(self._t("voice_settings"))
        active_voices = self._player.collect_voices(True)

        for idx, voice in enumerate(active_voices):
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

        # Attenuation
        dpg.push_container_stack(self._t("popup_attenuation"))

        # there may be multiple attenuations at the same time
        context_map = self._player.collect_effective_contexts(True)
        for voice in active_voices:
            ctx = context_map[voice.id]
            att = ctx.attenuation
            if att:
                self._attenuation_plot.add_attenuation(att)

        dpg.pop_container_stack()

        # RTPC & States
        dpg.push_container_stack(self._t("popup_states"))

        all_rtpcs, all_states = self._player.collect_control_states(False)
        active_rtpcs, active_states = self._player.collect_control_states(True)

        if all_rtpcs:
            with dpg.tree_node(label=µ("RTPC"), default_open=True):

                def toggle_rtpcs_active_only(
                    sender: str, enabled: bool, cb_user_data: Any
                ) -> None:
                    active_rtpcs, _ = self._player.collect_control_states(True)
                    for child in dpg.get_item_children(self._t("rtpcs_group"), slot=1):
                        ud = dpg.get_item_user_data(child)
                        if ud is not None:
                            show = not enabled or ud in active_rtpcs
                            dpg.configure_item(child, show=show)
                            # TODO adjust theme if not active

                dpg.add_checkbox(
                    label=µ("For active nodes only"),
                    default_value=True,
                    callback=toggle_rtpcs_active_only,
                    tag=self._t("states_active_only"),
                )

                with dpg.group(tag=self._t("rtpcs_group")):
                    for rtpc in all_rtpcs:
                        self._player.context.rtpcs.setdefault(rtpc, 0.0)

                        dpg.add_slider_double(
                            label=rtpc,
                            default_value=0.0,
                            height=15,
                            callback=self._on_set_rtpc,
                            user_data=rtpc,
                            show=rtpc in active_rtpcs,
                        )

        if all_states:
            with dpg.tree_node(label=µ("States"), default_open=True):

                def toggle_states_active_only(
                    sender: str, enabled: bool, cb_user_data: Any
                ) -> None:
                    _, active_states = self._player.collect_control_states(True)
                    for child in dpg.get_item_children(self._t("states_group"), slot=1):
                        ud = dpg.get_item_user_data(child)
                        if ud is not None:
                            show = not enabled or ud in active_states
                            dpg.configure_item(child, show=show)
                            # TODO adjust theme if not active

                dpg.add_checkbox(
                    label=µ("For active nodes only"),
                    default_value=True,
                    callback=toggle_states_active_only,
                    tag=self._t("states_active_only"),
                )

                with dpg.group(tag=self._t("states_group")):
                    for group, states in all_states.items():
                        group_name = lookup_name(group, f"#{group}")
                        state_names = sorted(lookup_name(s, f"#{s}") for s in states)
                        self._player.context.states[group, calc_hash(state_names[0])]

                        dpg.add_combo(
                            state_names,
                            default_value=state_names[0],
                            label=group_name,
                            callback=self._on_set_state,
                            user_data=group,
                            show=group in active_states,
                        )

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

    def _on_set_distance_angle(
        self, sender: str, value: tuple, cb_user_data: Any
    ) -> None:
        self._distance, self._angle = value

        if self._player:
            self._player.context.distance = self._distance
            self._player.context.angle = self._angle
            self._player.apply_context()

    def _on_set_rtpc(self, sender: str, value: float, rtpc: str) -> None:
        h = int(rtpc[1:]) if rtpc.startswith("#") else calc_hash(rtpc)
        self._rtpcs[h] = value

        if self._player:
            self._player.context.rtpcs[h] = value
            self._player.apply_context()

    def _on_set_state(self, sender: str, state: str, group: str) -> None:
        g = int(group[1:]) if group.startswith("#") else calc_hash(group)
        s = int(state[1:]) if state.startswith("#") else calc_hash(state)
        self._states[g] = s

        if self._player:
            self._player.context.states[g] = s
            self._player.apply_context()
            # This may cause the active nodes to change
            self.regenerate()

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

    def _on_set_volume_voice(self, sender: str, amp: float, voice_id: int) -> None:
        if self._player:
            self._player.set_volume(voice_id, amp)

    def _toggle_voice(self, sender: str, muted: bool, voice_id: int) -> None:
        if not self._player:
            return

        self._player.set_muted(voice_id, muted)
        tag = self._t(f"voice_volume_{voice_id}")

        if muted:
            dpg.enable_item(tag)
        else:
            dpg.disable_item(tag)

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
                    Icons.equalizer,
                    callback=self._open_ctrl_popup,
                    tint_color=style.light_grey,
                    user_data=self._t("popup_equalizer"),
                )
                # with dpg.tooltip(dpg.last_item(), delay=.3):
                #    dpg.add_text(µ("Equalizer"))

                dpg.add_image_button(
                    Icons.states,
                    callback=self._open_ctrl_popup,
                    tint_color=style.light_grey,
                    user_data=self._t("popup_states"),
                )
                # with dpg.tooltip(dpg.last_item(), delay=.3):
                #    dpg.add_text(µ("RTPC & States"))

                dpg.add_image_button(
                    Icons.spatial3d,
                    callback=self._open_ctrl_popup,
                    tint_color=style.light_grey,
                    user_data=self._t("popup_attenuation"),
                )
                # with dpg.tooltip(dpg.last_item(), delay=.3):
                #    dpg.add_text(µ("3D Positioning"))

                dpg.add_image_button(
                    Icons.sliders,
                    callback=self._open_ctrl_popup,
                    tint_color=style.light_grey,
                    user_data=self._t("popup_voices"),
                )
                # with dpg.tooltip(dpg.last_item(), delay=.3):
                #    dpg.add_text(µ("Voices"))

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
            self._attenuation_plot = add_attenuation_plot(
                None, self._on_set_distance_angle
            )

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
            dpg.add_separator(label=µ("Voices"))
            dpg.add_group(tag=self._t("voice_settings"))

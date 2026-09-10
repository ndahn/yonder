from typing import Any
import time
from dearpygui import dearpygui as dpg

from yonder import Soundbank, HIRCNode
from yonder.types import Sound, MusicTrack
from yonder.audio.hirc_player import HIRCPlayer
from yonder.audio.play_context import PlayContext
from yonder.util import logger
from yonder.gui import style
from yonder.gui.config import get_config
from yonder.gui.icons import Icons
from yonder.gui.localization import µ
from .dpg_item import DpgItem
from .equalizer_widget import add_equalizer
from .attenuation_plot import add_attenuation_plot


class add_hirc_player(DpgItem):
    def __init__(
        self,
        bnk: Soundbank = None,
        entrypoint: HIRCNode = None,
        *,
        tag: str = 0,
        parent: str = 0,
    ) -> None:
        super().__init__(tag)

        self._bnk: Soundbank = bnk
        self._entrypoint: HIRCNode = entrypoint
        self._dirty: bool = True
        self._player: HIRCPlayer = None
        self._vgmstream_requested: bool = False
        self._equalizer: add_equalizer = None
        self._attenuation_plot: add_attenuation_plot = None
        self._voices: list[Sound | MusicTrack] = []
        self._rtpcs: dict[int, float] = {}
        self._states: dict[int, int] = {}
        self._distance: float = 0.0
        self._angle: float = 0.0

        self._setup_content(parent)
        self.set_enabled(False)

    def set_enabled(self, enabled: bool) -> None:
        for child in dpg.get_item_children(self._t("buttons"), slot=1):
            if "button" in dpg.get_item_type(child).lower():
                dpg.configure_item(child, enabled=enabled)

    def set_entrypoint(self, entrypoint: HIRCNode, bnk: Soundbank = None) -> None:
        if self._player:
            self._player.stop()

        self._set_play_button_state(False)
        self._voices.clear()
        self._states.clear()
        self._rtpcs.clear()

        if bnk:
            self._bnk = bnk

        self._entrypoint = entrypoint
        self._dirty = True

    def _init_player(self) -> None:
        if self._player and not self._dirty:
            return

        self.set_enabled(False)

        # Removing pyo objects from a running pyo server tends to cause segfaults, so better
        # to recreate the player each time the structure changes. Closing the server takes a
        # few ms, but we can let this be handled by the GC in the background.
        if self._player:
            self._player.close()

        if not self._bnk:
            logger.error("Soundbank not set")
            return

        if not self._entrypoint:
            logger.error("Entrypoint not set")
            return

        cfg = get_config()

        if self._vgmstream_requested:
            # We already asked before, if it's still not available we fail
            vgmstream = cfg.vgmstream_exe
        else:
            self._vgmstream_requested = True
            vgmstream = cfg.locate_vgmstream()

        if not vgmstream:
            # Don't log this, it's just noise
            print("[ERROR] vgmstream not found, HIRC player disabled")
            return

        ctx = PlayContext(
            self._bnk,
            vgmstream,
            cfg.bankdirs,
            rtpcs=dict(self._rtpcs),
            states=dict(self._states),
            distance=self._distance,
            angle=self._angle,
        )

        self._player = HIRCPlayer(
            self._bnk, self._entrypoint, ctx, lambda: self._set_play_button_state(False)
        )
        self._player.set_equalizer(self._equalizer.values)

        # TODO collect rtpcs and states

        self._set_play_button_state(False)
        self.regenerate()
        self.set_enabled(True)
        self._dirty = False

    @property
    def player(self) -> HIRCPlayer:
        return self._player

    @property
    def voices(self) -> list[Sound | MusicTrack]:
        return self._voices

    @property
    def states(self) -> dict[int, set[int]]:
        return self._states

    @property
    def rtpcs(self) -> list[int]:
        return self._rtpcs

    def set_game_syncs(
        self, states: dict[int, int] = None, rtpcs: dict[int, float] = None
    ) -> None:
        if states:
            self._states.update(states)

        if rtpcs:
            self._rtpcs.update(rtpcs)

        if states or rtpcs:
            self.update_context()

        if states:
            # States can influence what is being played, rtpcs can't
            # TODO limit update rate
            self.regenerate()

    def play(self) -> None:
        self._init_player()
        if self._player:
            self._player.play()

    def stop(self) -> None:
        self._init_player()
        if self._player:
            self._player.stop()

    def update_context(self) -> None:
        if self._player:
            self._player.apply_context(None)

    def regenerate(self) -> None:
        dpg.delete_item(self._t("voice_settings"), children_only=True)
        dpg.delete_item(self._t("popup_states"), children_only=True)
        self._attenuation_plot.clear()

        grad1 = style.RGBA.create_gradient(
            style.light_blue.but(a=162), style.light_orange.but(a=162), 10
        )
        grad2 = style.RGBA.create_gradient(
            style.pink.but(a=162), style.light_red.but(a=162), 10
        )

        self._voices = self._player.collect_voices()

        # Individual voice settings
        dpg.push_container_stack(self._t("voice_settings"))

        for idx, voice in enumerate(self._voices):
            with dpg.group(horizontal=True):
                dpg.add_checkbox(
                    default_value=True,
                    callback=self._toggle_voice,
                    user_data=voice.id,
                    tag=self._t(f"voice_toggle_{voice.id}"),
                )
                dpg.add_slider_float(
                    label=voice.get_name(),
                    callback=self._on_set_volume_voice,
                    default_value=1.0,
                    min_value=-10,
                    max_value=10,
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

        # there may be multiple attenuations affecting different voices at the same time
        for voice in self._voices:
            if voice.is_pyo_initialized():
                att = voice.pyo_state().ctx.attenuation
                if att:
                    self._attenuation_plot.add_attenuation(att)

        dpg.pop_container_stack()

    def _set_play_button_state(self, playing: bool) -> None:
        dpg.configure_item(
            self._t("btn_play"), texture_tag=Icons.pause if playing else Icons.play
        )

    def _on_ctrl_seek_zero(self) -> None:
        if self._player:
            self._player.seek(0, None)

    def _on_ctrl_stop(self) -> None:
        if not self._player:
            return

        self._player.stop()
        self._player.seek(0, None)
        self._set_play_button_state(False)

    def _on_ctrl_play_pause(self) -> None:
        self._init_player()
        if not self._player:
            return

        if self._player.playing:
            self._player.stop()
            self._set_play_button_state(False)
        else:
            self._player.play()
            self._set_play_button_state(True)
            time.sleep(0.1)
            self.regenerate()

    def _on_ctrl_forward_10s(self) -> None:
        if self._player:
            self._player.seek(self._player.pos + 10.0, None)

    def _on_ctrl_forward_30s(self) -> None:
        if self._player:
            self._player.seek(self._player.pos + 30.0, None)

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

    def _on_eqboost_changed(
        self, sender: str, values: list[float], user_data: Any
    ) -> None:
        if self._player:
            self._player.set_equalizer(values)

    def _on_set_volume(self, sender: str, vol: float, user_data: Any) -> None:
        if not self._player:
            return

        self._player.set_muted(False, None)
        self._player.set_master_volume(vol)

    def _on_set_volume_voice(self, sender: str, vol: float, voice_id: int) -> None:
        if self._player:
            self._player.set_volume(vol, voice_id)

    def _toggle_voice(self, sender: str, muted: bool, voice_id: int) -> None:
        if not self._player:
            return

        self._player.set_muted(muted, voice_id)
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
            tag=self.tag,
            parent=parent,
        ):
            with dpg.group(horizontal=True, tag=self._t("buttons")):
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
            # TODO non-editable link to attenuation
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
                min_value=-10,
                max_value=10,
                clamped=True,
                width=280,
            )
            dpg.add_separator(label=µ("Voices"))
            dpg.add_group(tag=self._t("voice_settings"))

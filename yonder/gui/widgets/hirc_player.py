from typing import Any
from dearpygui import dearpygui as dpg

from yonder import Soundbank, HIRCNode
from yonder.util import logger
from yonder.audio import Player, Voice
from yonder.gui import style
from yonder.gui.config import get_config
from yonder.gui.icons import Icons
from yonder.gui.localization import µ
from .dpg_item import DpgItem


class add_hirc_player(DpgItem):
    def __init__(
        self,
        *,
        tag: str = 0,
        parent: str = 0,
    ) -> None:
        super().__init__(tag)
        self._player: Player = None
        self._setup_content(parent)
        self.set_enabled(False)

    def set_enabled(self, enabled: bool) -> None:
        # TODO
        pass

    def load(
        self, bnk: Soundbank, entrypoint: HIRCNode, full_tree: bool = False
    ) -> None:
        self.set_enabled(False)

        # Removing pyo objects from a running pyo server tends to cause segfaults, so better
        # to recreate the player each time the structure changes. Closing the server takes a
        # few ms, but we can let this be handled by the GC in the background.

        self._player = Player(bnk, entrypoint, get_config().locate_vgmstream(), full_tree)
        self.regenerate()

        self.set_enabled(True)

    def regenerate(self) -> None:
        dpg.delete_item(self._t("voice_settings"), children_only=True)
        dpg.push_container_stack(self._t("voice_settings"))

        grad1 = style.RGBA.create_gradient(
            style.light_blue.but(a=162), style.light_orange.but(a=162), 10
        )
        grad2 = style.RGBA.create_gradient(
            style.pink.but(a=162), style.light_red.but(a=162), 10
        )

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

    def _on_ctrl_reset(self) -> None:
        self.regenerate()

    def _open_voice_ctrl(self, sender: str, app_data: str, user_data: Any) -> None:
        tag = self._t("popup_voice_ctrl")
        pos = dpg.get_item_rect_min(sender)
        size = dpg.get_item_rect_size(tag)
        dpg.set_item_pos(tag, (pos[0], pos[1] - size[1] - 6))
        dpg.show_item(tag)

    def _on_set_volume(self, sender: str, amp: float, user_data: Any) -> None:
        if amp == 0.0:
            self._player.set_muted(True)
        else:
            self._player.set_muted(False)
            self._player.set_volume(amp)

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
                    Icons.sound_reset,
                    callback=self._on_ctrl_reset,
                    tint_color=style.light_grey,
                )
                dpg.add_image_button(
                    Icons.sliders,
                    callback=self._open_voice_ctrl,
                    tint_color=style.light_grey,
                    tag=self._t("btn_voice_ctrl"),
                )

        with dpg.window(
            popup=True,
            min_size=(100, 20),
            show=False,
            tag=self._t("popup_voice_ctrl"),
        ):
            dpg.add_slider_float(
                label=µ("Volume"),
                callback=self._on_set_volume,
                default_value=1.0,
                min_value=0.0,
                max_value=2.0,
                clamped=True,
                no_input=True,
                width=280,
            )
            dpg.add_separator(label=µ("Voices"))
            dpg.add_group(tag=self._t("voice_settings"))

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
        width: int = -1,
        height: int = 100,
        tag: str = 0,
        parent: str = 0,
    ) -> None:
        super().__init__(tag)
        self._player = Player(None)
        self._setup_content(width, height, parent)

    def load(
        self, bnk: Soundbank, entrypoint: HIRCNode, full_tree: bool = False
    ) -> None:
        self._player.vgmstream_exe = get_config().locate_vgmstream()
        self._player.from_hierarchy(bnk, entrypoint, full_tree)
        self.regenerate()

    def regenerate(self) -> None:
        dpg.delete_item(self._t("players"), children_only=True)
        dpg.push_container_stack(self._t("players"))

        for voice in self._player.voices:
            with dpg.group(horizontal=True):
                dpg.add_checkbox(
                    default_value=True,
                    callback=self._toggle_voice,
                    user_data=voice,
                )
                dpg.add_button(
                    arrow=True,
                    direction=dpg.mvDir_Down,
                    callback=self._open_voice_ctrl,
                    user_data=voice,
                )
                with dpg.tree_node(
                    label=voice.src.path.name,
                    span_full_width=True,
                    default_open=False,
                ):
                    # TODO visualization
                    pass

        dpg.pop_container_stack()

    def _on_ctrl_seek_zero(self) -> None:
        self._player.seek(0)

    def _on_ctrl_rewind(self) -> None:
        self._player.seek(self._player.pos - 1.0)

    def _on_ctrl_play_pause(self) -> None:
        if self._player.playing:
            self._player.stop()
            dpg.configure_item(self._t("btn_play"), texture_tag=Icons.player_play)
        else:
            self._player.play()
            dpg.configure_item(self._t("btn_play"), texture_tag=Icons.player_pause)

    def _on_ctrl_forward(self) -> None:
        self._player.seek(self._player.pos + 1.0)

    def _on_ctrl_seek_end(self) -> None:
        self._player.seek(-1)

    def _on_ctrl_reset(self) -> None:
        self._player.stop()
        self._player.from_hierarchy(self._entrypoint)
        self.regenerate()

    def _toggle_voice(self, sender: str, app_data: str, voice: Voice) -> None:
        # TODO
        pass

    def _open_voice_ctrl(self, sender: str, app_data: str, voice: Voice) -> None:
        # TODO
        # voice.update()
        pass

    def _setup_content(
        self,
        width: int,
        height: int,
        parent: str,
    ) -> None:
        with dpg.child_window(
            autosize_x=True,
            auto_resize_y=True,
            width=width,
            height=height,
            tag=self._tag,
            parent=parent,
        ):
            with dpg.group(horizontal=True):
                dpg.add_image_button(
                    Icons.player_seek_zero,
                    callback=self._on_ctrl_seek_zero,
                    tint_color=style.pink,
                )
                dpg.add_image_button(
                    Icons.player_rewind,
                    callback=self._on_ctrl_rewind,
                    tint_color=style.light_blue,
                )
                dpg.add_image_button(
                    Icons.player_play,
                    callback=self._on_ctrl_play_pause,
                    tint_color=style.white,
                    tag=self._t("btn_play"),
                )
                dpg.add_image_button(
                    Icons.player_forward,
                    callback=self._on_ctrl_forward,
                    tint_color=style.light_blue,
                )
                dpg.add_image_button(
                    Icons.player_seek_end,
                    callback=self._on_ctrl_seek_end,
                    tint_color=style.pink,
                )

                dpg.add_text("|")

                dpg.add_image_button(
                    Icons.player_reset,
                    callback=self._on_ctrl_reset,
                    tint_color=style.pink,
                )

            dpg.add_group(tag=self._t("players"))

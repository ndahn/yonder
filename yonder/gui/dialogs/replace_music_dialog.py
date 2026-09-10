from typing import Any, Callable
from pathlib import Path
import webbrowser
import shutil
from dearpygui import dearpygui as dpg

from yonder import Soundbank, HIRCNode
from yonder.types import MusicSwitchContainer, MusicTrack
from yonder.enums import SourceType
from yonder.util import get_temp_dir, logger
from yonder.wem import wem2wav, wav2wem, get_wem_id
from yonder.audio.old.wav_player import WavPlayer
from yonder.gui import style
from yonder.gui.icons import Icons
from yonder.gui.localization import µ
from yonder.gui.config import get_config
from yonder.gui.widgets import (
    DpgItem,
    add_generic_widget,
    loading_indicator,
    add_select_node,
    add_paragraphs,
    yay,
)


class replace_music_dialog(DpgItem):
    def __init__(
        self,
        bnk: Soundbank,
        callback: Callable[[dict[tuple[int, int], Path]], None] = None,
        *,
        title: str = "Replace Music",
        tag: str = None,
    ) -> None:
        super().__init__(tag)

        self._bnk: Soundbank = bnk
        self._callback = callback
        self._msc_select: add_select_node = None
        self._replacements: dict[tuple[int, int], Path] = {}
        self._player: WavPlayer = None

        self._build(title)

    def _on_msc_changed(
        self, sender: str, msc: MusicSwitchContainer, user_data: Any
    ) -> None:
        self._replacements.clear()
        self.regenerate()

    def _on_music_path_changed(
        self, sender: str, path: Path, info: tuple[int, int]
    ) -> None:
        track, source_idx = info
        self._replacements[(track.id, source_idx)] = path
        dpg.configure_item(
            self._t(f"reset_{track.id}_{source_idx}"), tint_color=style.yellow
        )

        self._close_player()

    def _on_restore_track(
        self, sender: str, app_data: Any, info: tuple[int, int]
    ) -> None:
        self._replacements.pop(info, None)
        dpg.configure_item(sender, tint_color=style.white)

        self._close_player()

    def _close_player(self) -> None:
        if self._player:
            self._player.stop()
            self._player = None
            # TODO restore play icon

    def _on_play_pause_track(
        self, sender: str, app_data: Any, info: tuple[int, int]
    ) -> None:
        track, sidx = info
        node: MusicTrack = self._bnk[track]
        source_id = node.source_ids[sidx]

        player = self._player
        if player:
            if player.path.endswith(f"{source_id}.wav"):
                if player.playing:
                    player.pause()
                    dpg.configure_item(sender, texture_tag=Icons.play)
                else:
                    player.play()
                    dpg.configure_item(sender, texture_tag=Icons.pause)
                return
            else:
                self._close_player()

        wav = get_temp_dir() / f"{source_id}.wem"

        if not wav.is_file():
            cfg = get_config()
            wem = self._bnk.get_wem_path(source_id, search_paths=cfg.bankdirs)

            if wem:
                vgmstream_exe = cfg.locate_vgmstream()
                wav = wem2wav(vgmstream_exe, wem)[0]

        self._player = WavPlayer(str(wav))
        self._player.play()

    def regenerate(self) -> None:
        dpg.delete_item(self._t("music_table"), slot=1, children_only=True)

        msc: MusicSwitchContainer = self._msc_select.selected_node
        if not isinstance(msc, MusicSwitchContainer):
            return

        def make_rows(node: MusicTrack, path: str, indent: int) -> None:
            if dpg.does_item_exist(self._t(f"row_{path}")):
                return

            if not node.sources:
                return

            with dpg.table_row(
                filter_key=path,
                parent=self._t("music_table"),
                tag=self._t(f"row_{path}"),
            ):
                dpg.add_text(path, indent=indent * 12)

                with dpg.group():
                    for idx, source in enumerate(node.source_ids):
                        add_generic_widget(
                            Path,
                            None,
                            self._on_music_path_changed,
                            default=self._bnk.get_wem_path(source),
                            filetypes={},
                            user_data=(node, idx),
                        )

                with dpg.group():
                    for idx, source in enumerate(node.source_ids):
                        with dpg.group(horizontal=True):
                            tint = (
                                style.yellow
                                if (node.id, idx) in self._replacements
                                else style.white
                            )
                            dpg.add_image_button(
                                Icons.restore_file,
                                width=18,
                                height=18,
                                tint_color=tint,
                                callback=self._on_restore_track,
                                user_data=(node, idx),
                            )
                            dpg.add_image_button(
                                Icons.play,
                                width=18,
                                height=18,
                                callback=self._on_play_pause_track,
                                user_data=(node, idx),
                            )

        def delve(root: HIRCNode, path: str, indent: int) -> None:
            todo = [root]

            while todo:
                node = todo.pop()

                if isinstance(node, MusicTrack):
                    make_rows(node, path, indent)
                elif isinstance(node, MusicSwitchContainer):
                    delve_msc(node, path + "/", indent + 1)
                else:
                    for _, ref in node.get_references():
                        child = self._bnk.get(ref)
                        if child:
                            todo.append(child)

        def delve_msc(
            node: MusicSwitchContainer, path_prefix: str, indent: int
        ) -> None:
            tree = node.get_flat_tree()
            keys = sorted(tree)

            for key in keys:
                node = self._bnk.get(tree[key])
                if not node:
                    continue

                condensed = "/".join(p for p in key if p != "*")
                if not condensed:
                    condensed = "*"

                # need to dive down until we find the leaves
                path = path_prefix + condensed
                delve(node, path, indent)

        delve_msc(msc, "", 0)

    def show_message(self, msg: str = None, color: style.RGBA = style.red) -> None:
        if not msg:
            dpg.hide_item(self._t("notification"))
            return

        dpg.configure_item(
            self._t("notification"),
            default_value=msg,
            color=color,
            show=True,
        )

    def _on_okay(self) -> None:
        if not self._replacements:
            self.show_message(µ("No replacements"))
            return

        self._close_player()
        self.show_message()
        delete_originals = dpg.get_value(self._t("delete_originals"))
        successes = 0

        with loading_indicator(µ("Working...")):
            cfg = get_config()
            wwise_exe: Path = None

            for (nid, sidx), path in self._replacements.items():
                node: MusicTrack = self._bnk.get(nid)
                if not node:
                    logger.warning(f"Node {nid} not found")
                    continue

                source_id = node.source_ids[sidx]
                wem = self._bnk.get_wem_path(source_id, search_paths=cfg.bankdirs)

                if wem and delete_originals:
                    wem.unlink()

                if path.suffix != ".wem":
                    if not wwise_exe:
                        wwise_exe = cfg.locate_wwise()

                    path = wav2wem(wwise_exe, path)

                wem_id = get_wem_id(path)
                target_path = wem.parent / f"{wem_id}.wem"
                shutil.copyfile(path, target_path)

                source = node.sources[sidx]
                source.source_id = wem_id
                source.media_information.in_memory_media_size = (
                    target_path.stat().st_size
                )
                source.source_type = SourceType.Streaming

                successes += 1

        if self._callback:
            self._callback(self._replacements)

        logger.info(f"Replaced {successes} music tracks")
        yay()

    def _build(self, title: str) -> None:
        with dpg.window(
            label=title,
            width=520,
            height=460,
            no_saved_settings=True,
            tag=self.tag,
            on_close=lambda: dpg.delete_item(window),
        ) as window:
            self._msc_select = add_select_node(
                self._bnk,
                µ("Music manager"),
                self._on_msc_changed,
                node_type=MusicSwitchContainer,
                default=self._bnk.get(1001573296) if self._bnk else None,
                tag=self._t("msc"),
            )
            dpg.add_checkbox(
                label=µ("Delete original wems"),
                default_value=True,
                tag=self._t("delete_originals"),
            )

            with dpg.child_window(
                autosize_x=True,
                height=-120,
            ):
                dpg.add_input_text(
                    default_value="",
                    hint=µ("Filter"),
                    callback=lambda s, a, u: dpg.set_value(self._t("music_table"), a),
                    tag=self._t("music_filter"),
                )
                with dpg.table(
                    header_row=True,
                    borders_outerH=True,
                    borders_outerV=True,
                    tag=self._t("music_table"),
                ):
                    dpg.add_table_column(label=µ("Condition"), width_stretch=True)
                    dpg.add_table_column(label=µ("File"), width_stretch=True)
                    dpg.add_table_column(width_fixed=True)

            dpg.add_spacer(height=1)
            add_paragraphs(
                µ(
                    """\
                    - Music is usually in cs_smain (sss!)
                    - The main music controller is 1001573296 in ER/NR
                    """,
                    "tips",
                ),
                color=style.light_blue,
            )

            dpg.add_separator()
            dpg.add_spacer(height=2)
            dpg.add_text(show=False, tag=self._t("notification"), color=style.red)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label=µ("Scotty, beam them!", "button"),
                    callback=self._on_okay,
                    tag=self._t("button_okay"),
                )
                dpg.add_button(
                    label="?",
                    callback=lambda s, a, u: webbrowser.open(u),
                    user_data="https://ndahn.github.io/yonder/tools/replace_music/",
                )
                with dpg.tooltip(dpg.last_item()):
                    dpg.add_text("https://ndahn.github.io/yonder/tools/replace_music/")

        self.regenerate()

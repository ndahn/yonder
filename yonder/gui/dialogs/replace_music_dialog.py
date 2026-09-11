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
        self._music_tracks: set[int] = set()
        self._replacements: dict[tuple[int, int], Path] = {}
        self._buttons: dict[int, list[tuple[int, int]]] = {}
        self._player: WavPlayer = None
        self._playback_source_id: int = None

        self._build(title)

    def _on_msc_changed(
        self, sender: str, msc: MusicSwitchContainer, user_data: Any
    ) -> None:
        self._close_player()
        self._replacements.clear()
        self.regenerate()

    def _on_music_path_changed(
        self, sender: str, path: Path, info: tuple[int, int]
    ) -> None:
        self._close_player()

        track, sidx = info
        node: MusicTrack = self._bnk[track]
        source_id = node.source_ids[sidx]

        if dpg.get_value(self._t("replace_all")):
            for track in self._music_tracks:
                node = self._bnk.get(track)
                if node:
                    try:
                        sidx = node.source_ids.index(source_id)
                        self._replacements[(track, sidx)] = path
                    except ValueError:
                        pass
        else:
            self._replacements[(track, sidx)] = path

        self.regenerate()

    def _on_restore_track(
        self, sender: str, app_data: Any, info: tuple[int, int]
    ) -> None:
        self._close_player()
        prev = self._replacements.pop(info, None)
        
        if prev is not None:
            dpg.configure_item(sender, tint_color=style.white)
            self.regenerate()

    def _close_player(self) -> None:
        self._set_play_buttons_state(self._playback_source_id, False)
        self._playback_source_id = None

        if self._player:
            self._player.stop()
            self._player = None

    def _init_player(self, track: int, sidx: int) -> WavPlayer:
        self._close_player()
        cfg = get_config()

        if (track, sidx) in self._replacements:
            audio = self._replacements[(track, sidx)]

            if not audio.is_file():
                logger.warning(f"Replacement file {audio.name} not found")
                return None
        else:
            source_id = self._bnk[track].source_ids[sidx]
            audio = self._bnk.get_wem_path(source_id, search_paths=cfg.bankdirs)

            if not audio:
                logger.warning(f"Could not find audio file for {source_id}")
                return None

        if audio.suffix == ".wav":
            wav = audio
        else:
            wav = get_temp_dir() / f"{audio.stem}.wav"

        if not wav.is_file():
            vgmstream_exe = cfg.locate_vgmstream()
            wav = wem2wav(vgmstream_exe, audio, get_temp_dir())[0]

        return WavPlayer(str(wav))

    def _set_play_buttons_state(self, source_id: int, playing: bool) -> None:
        if source_id is None:
            return

        tint = style.light_blue if playing else style.white
        icon = Icons.pause if playing else Icons.play

        for _, btn in self._buttons.get(source_id, []):
            if dpg.does_item_exist(btn):
                dpg.configure_item(btn, texture_tag=icon, tint_color=tint)

    def _on_play_pause_track(
        self, sender: str, app_data: Any, info: tuple[int, int]
    ) -> None:
        track, sidx = info
        node: MusicTrack = self._bnk[track]
        source_id = node.source_ids[sidx]
        player = self._player

        if not player or source_id != self._playback_source_id:
            player = self._init_player(track, sidx)
            if not player:
                return

            self._player = player

        if player.playing:
            player.pause()
            self._set_play_buttons_state(source_id, False)
            self._playback_source_id = None
        else:
            player.play()
            self._set_play_buttons_state(source_id, True)
            self._playback_source_id = source_id

    def regenerate(self) -> None:
        dpg.delete_item(self._t("music_table"), slot=1, children_only=True)

        msc: MusicSwitchContainer = self._msc_select.selected_node
        if not isinstance(msc, MusicSwitchContainer):
            return

        indent_px = 10

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
                dpg.add_text(path, indent=indent * indent_px)

                with dpg.group():
                    for idx, sid in enumerate(node.source_ids):
                        if (node.id, idx) in self._replacements:
                            default = self._replacements[(node.id, idx)]
                        else:
                            default = self._bnk.get_wem_path(sid)

                        add_generic_widget(
                            Path,
                            None,
                            self._on_music_path_changed,
                            default=default,
                            filetypes={},
                            user_data=(node.id, idx),
                            width=-50,
                        )

                with dpg.group():
                    for idx, sid in enumerate(node.source_ids):
                        with dpg.group(horizontal=True):
                            tint = (
                                style.yellow
                                if (node.id, idx) in self._replacements
                                else style.white
                            )
                            reset_btn = dpg.add_image_button(
                                Icons.restore_file,
                                width=18,
                                height=18,
                                tint_color=tint,
                                callback=self._on_restore_track,
                                user_data=(node.id, idx),
                            )
                            play_btn = dpg.add_image_button(
                                Icons.play,
                                width=18,
                                height=18,
                                callback=self._on_play_pause_track,
                                user_data=(node.id, idx),
                            )

                            self._buttons.setdefault(sid, []).append(
                                (reset_btn, play_btn)
                            )

        def delve(root: HIRCNode, path: str, indent: int) -> None:
            todo = [root]

            while todo:
                node = todo.pop()

                if isinstance(node, MusicTrack):
                    self._music_tracks.add(node.id)
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

            if path_prefix:
                with dpg.table_row(
                    filter_key=path_prefix,
                    parent=self._t("music_table"),
                ):
                    dpg.add_text(path_prefix, indent=indent * indent_px)

            for key in keys:
                node = self._bnk.get(tree[key])
                if not node:
                    continue

                condensed = "/".join(p for p in key if p != "*")
                if not condensed:
                    condensed = "*"

                # need to dive down until we find the leaves
                path = path_prefix + condensed
                delve(node, path, indent + 1)

        with dpg.table_row(
            parent=self._t("music_table"),
        ):
            dpg.add_text(msc.get_name())

        with loading_indicator(µ("Discovering"), color=style.purple):
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
                    wem.unlink(missing_ok=True)

                if path.suffix != ".wem":
                    if not wwise_exe:
                        wwise_exe = cfg.locate_wwise()

                    path = wav2wem(wwise_exe, path, get_temp_dir())

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
            width=600,
            height=480,
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
                label=µ("Replace all instances"),
                default_value=True,
                tag=self._t("replace_all"),
            )
            dpg.add_checkbox(
                label=µ("Delete original wems"),
                default_value=True,
                tag=self._t("delete_originals"),
            )

            with dpg.child_window(
                autosize_x=True,
                no_scrollbar=True,
                height=-120,
            ):
                dpg.add_input_text(
                    default_value="",
                    hint=µ("Filter"),
                    callback=lambda s, a, u: dpg.set_value(self._t("music_table"), a),
                    tag=self._t("music_filter"),
                )
                with dpg.table(
                    resizable=True,
                    header_row=True,
                    freeze_rows=1,
                    borders_outerH=True,
                    borders_outerV=True,
                    no_host_extendY=True,
                    scrollY=True,
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
                    label=µ("Let chaos reign!", "button"),
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

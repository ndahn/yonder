from typing import Any, Type
import sys
import logging
import json
from copy import deepcopy
from pathlib import Path
import subprocess
import pyperclip
import networkx as nx
from dearpygui import dearpygui as dpg

from yonder import Soundbank, Node
from yonder.node_types import (
    Action,
    Event,
    WwiseNode,
)

from yonder.util import logger, unpack_soundbank, repack_soundbank
from yonder.query import query_nodes
from yonder.gui.config import Config, load_config
from yonder.gui.helpers import center_window, shorten_path
from yonder.gui.widgets import (
    create_attribute_widgets,
    loading_indicator,
    table_tree_node,
    add_lazy_table_tree_node,
    set_foldable_row_status,
    get_foldable_row_descriptor,
    is_row_visible,
    add_graph_widget,
)
from yonder.gui import style
from yonder.gui.style import themes
from yonder.gui.localization import Localization, English
from yonder.gui.dialogs.about_dialog import about_dialog
from yonder.gui.dialogs.choice_dialog import choice_dialog
from yonder.gui.dialogs.create_node_dialog import create_node_dialog
from yonder.gui.dialogs.new_wwise_event_dialog import new_wwise_event_dialog
from yonder.gui.dialogs.file_dialog import (
    open_file_dialog,
    save_file_dialog,
    choose_folder,
)
from yonder.gui.dialogs.create_simple_sound_dialog import create_simple_sound_dialog
from yonder.gui.dialogs.calc_hash_dialog import calc_hash_dialog
from yonder.gui.dialogs.mass_transfer_dialog import mass_transfer_dialog
from yonder.gui.dialogs.convert_wav_dialog import convert_wavs_dialog
from yonder.gui.dialogs.settings_dialog import settings_dialog
from yonder.gui.dialogs.new_boss_track_dialog import new_boss_track_dialog
from yonder.gui.dialogs.export_sounds_dialog import export_sounds_dialog


# TODO boss bgm: transition rules
# TODO new ambience track
# TODO setup RTPCs


class BanksOfYonder:
    def __init__(self, tag: str = None):
        if tag is None:
            tag = dpg.generate_uuid()

        self.tag = tag
        self.max_list_nodes = 500
        self.language: Localization = English()
        self.bnk: Soundbank = None
        self.event_map: dict[int, Event] = {}
        self.globals_map: dict[int, Event] = {}
        self._selected_root: str = None
        self._selected_node: Node = None
        self._selected_node_backup: dict = None

        self.config: Config = load_config()

        self._setup_menu()
        self._setup_content()
        self._setup_context_menus()
        self._set_bnk_menus_enabled(False)

        class LogHandler(logging.Handler):
            def emit(this, record: logging.LogRecord):
                this.format(record)

                if record.levelno >= logging.ERROR:
                    color = style.red
                elif record.levelno >= logging.WARNING:
                    color = style.yellow
                else:
                    color = style.blue

                self.show_notification(record.message, color)

        sys.excepthook = self._handle_exception
        logger.addHandler(LogHandler())
        dpg.set_frame_callback(5, lambda: logger.info("Hello :3"))

    def _handle_exception(
        self, exc_type: Type[Exception], exc_value: Exception, exc_traceback
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            dpg.stop_dearpygui()
            return

        self.show_notification(str(exc_value), style.red)
        raise exc_value

    def _setup_menu(self) -> None:
        with dpg.menu_bar():
            with dpg.menu(label="File"):
                dpg.add_menu_item(
                    label="Open...",
                    shortcut="ctrl-o",
                    callback=self._open_soundbank,
                )
                dpg.add_menu(
                    label="Recent files",
                    tag=f"{self.tag}_menu_recent_files",
                )
                dpg.add_separator()
                dpg.add_menu_item(
                    label="Save",
                    shortcut="ctrl-s",
                    callback=self._save_soundbank,
                    tag=f"{self.tag}_menu_file_save",
                )
                dpg.add_menu_item(
                    label="Save As...",
                    shortcut="ctrl-shift-s",
                    callback=self._save_soundbank_as,
                    tag=f"{self.tag}_menu_file_save_as",
                )
                dpg.add_separator()
                dpg.add_menu_item(
                    label="Repack",
                    shortcut="f4",
                    callback=self._repack_soundbank,
                    tag=f"{self.tag}_menu_file_repack",
                )
                dpg.add_separator()
                dpg.add_menu_item(
                    label="New Soundbank...",
                    shortcut="ctrl-n",
                    callback=self._create_empty_soundbank,
                )

            dpg.add_separator()
            with dpg.menu(label="Bank", tag=f"{self.tag}_menu_bank"):
                dpg.add_menu_item(label="Pin Orphans", callback=self.pin_lost_objects)

                dpg.add_separator()
                dpg.add_menu_item(
                    label="Solve HIRC",
                    callback=self._bank_solve_hirc,
                )
                dpg.add_menu_item(
                    label="Verify",
                    callback=self._bank_verify,
                )

                dpg.add_separator()
                with dpg.menu(label="Advanced"):
                    dpg.add_menu_item(
                        label="Delete unused wems",
                        callback=self._bank_remove_unused_wems,
                    )
                    dpg.add_menu_item(
                        label="Delete orphans",
                        callback=self._bank_delete_orphans,
                    )

            with dpg.menu(label="Create", tag=f"{self.tag}_menu_create"):
                dpg.add_menu_item(
                    label="Simple Sound",
                    callback=self._open_simple_sound_dialog,
                )
                dpg.add_menu_item(
                    label="Boss Track",
                    callback=self._open_boss_track_dialog,
                )
                dpg.add_menu_item(
                    label="Ambience Track",
                    callback=self._open_ambience_track_dialog,
                    enabled=False,  # TODO
                )
                dpg.add_separator()
                dpg.add_menu_item(
                    label="New Wwise Event",
                    callback=self._open_new_wwise_event_dialog,
                )

            dpg.add_separator()

            with dpg.menu(label="Tools"):
                dpg.add_menu_item(
                    label="Calc Hash",
                    callback=self._open_calc_hash_dialog,
                )
                dpg.add_menu_item(
                    label="Mass Transfer",
                    callback=self._open_transfer_events_dialog,
                )
                dpg.add_menu_item(
                    label="Export Sounds",
                    callback=self._open_export_sounds_dialog,
                )
                dpg.add_menu_item(
                    label="Waves to Wems",
                    callback=self._open_convert_wavs_dialog,
                )

            dpg.add_separator()
            with dpg.menu(label="Yonder"):
                with dpg.menu(label="dearpygui"):
                    dpg.add_menu_item(
                        label="About", callback=lambda: dpg.show_tool(dpg.mvTool_About)
                    )
                    dpg.add_menu_item(
                        label="Metrics",
                        callback=lambda: dpg.show_tool(dpg.mvTool_Metrics),
                    )
                    dpg.add_menu_item(
                        label="Documentation",
                        callback=lambda: dpg.show_tool(dpg.mvTool_Doc),
                    )
                    dpg.add_menu_item(
                        label="Debug", callback=lambda: dpg.show_tool(dpg.mvTool_Debug)
                    )
                    dpg.add_menu_item(
                        label="Style Editor",
                        callback=lambda: dpg.show_tool(dpg.mvTool_Style),
                    )
                    dpg.add_menu_item(
                        label="Font Manager",
                        callback=lambda: dpg.show_tool(dpg.mvTool_Font),
                    )
                    dpg.add_menu_item(
                        label="Item Registry",
                        callback=lambda: dpg.show_tool(dpg.mvTool_ItemRegistry),
                    )
                    dpg.add_menu_item(
                        label="Stack Tool",
                        callback=lambda: dpg.show_tool(dpg.mvTool_Stack),
                    )
                dpg.add_menu_item(
                    label="Settings",
                    callback=self._open_settings_dialog,
                )
                dpg.add_menu_item(
                    label="About",
                    callback=self._open_about_dialog,
                )

        with dpg.handler_registry(tag=f"{self.tag}_shortcut_handler"):
            dpg.add_key_press_handler(dpg.mvKey_None, callback=self._on_key_press)

        self._regenerate_recent_files_menu()

    def _set_bnk_menus_enabled(self, enabled: bool) -> None:
        for subtag in [
            "_menu_file_save",
            "_menu_file_save_as",
            "_menu_file_repack",
            "_menu_bank",
            "_menu_create",
        ]:
            if enabled:
                dpg.enable_item(f"{self.tag}{subtag}")
            else:
                dpg.disable_item(f"{self.tag}{subtag}")

    def _setup_content(self) -> None:
        tag = self.tag

        with dpg.group(horizontal=True):
            with dpg.child_window(
                horizontal_scrollbar=False,
                width=300,
                resizable_x=True,
                autosize_y=True,
                border=False,
                tag=f"{tag}_events_window",
            ):
                with dpg.child_window(border=True, resizable_y=True, height=500):
                    with dpg.tab_bar():
                        with dpg.tab(label="Events"):
                            dpg.add_input_text(
                                hint="Search on enter",
                                width=-1,
                                on_enter=True,
                                callback=self._regenerate_events_list,
                                tag=f"{tag}_events_filter",
                            )
                            dpg.add_text("Showing 0 events", tag=f"{tag}_events_count")
                            with dpg.table(
                                no_host_extendX=True,
                                resizable=True,
                                borders_innerV=True,
                                policy=dpg.mvTable_SizingFixedFit,
                                header_row=False,
                                tag=f"{tag}_events_table",
                            ):
                                dpg.add_table_column(label="Node", width_stretch=True)
                        with dpg.tab(label="Globals"):
                            dpg.add_input_text(
                                hint="Search on enter",
                                width=-1,
                                on_enter=True,
                                callback=self._regenerate_globals_list,
                                tag=f"{tag}_globals_filter",
                            )
                            dpg.add_text(
                                "Showing 0 globals", tag=f"{tag}_globals_count"
                            )
                            with dpg.table(
                                no_host_extendX=True,
                                resizable=True,
                                borders_innerV=True,
                                policy=dpg.mvTable_SizingFixedFit,
                                header_row=False,
                                tag=f"{tag}_globals_table",
                            ):
                                dpg.add_table_column(label="Node", width_stretch=True)
                with dpg.child_window(autosize_y=True, border=True):
                    dpg.add_text("Pinned Nodes")
                    dpg.add_separator()
                    with dpg.table(
                        no_host_extendX=True,
                        header_row=False,
                        resizable=True,
                        policy=dpg.mvTable_SizingFixedFit,
                        scrollY=True,
                        tag=f"{self.tag}_pinned_objects_table",
                    ) as self.pinned_objects_table:
                        dpg.add_table_column(label="Pinned Nodes", width_stretch=True)

            dpg.add_child_window(
                width=600,
                resizable_x=True,
                autosize_y=True,
                border=True,
                tag=f"{tag}_attributes",
            )

            with dpg.child_window(
                width=400,
                autosize_x=True,
                autosize_y=True,
                border=False,
            ):
                dpg.add_input_text(
                    multiline=True,
                    width=-1,
                    height=-30,
                    callback=lambda s, a, u: self._set_json_highlight(True),
                    tag=f"{tag}_json",
                )
                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label="Apply",
                        callback=self.node_apply_json,
                        tag=f"{tag}_json_apply",
                    )
                    dpg.add_button(
                        label="Reload Json",
                        callback=self.update_json_panel,
                    )
                    dpg.add_button(
                        label="Reset Node",
                        callback=self.node_reset_json,
                    )

        # Shown now, but will be positioned properly by the welcome message
        with dpg.window(
            no_title_bar=True,
            no_move=True,
            no_close=True,
            no_resize=True,
            no_saved_settings=True,
            min_size=(10, 10),
            tag=f"{tag}_notification_window",
        ):
            with dpg.group(width=-1):
                dpg.add_text(
                    "Hello :3", color=style.red, tag=f"{tag}_notification_text"
                )

        dpg.bind_item_theme(f"{tag}_notification_window", themes.notification_frame)

        with dpg.handler_registry():
            dpg.add_mouse_click_handler(
                callback=lambda s, a, u: dpg.hide_item(f"{tag}_notification_window")
            )

    def _setup_context_menus(self) -> None:
        tag = self.tag

        with dpg.window(
            popup=True,
            show=False,
            min_size=(50, 20),
            no_saved_settings=True,
            tag=f"{tag}_context_menu",
        ):
            dpg.add_menu_item(
                label="New child",
                callback=self.node_new_child,
                tag=f"{tag}_context_new_child",
            )
            # TODO create action dialog
            with dpg.menu(label="Add action", tag=f"{tag}_context_add_action"):
                dpg.add_menu_item(
                    label="Play",
                    callback=self.node_add_action_play,
                    tag=f"{tag}_context_add_action_play",
                )
                dpg.add_menu_item(
                    label="Event",
                    callback=self.node_add_action_event,
                    tag=f"{tag}_context_add_action_event",
                )
                dpg.add_menu_item(
                    label="Stop",
                    callback=self.node_add_action_stop,
                    tag=f"{tag}_context_add_action_stop",
                )
                dpg.add_menu_item(
                    label="Mute Bus",
                    callback=self.node_add_action_mute_bus,
                    tag=f"{tag}_context_add_action_mute_bus",
                )
                dpg.add_menu_item(
                    label="Reset Bus Volume",
                    callback=self.node_add_action_reset_bus_volume,
                    tag=f"{tag}_context_add_action_reset_bus",
                )

            dpg.add_menu_item(
                label="Show Graph",
                callback=self._open_node_graph,
                tag=f"{tag}_context_show_graph",
            )

            dpg.add_separator()

            dpg.add_menu_item(
                label="Pin",
                callback=lambda s, a, u: self.add_pinned_object(self._selected_node),
                tag=f"{tag}_context_pin",
            )
            dpg.add_menu_item(
                label="Cut",
                callback=self.node_cut,
                tag=f"{tag}_context_cut",
            )
            dpg.add_menu_item(
                label="Copy",
                callback=self.node_copy,
                tag=f"{tag}_context_copy",
            )
            # TODO copy/paste hierarchy
            dpg.add_separator()
            dpg.add_menu_item(
                label="Paste child",
                callback=self.node_paste_child,
                tag=f"{tag}_context_paste_child",
            )

            dpg.add_separator()

            dpg.add_menu_item(
                label="Delete",
                callback=self.node_delete,
                tag=f"{tag}_context_delete",
            )

        with dpg.item_handler_registry(tag=f"{self.tag}_pin_registry"):
            dpg.add_item_clicked_handler(
                button=dpg.mvMouseButton_Left, callback=self.on_pin_selected
            )
            dpg.add_item_clicked_handler(
                button=dpg.mvMouseButton_Right, callback=self.open_pin_menu
            )

    def _on_key_press(self, sender, key: int) -> None:
        if dpg.is_key_down(dpg.mvKey_ModShift) and dpg.is_key_down(dpg.mvKey_ModCtrl):
            if key == dpg.mvKey_S:
                self._save_soundbank_as()

        elif dpg.is_key_down(dpg.mvKey_ModCtrl):
            if key == dpg.mvKey_O:
                self._open_soundbank()
            elif key == dpg.mvKey_S:
                self._save_soundbank()
            elif key == dpg.mvKey_N:
                self._create_empty_soundbank()
            # elif key == dpg.mvKey_Q:
            #     self._exit_app()
            # elif key == dpg.mvKey_Z:
            #     self.undo()
            # elif key == dpg.mvKey_Y:
            #     self.redo()
            # elif key == dpg.mvKey_F:
            #     self.open_search_dialog()

        elif dpg.is_key_down(dpg.mvKey_ModShift):
            pass

        else:
            if key == dpg.mvKey_F4:
                self._repack_soundbank()

    def _regenerate_recent_files_menu(self) -> None:
        dpg.delete_item(f"{self.tag}_menu_recent_files", slot=1, children_only=True)
        # dpg.split_frame()

        def load_file_choice(sender: str, choice: str, path: Path) -> None:
            if choice == "Save":
                self._save_soundbank()
                self._load_soundbank_with_choice(path)
            elif choice == "Save as":
                if self._save_soundbank_as():
                    self._load_soundbank_with_choice(path)
            elif choice == "Just do it":
                self._load_soundbank_with_choice(path)

        def load_file(sender: str, app_data: Any, path: Path) -> None:
            if self.bnk:
                # A soundbank is loaded, save before exiting?
                choice_dialog(
                    f"Save soundbank f{self.bnk.name} first?",
                    ["Save", "Save as", "|", "Just do it"],
                    load_file_choice,
                    title="Continue?",
                    user_data=path,
                )
                return
            else:
                self._load_soundbank_with_choice(path)

        for i in range(10):
            if i < len(self.config.recent_files):
                path = Path(self.config.recent_files[i])
                short = shorten_path(path, maxlen=70)

                dpg.add_menu_item(
                    label=str(short),
                    parent=f"{self.tag}_menu_recent_files",
                    callback=load_file,
                    user_data=path,
                )
            else:
                # We need to add menu item stubs, otherwise the additional items will mess up
                # the dearpygui layout
                dpg.add_menu_item(
                    parent=f"{self.tag}_menu_recent_files",
                    show=False,
                )

    def get_pinned_objects(self) -> list[str]:
        ret = []

        for row in dpg.get_item_children(f"{self.tag}_pinned_objects_table", slot=1):
            ret.append(dpg.get_item_user_data(row))

        return ret

    def add_pinned_object(self, node: int | Node) -> None:
        if node is None:
            return

        if not isinstance(node, Node):
            node = self.bnk[node]

        if dpg.does_item_exist(f"{self.tag}_pin_{node}"):
            # Already pinned
            return

        def on_select(sender: str):
            # No selection
            dpg.set_value(sender, False)

        with dpg.table_row(
            # For some reason self.pinned_objects_table doesn't work?
            parent=f"{self.tag}_pinned_objects_table",
            tag=f"{self.tag}_pin_{node}",
            user_data=node.id,
        ):
            dpg.add_selectable(
                label=str(node),
                span_columns=True,
                callback=on_select,
                user_data=node.id,
            )
            dpg.bind_item_handler_registry(dpg.last_item(), f"{self.tag}_pin_registry")

    def remove_pinned_object(self, node: int | Node) -> None:
        if isinstance(node, Node):
            node = node.id

        for row in dpg.get_item_children(f"{self.tag}_pinned_objects_table", slot=1):
            if dpg.get_item_user_data(row) == node:
                dpg.delete_item(row)
                break

    def remove_all_pinned_objects(self) -> None:
        dpg.delete_item(f"{self.tag}_pinned_objects_table", children_only=True, slot=1)

    def pin_lost_objects(self) -> None:
        for node in self.bnk.find_orphans():
            self.add_pinned_object(node)

    def on_pin_selected(self, sender: str, app_data: str, user_data: Any) -> None:
        _, selectable = app_data
        node_id = dpg.get_item_user_data(selectable)
        node = self.bnk.get(node_id)
        if not node:
            logger.error(f"Node {node_id} no longer exists")
            return

        # Select, but don't jump
        self.select_node(node)

    def open_pin_menu(self, sender: str, app_data: str, user_data: Any) -> None:
        _, selectable = app_data
        node_id = dpg.get_item_user_data(selectable)

        # Pin context menu
        with dpg.window(
            popup=True,
            min_size=(100, 20),
            no_title_bar=True,
            no_resize=True,
            no_move=True,
            no_saved_settings=True,
            autosize=True,
        ) as popup:
            dpg.add_selectable(
                label="Unpin",
                callback=lambda s, a, u: self.remove_pinned_object(u),
                user_data=node_id,
            )
            dpg.add_selectable(
                label="Unpin All",
                callback=self.remove_all_pinned_objects,
            )
            dpg.add_selectable(
                label="Jump To",
                callback=lambda s, a, u: self.jump_to_event_node(u),
                user_data=node_id,
            )

        dpg.set_item_pos(popup, dpg.get_mouse_pos(local=False))

    def show_notification(
        self, msg: str, color: tuple[int, int, int, int] = style.red
    ) -> None:
        w = dpg.get_viewport_width()
        h = (
            dpg.get_viewport_height()
            - dpg.get_item_height(f"{self.tag}_notification_window")
            - 32
        )
        # Note: since this is a popup there's no need for a timer to hide it
        dpg.configure_item(
            f"{self.tag}_notification_window", show=True, pos=(0, h), min_size=(w, 10)
        )
        dpg.configure_item(
            f"{self.tag}_notification_text", default_value=msg, color=color
        )

    def _set_component_highlight(self, widget: str, highlight: bool) -> None:
        if highlight:
            dpg.bind_item_theme(widget, themes.item_highlight)
        else:
            dpg.bind_item_theme(widget, themes.item_default)

    def _save_soundbank(self) -> None:
        if not self.bnk:
            return

        self.bnk.save()

    def _save_soundbank_as(self) -> bool:
        if not self.bnk:
            return False

        lang = self.language
        path = save_file_dialog(
            title=lang.save_soundbank,
            default_dir=str(self.bnk.bnk_dir),
            filetypes={lang.json_files: "*.json"},
        )
        if path:
            loading = loading_indicator("Saving soundbank...")
            try:
                logger.info(f"Saving soundbank to {path}")
                self.bnk.save(path)
                logger.info("Don't forget to repack!")
                return True
            finally:
                dpg.delete_item(loading)

        return False

    def _repack_soundbank(self) -> None:
        if not self.bnk:
            return

        loading = loading_indicator("Repacking...")
        try:
            logger.info("Repacking soundbank")
            bnk2json = self.config.locate_bnk2json()
            repack_soundbank(bnk2json, self.bnk.bnk_dir)
        except subprocess.CalledProcessError as e:
            logger.error(f"Repack failed ({e.returncode}):\n{e.output}")
        finally:
            dpg.delete_item(loading)

    def _create_empty_soundbank(self) -> None:
        path = choose_folder(title="Choose Empty Directory")
        if path:
            path = Path(path)
            empty = not bool(next(path.iterdir(), None))
            if not empty:
                logger.error("Directory not empty")
                return

            bnk = Soundbank.create_empty_soundbank(path, path.name)
            self._load_soundbank(bnk.bnk_dir)

    def _open_soundbank(self) -> None:
        lang = self.language
        path = open_file_dialog(
            title=lang.open,
            filetypes={
                "Soundbank files (.bnk, .json)": ["*.bnk", "*.json"],
                lang.json_files: "*.json",
                lang.soundbank_files: "*.bnk",
            },
        )

        if path:
            self._load_soundbank_with_choice(Path(path))

    def _load_soundbank_with_choice(self, path: Path) -> None:
        if path.name.endswith(".bnk"):
            unpacked_json = path.parent / path.stem / "soundbank.json"

            def on_unpack_choice(sender: str, choice: str, bnk_path: Path):
                if choice == "Open json":
                    target = bnk_path.parent / bnk_path.stem / "soundbank.json"
                else:
                    target = bnk_path

                self._load_soundbank(target)

            if unpacked_json.is_file():
                # Soundbank was already unpacked, ask if we should open the json instead
                choice_dialog(
                    f"Soundbank {path.stem} was already unpacked. Open the json instead?",
                    ["Open json", "Unpack again"],
                    on_unpack_choice,
                    user_data=path,
                    title="Bnk or json?",
                )
                return

        self._load_soundbank(path)

    def _load_soundbank(self, path: Path) -> None:
        if not path.is_file():
            logger.error(f"File not found: {path}")
            self.config.remove_recent_file(path)
            self.config.save()

            self._regenerate_recent_files_menu()
            return

        if path.name.endswith(".bnk"):
            logger.info(f"Unpacking soundbank {path}")
            loading = loading_indicator("Unpacking...")
            try:
                bnk2json = self.config.locate_bnk2json()
                unpack_soundbank(bnk2json, path)
            finally:
                dpg.delete_item(loading)
                dpg.split_frame()  # to enable the next modal loading indicator

        logger.info(f"Loading soundbank {path}")
        loading = loading_indicator("Loading soundbank...")
        try:
            self.remove_all_pinned_objects()
            dpg.set_value(f"{self.tag}_events_filter", "")
            dpg.set_value(f"{self.tag}_globals_filter", "")

            self.bnk = Soundbank.load(path)
            dpg.set_viewport_title(f"Banks of Yonder - {self.bnk.name}")
            self.config.add_recent_file(path)
            self.config.save()
            self._regenerate_recent_files_menu()

            self.regenerate()
            self._set_bnk_menus_enabled(True)
            logger.info(
                f"Loaded soundbank {self.bnk.name} with {len(self.event_map)} events"
            )
        finally:
            dpg.delete_item(loading)

    def _create_root_entry(self, node: Event, table: str) -> None:
        bnk = self.bnk

        def register_context_menu(tag: str, node: Node) -> None:
            registry = f"{tag}_handlers"

            if not dpg.does_item_exist(registry):
                dpg.add_item_handler_registry(tag=registry)

            dpg.add_item_clicked_handler(
                dpg.mvMouseButton_Right,
                callback=self._open_context_menu,
                user_data=(tag, node),
                parent=registry,
            )
            dpg.bind_item_handler_registry(tag, registry)

        def lazy_load_event_structure(
            sender: str, anchor: str, entrypoint: Node
        ) -> None:
            def delve(node: Node) -> None:
                references = node.get_references()
                seen = set()

                # TODO children of first lazy node are expanded if last lazy node is expanded
                # Test withcs_c3671
                for _, ref_id in references:
                    if ref_id in seen:
                        continue

                    sub_tag = f"{self.tag}_node_{ref_id}"
                    while dpg.does_item_exist(sub_tag):
                        sub_tag += "_1"

                    seen.add(ref_id)
                    child = bnk.get(ref_id)
                    if child:
                        with table_tree_node(
                            str(child),
                            on_click_callback=self._on_node_selected,
                            table=table,
                            tag=sub_tag,
                            before=anchor,
                            user_data=child,
                        ) as row:
                            register_context_menu(row.selectable, child)
                            delve(child)
                    else:
                        # reference placeholder?
                        pass

            delve(entrypoint)

        root_row = add_lazy_table_tree_node(
            str(node),
            lazy_load_event_structure,
            on_click_callback=self._on_node_selected,
            table=table,
            tag=f"{self.tag}_node_{node.id}",
            user_data=node,
        )
        register_context_menu(root_row.selectable, node)

    def regenerate(self) -> None:
        dpg.delete_item(f"{self.tag}_attributes", children_only=True, slot=1)
        dpg.set_value(f"{self.tag}_json", "")

        self._regenerate_events_list()
        self._regenerate_globals_list()

        if self._selected_node:
            self.jump_to_event_node(self._selected_node)

    def _regenerate_events_list(self) -> None:
        dpg.delete_item(f"{self.tag}_events_table", children_only=True, slot=1)
        self.event_map.clear()

        all_events = list(self.bnk.query("type=Event"))

        filt: str = dpg.get_value(f"{self.tag}_events_filter").strip()
        if filt:
            # Find the events associated with visible nodes
            g = self.bnk.get_full_tree()
            selected = self.bnk.query(filt)
            events = set()

            for node in selected:
                for pid in nx.ancestors(g, node.id):
                    parent = self.bnk[pid]
                    if parent.type == "Event":
                        events.add(parent)

            events = sorted(events)
        else:
            events = all_events

        for node in events:
            node: Event = node.cast()
            node_tag = self._create_root_entry(node, f"{self.tag}_events_table")
            self.event_map[node.id] = node_tag
            if len(self.event_map) >= self.max_list_nodes:
                break

        dpg.set_value(
            f"{self.tag}_events_count",
            f"Showing {len(self.event_map)}/{len(all_events)} events",
        )

    def _regenerate_globals_list(self) -> None:
        dpg.delete_item(f"{self.tag}_globals_table", children_only=True, slot=1)
        self.globals_map.clear()

        global_nodes = [
            n
            for n in self.bnk
            if n.parent is None and n.type not in ("Event", "Action")
        ]

        type_map: dict[str, list[Node]] = {}
        for node in global_nodes:
            type_map.setdefault(node.type, []).append(node)

        filt: str = dpg.get_value(f"{self.tag}_globals_filter")
        if filt:
            for node_type, nodes in type_map.items():
                type_map[node_type] = list(query_nodes(nodes, filt))

        # Sort the keys
        type_map = {k: sorted(type_map[k]) for k in sorted(type_map.keys())}

        for node_type, nodes in type_map.items():
            if not nodes:
                continue

            with table_tree_node(
                node_type,
                table=f"{self.tag}_globals_table",
                on_click_callback=self._on_node_selected,
            ):
                for node in nodes:
                    node_tag = self._create_root_entry(
                        node, f"{self.tag}_globals_table"
                    )
                    self.globals_map[node.id] = node_tag

                    if len(self.globals_map) >= self.max_list_nodes:
                        break

        dpg.set_value(
            f"{self.tag}_globals_count",
            f"Showing {len(self.globals_map)}/{len(global_nodes)} globals",
        )

    def _open_context_menu(
        self, sender: str, app_data: Any, user_data: tuple[str, Node]
    ) -> None:
        item, node = user_data
        self._on_node_selected(item, app_data, node)

        if "children" in node:
            dpg.show_item(f"{self.tag}_context_new_child")
            dpg.show_item(f"{self.tag}_context_paste_child")
        else:
            dpg.hide_item(f"{self.tag}_context_new_child")
            dpg.hide_item(f"{self.tag}_context_paste_child")

        if isinstance(node, Event):
            dpg.show_item(f"{self.tag}_context_add_action")
        else:
            dpg.hide_item(f"{self.tag}_context_add_action")

        dpg.set_item_pos(f"{self.tag}_context_menu", dpg.get_mouse_pos())
        dpg.show_item(f"{self.tag}_context_menu")

    def select_node(self, node: int | Node) -> None:
        sender = None
        if node:
            node_id = node.id if isinstance(node, Node) else node
            row = f"{self.tag}_node_{node_id}"
            desc = get_foldable_row_descriptor(row)
            sender = desc.selectable

        self._on_node_selected(sender, None, node)

    def _on_node_selected(self, sender: str, app_data: Any, node: int | Node) -> None:
        # Deselect previous selectable
        if self._selected_root and dpg.does_item_exist(self._selected_root):
            dpg.set_value(self._selected_root, False)

        self._selected_root = sender
        if sender is not None:
            dpg.set_value(sender, True)

        if isinstance(node, int):
            node: Node = self.bnk[node]

        if isinstance(node, Node):
            node = node.cast()
            self._selected_node_backup = deepcopy(node.dict)
            dpg.set_value(f"{self.tag}_json", node.json())
        else:
            self._selected_node_backup = None
            dpg.set_value(f"{self.tag}_json", "")

        self._selected_node = node
        self._set_json_highlight(False)

        dpg.delete_item(f"{self.tag}_attributes", children_only=True, slot=1)
        if node:
            create_attribute_widgets(
                self.bnk,
                node,
                lambda s, a, u: self.update_json_panel(),
                lambda s, a, u: self.jump_to_event_node(a),
                tag=f"{self.tag}_attributes_",
                parent=f"{self.tag}_attributes",
            )

    def jump_to_event_node(self, node: int | Node) -> None:
        if isinstance(node, int):
            node_id = node
            node = self.bnk[node_id]
        else:
            node_id = node.id

        if not isinstance(node.cast(), Event):
            for evt, sub in self.bnk.find_event_subgraphs_for(node):
                if not self._selected_node or self._selected_node.id in sub:
                    break
            else:
                logger.error(f"Could not find an event subgraph containing node {node}")
                return

            path = nx.shortest_path(sub, evt.id, node_id)

            for n in path:
                if n == node_id:
                    break

                row = f"{self.tag}_node_{n}"
                set_foldable_row_status(row, True)

            dpg.split_frame()

        # TODO switch to globals tab if not an event node descendant
        self.select_node(node)
        self._scroll_to_item(f"{self.tag}_events_table", node)

    def _scroll_to_item(self, table: str, node: int | Node) -> None:
        node_id = node.id if isinstance(node, Node) else node
        num_visible = 0

        for row in dpg.get_item_children(table, slot=1):
            if not is_row_visible(table, row):
                continue

            num_visible += 1
            if dpg.get_item_alias(row) == f"{self.tag}_node_{node_id}":
                desc = get_foldable_row_descriptor(row)
                _, row_height = dpg.get_item_rect_size(desc.selectable)
                dpg.set_y_scroll(table, row_height * num_visible)
                break
        else:
            logger.error(f"Could not locate root item row for node {node} in {table}")

    def regenerate_attributes(self) -> None:
        self._on_node_selected(self._selected_root, True, self._selected_node)

    def _bank_solve_hirc(self) -> None:
        loading = loading_indicator("Solving...")
        try:
            self.bnk.solve()
        finally:
            dpg.delete_item(loading)

    def _bank_verify(self) -> None:
        loading = loading_indicator("Verifying...")
        try:
            self.bnk.verify()
        finally:
            dpg.delete_item(loading)

    def _bank_remove_unused_wems(self) -> None:
        self.bnk.remove_unused_wems()
        self.regenerate

    def _bank_delete_orphans(self) -> None:
        self.bnk.delete_orphans()
        self.regenerate()

    def node_new_child(self) -> None:
        tag = f"{self.tag}_add_child_to_{self._selected_node.id}"
        if dpg.does_item_exist(tag):
            dpg.show_item(tag)
            dpg.focus_item(tag)
            return

        def on_node_created(node: WwiseNode) -> None:
            self.bnk.add_nodes(node)
            self._selected_node.add_child(node)
            logger.info(f"Attached new node {node} to {self._selected_node}")
            # TODO no need to regenerate everything
            self.regenerate()

        create_node_dialog(self.bnk, on_node_created, tag=tag)

        dpg.split_frame()
        center_window(tag)

    def node_add_action_play(self) -> None:
        act = Action.new_play_action(self.bnk.new_id(), 0)
        self._selected_node.add_action(act)
        self.bnk.add_nodes(act)
        self.regenerate()
        set_foldable_row_status(f"{self.tag}_event_{self._selected_node.id}", True)
        self.select_node(act)

    def node_add_action_event(self) -> None:
        act = Action.new_event_action(self.bnk.new_id(), 0)
        self._selected_node.add_action(act)
        self.bnk.add_nodes(act)
        self.regenerate()
        set_foldable_row_status(f"{self.tag}_event_{self._selected_node.id}", True)
        self.select_node(act)

    def node_add_action_stop(self) -> None:
        act = Action.new_stop_action(self.bnk.new_id(), 0)
        self._selected_node.add_action(act)
        self.bnk.add_nodes(act)
        self.regenerate()
        set_foldable_row_status(f"{self.tag}_event_{self._selected_node.id}", True)
        self.select_node(act)

    def node_add_action_mute_bus(self) -> None:
        act = Action.new_mute_bus_action(self.bnk.new_id(), 0)
        self._selected_node.add_action(act)
        self.bnk.add_nodes(act)
        self.regenerate()
        set_foldable_row_status(f"{self.tag}_event_{self._selected_node.id}", True)
        self.select_node(act)

    def node_add_action_reset_bus_volume(self) -> None:
        act = Action.new_reset_bus_volume_action(self.bnk.new_id(), 0)
        self._selected_node.add_action(act)
        self.bnk.add_nodes(act)
        self.regenerate()
        set_foldable_row_status(f"{self.tag}_event_{self._selected_node.id}", True)
        self.select_node(act)

    def node_cut(self) -> None:
        self.node_copy()
        self.node_delete()
        logger.info(f"Cut node {self._selected_node} to clipboard")
        self._on_node_selected(None, False, None)
        self.regenerate()

    def node_copy(self) -> None:
        data = self._selected_node.json()
        pyperclip.copy(data)
        logger.info(f"Copied node {self._selected_node} to clipboard")

    def node_paste_child(self) -> None:
        data = json.loads(pyperclip.paste())
        node = Node.wrap(data)
        if not isinstance(node, WwiseNode):
            raise ValueError(f"Node {node} cannot be parented")

        if node.id in self.bnk:
            node.id = self.bnk.new_id()
            logger.warning(
                f"ID of pasted node already exists, assigned new ID {node.id}"
            )

        self.bnk.add_nodes(node)
        self._selected_node.add_child(node)
        logger.info(
            f"Pasted node {node} from clipboard as child of {self._selected_node}"
        )
        self.regenerate()

    def node_delete(self) -> None:
        if not self._selected_node:
            return

        self.bnk.delete_nodes(self._selected_node)
        logger.info(f"Deleted node {self._selected_node} and all its children")
        self._on_node_selected(None, False, None)
        self.regenerate()

    def node_apply_json(self) -> None:
        if not self._selected_node:
            return

        data_str = dpg.get_value(f"{self.tag}_json")
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError as e:
            raise ValueError("Failed to parse json") from e

        self._selected_node.update(data)
        self.regenerate()

    def node_reset_json(self) -> None:
        if self._selected_node:
            self._selected_node.update(self._selected_node_backup)
            self.select_node(self._selected_node)

    def update_json_panel(self) -> None:
        value = ""
        if self._selected_node:
            value = self._selected_node.json()
        dpg.set_value(f"{self.tag}_json", value)
        self._set_json_highlight(False)

    def _set_json_highlight(self, highlight: bool) -> None:
        self._set_component_highlight(f"{self.tag}_json", highlight)
        self._set_component_highlight(f"{self.tag}_json_apply", highlight)

    def _open_create_node_dialog(self) -> None:
        tag = f"{self.tag}_create_node_dialog"
        if dpg.does_item_exist(tag):
            dpg.show_item(tag)
            dpg.focus_item(tag)
            return

        def on_node_created(node: WwiseNode) -> None:
            data = node.json()
            pyperclip.copy(data)
            logger.info(f"Copied new node {node} to clipboard")

        create_node_dialog(self.bnk, on_node_created, tag=tag)

        dpg.split_frame()
        center_window(tag)

    def _open_settings_dialog(self) -> None:
        tag = f"{self.tag}_settings_dialog"
        if dpg.does_item_exist(tag):
            dpg.show_item(tag)
            dpg.focus_item(tag)
            return

        settings_dialog(tag=tag)

        dpg.split_frame()
        center_window(tag)

    def _open_node_graph(self) -> None:
        node = self._selected_node
        if not node:
            return

        tag = f"{self.tag}_node_graph_{node.id}"
        if dpg.does_item_exist(tag):
            dpg.show_item(tag)
            dpg.focus_item(tag)
            return

        def on_graph_node_click(sender: str, node: int | Node, user_data: Any) -> None:
            if node in self.bnk:
                self.jump_to_event_node(node)

        with dpg.window(
            label=f"{node}",
            width=400,
            height=400,
            on_close=lambda: dpg.delete_item(window),
        ) as window:
            add_graph_widget(self.bnk, node, on_graph_node_click, width=-1, height=-1)

    def _open_new_wwise_event_dialog(self) -> None:
        tag = f"{self.tag}_new_wwise_event_dialog"
        if dpg.does_item_exist(tag):
            dpg.show_item(tag)
            dpg.focus_item(tag)
            return

        def on_events_created(nodes: list[Node]) -> None:
            logger.info(f"Created {len(nodes)} new nodes")
            self.regenerate()
            self.select_node(nodes[0])

        new_wwise_event_dialog(self.bnk, on_events_created, tag=tag)

        dpg.split_frame()
        center_window(tag)

    def _open_simple_sound_dialog(self) -> None:
        tag = f"{self.tag}_create_simple_sound_dialog"
        if dpg.does_item_exist(tag):
            dpg.show_item(tag)
            dpg.focus_item(tag)
            return

        def on_sound_created(play_evt: Event, stop_evt: Event) -> None:
            logger.info(f"Added new sound {play_evt.lookup_name()} ({play_evt.id})")
            self.add_pinned_object(play_evt)
            self.add_pinned_object(stop_evt)
            self.regenerate()
            self.jump_to_event_node(play_evt)

        create_simple_sound_dialog(self.bnk, on_sound_created, tag=tag)

        dpg.split_frame()
        center_window(tag)

    def _open_boss_track_dialog(self) -> None:
        tag = f"{self.tag}_create_boss_track_dialog"
        if dpg.does_item_exist(tag):
            dpg.show_item(tag)
            dpg.focus_item(tag)
            return

        def on_boss_track_created(bgm_enemy_type: str, nodes: list[Node]) -> None:
            logger.info(
                f"Added new boss track for {bgm_enemy_type}, branch starting at {nodes[0]}"
            )
            self.add_pinned_object(nodes[0])
            self.jump_to_event_node(nodes[0])

        new_boss_track_dialog(self.bnk, on_boss_track_created, tag=tag)

        dpg.split_frame()
        center_window(tag)

    def _open_ambience_track_dialog(self) -> None:
        tag = f"{self.tag}_create_ambience_track_dialog"
        if dpg.does_item_exist(tag):
            dpg.show_item(tag)
            dpg.focus_item(tag)
            return

        def on_ambience_track_created(nodes: list[Node]) -> None:
            logger.info(
                f"Added new ambience track {nodes[0].lookup_name()} ({nodes[0].id})"
            )

        create_ambience_track_dialog(self.bnk, on_ambience_track_created, tag=tag)

        dpg.split_frame()
        center_window(tag)

    def _open_calc_hash_dialog(self) -> None:
        tag = f"{self.tag}_calc_hash_dialog"
        if dpg.does_item_exist(tag):
            dpg.show_item(tag)
            dpg.focus_item(tag)
            return

        calc_hash_dialog(tag=tag)

        dpg.split_frame()
        center_window(tag)

    def _open_transfer_events_dialog(self) -> None:
        tag = f"{self.tag}_transfer_events_dialog"
        if dpg.does_item_exist(tag):
            dpg.show_item(tag)
            dpg.focus_item(tag)
            return

        mass_transfer_dialog(tag=tag)

        dpg.split_frame()
        center_window(tag)

    def _open_export_sounds_dialog(self) -> None:
        tag = f"{self.tag}_convert_wavs_dialog"
        if dpg.does_item_exist(tag):
            dpg.show_item(tag)
            dpg.focus_item(tag)
            return

        export_sounds_dialog(tag=tag)

        dpg.split_frame()
        center_window(tag)

    def _open_convert_wavs_dialog(self) -> None:
        tag = f"{self.tag}_convert_wavs_dialog"
        if dpg.does_item_exist(tag):
            dpg.show_item(tag)
            dpg.focus_item(tag)
            return

        convert_wavs_dialog(self.config, None, tag=tag)

        dpg.split_frame()
        center_window(tag)

    def _open_about_dialog(self) -> None:
        tag = f"{self.tag}_calc_hash_dialog"
        if dpg.does_item_exist(tag):
            dpg.show_item(tag)
            dpg.focus_item(tag)
            return

        about_dialog(tag=tag)

        dpg.split_frame()
        center_window(tag)

    def _exit_app(self):
        dpg.stop_dearpygui()
        dpg.destroy_context()
        sys.exit(0)

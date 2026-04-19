from __future__ import annotations
from typing import Any, Type
import sys
import os
import logging
import json
from pathlib import Path
import subprocess
import pyperclip
import networkx as nx
from dearpygui import dearpygui as dpg

from yonder import Soundbank, HIRCNode
from yonder.types import (
    Action,
    ActorMixer,
    Event,
    Section,
    HIRCSection,
    DataNode,
)
from yonder.types.serialization import serialize
from yonder.util import logger, unpack_soundbank, repack_soundbank
from yonder.query import query_nodes
from .config import Config, get_config
from .helpers import center_window, shorten_path, tmp_dir
from .widgets import (
    DpgItem,
    create_node_widgets,
    create_section_widgets,
    loading_indicator,
    table_tree_node,
    add_lazy_table_tree_node,
    set_foldable_row_status,
    get_foldable_row_descriptor,
    is_row_visible,
    add_graph_widget,
    add_paragraphs,
)
from . import style
from .style import themes
from .localization import (
    set_active_language,
    get_active_language,
    translate_dpg_item,
    get_available_languages,
    µ,
)
from .dialogs.about_dialog import about_dialog
from .dialogs.choice_dialog import simple_choice_dialog
from .dialogs.create_node_dialog import create_node_dialog
from .dialogs.create_wwise_event_dialog import create_wwise_event_dialog
from .dialogs.file_dialog import (
    open_file_dialog,
    save_file_dialog,
    choose_folder,
)
from .dialogs.create_simple_sound_dialog import create_simple_sound_dialog
from .dialogs.batch_sound_builder import create_batch_sound_builder_dialog
from .dialogs.calc_hash_dialog import calc_hash_dialog
from .dialogs.mass_transfer_dialog import mass_transfer_dialog
from .dialogs.convert_wav_dialog import convert_wavs_dialog
from .dialogs.settings_dialog import settings_dialog
from .dialogs.create_boss_track_dialog import create_boss_track_dialog
from .dialogs.export_sounds_dialog import export_sounds_dialog


class BanksOfYonder(DpgItem):
    def __init__(self, tag: str = None):
        super().__init__(tag)

        self.max_list_nodes = 500
        self.bnk: Soundbank = None
        self.event_map: dict[int, str] = {}
        self.globals_map: dict[int, str] = {}
        self._selected_root: str = None
        self._selected_node: HIRCNode = None
        self._selected_section: Section = None
        self._backup: DataNode = None

        self.config: Config = get_config()
        # Call once to
        set_active_language(self.config.language)

        self._setup_menu()
        self._setup_content()
        self._setup_context_menus()
        self._set_bnk_menus_enabled(False)

        # Call late to get all created items translated
        self._change_language(self.config.language)

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
        dpg.set_frame_callback(5, lambda: logger.info(µ("Hello :3", "log")))

    def _handle_exception(
        self, exc_type: Type[Exception], exc_value: Exception, exc_traceback
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            dpg.stop_dearpygui()
            return

        self.show_notification(str(exc_value), style.red)
        raise exc_value

    def _change_language(self, lang: str) -> None:
        languages = get_available_languages()
        if lang not in languages:
            for key, val in languages.items():
                if val == lang:
                    lang = key
                    break
            else:
                raise ValueError(f"Unknown language {lang}")

        set_active_language(lang)
        lang = get_active_language()

        for win in dpg.get_windows():
            translate_dpg_item(win, lang)

        # Only save if changing the language didn't cause any issues
        self.config.language = lang
        self.config.save()

    # def _save_reference_dict(self) -> None:
    #     ret = save_file_dialog(
    #         title=µ("Generate i18n Template"),
    #         filetypes={µ("Localization Templates (.pot)"): "*.pot"},
    #     )
    #     if ret:
    #         save_language_dict(Path(ret))

    def _setup_menu(self) -> None:
        with dpg.menu_bar():
            with dpg.menu(
                label=µ("File", "menu"),
                tag=self._t("menu/file"),
            ):
                dpg.add_menu_item(
                    label=µ("Open...", "menu"),
                    shortcut="ctrl-o",
                    callback=self._open_soundbank,
                    tag=self._t("menu/open"),
                )
                dpg.add_menu(
                    label=µ("Recent files", "menu"),
                    tag=self._t("menu/recent_files"),
                )
                dpg.add_separator()
                dpg.add_menu_item(
                    label=µ("Save", "menu"),
                    shortcut="ctrl-s",
                    callback=self._save_soundbank,
                    tag=self._t("menu/file_save"),
                )
                dpg.add_menu_item(
                    label=µ("Save As...", "menu"),
                    shortcut="ctrl-shift-s",
                    callback=self._save_soundbank_as,
                    tag=self._t("menu/file_save_as"),
                )
                dpg.add_separator()
                dpg.add_menu_item(
                    label=µ("Repack", "menu"),
                    shortcut="f4",
                    callback=self._repack_soundbank,
                    tag=self._t("menu/file_repack"),
                )
                dpg.add_separator()
                dpg.add_menu_item(
                    label=µ("New Soundbank...", "menu"),
                    shortcut="ctrl-n",
                    callback=self._create_empty_soundbank,
                    tag=self._t("menu/new_soundbank"),
                )

            dpg.add_separator()
            with dpg.menu(label=µ("Bank", "menu"), tag=self._t("menu/bank")):
                dpg.add_menu_item(
                    label=µ("Pin Orphans", "menu"),
                    callback=self.pin_lost_objects,
                    tag=self._t("menu/pin_orphans"),
                )

                dpg.add_separator()
                dpg.add_menu_item(
                    label=µ("Solve HIRC", "menu"),
                    callback=self._bank_solve_hirc,
                    tag=self._t("menu/solve_hirc"),
                )
                dpg.add_menu_item(
                    label=µ("Verify", "menu"),
                    callback=self._bank_verify,
                    tag=self._t("menu/verify"),
                )

                dpg.add_separator()
                with dpg.menu(
                    label=µ("Advanced", "menu"),
                    tag=self._t("menu/advanced"),
                ):
                    dpg.add_menu_item(
                        label=µ("Delete unused wems", "menu"),
                        callback=self._bank_remove_unused_wems,
                        tag=self._t("menu/remove_unused_wems"),
                    )
                    dpg.add_menu_item(
                        label=µ("Delete orphans", "menu"),
                        callback=self._bank_delete_orphans,
                        tag=self._t("menu/delete_orphans"),
                    )

            with dpg.menu(label=µ("Create", "menu"), tag=self._t("menu/create")):
                dpg.add_menu_item(
                    label=µ("Simple Sound", "menu"),
                    callback=self._open_simple_sound_dialog,
                    tag=self._t("menu/create_simple_sound"),
                )
                dpg.add_menu_item(
                    label=µ("Batch Sound Builder", "menu"),
                    callback=self._open_batch_sound_builder_dialog,
                    tag=self._t("menu/batch_sound_builder"),
                )
                dpg.add_menu_item(
                    label=µ("Boss Track", "menu"),
                    callback=self._open_boss_track_dialog,
                    tag=self._t("menu/create_boss_track"),
                )
                dpg.add_menu_item(
                    label=µ("Ambience Track", "menu"),
                    callback=self._open_ambience_track_dialog,
                    enabled=False,  # TODO
                    tag=self._t("menu/create_ambience"),
                )
                dpg.add_separator()
                dpg.add_menu_item(
                    label=µ("New Play/Stop Event", "menu"),
                    callback=self._open_new_wwise_event_dialog,
                    tag=self._t("menu/create_event"),
                )

            dpg.add_separator()

            with dpg.menu(label=µ("Tools", "menu")):
                dpg.add_menu_item(
                    label=µ("Calc Hash", "menu"),
                    callback=self._open_calc_hash_dialog,
                    tag=self._t("menu/calc_hash"),
                )
                dpg.add_menu_item(
                    label=µ("Mass Transfer", "menu"),
                    callback=self._open_mass_transfer_dialog,
                    tag=self._t("menu/mass_transfer"),
                )
                dpg.add_menu_item(
                    label=µ("Export Sounds", "menu"),
                    callback=self._open_export_sounds_dialog,
                    tag=self._t("menu/export_sounds"),
                )
                dpg.add_menu_item(
                    label=µ("Waves to Wems", "menu"),
                    callback=self._open_convert_wavs_dialog,
                    tag=self._t("menu/waves_to_wems"),
                )

            dpg.add_separator()
            with dpg.menu(label=µ("Yonder", "menu")):
                with dpg.menu(
                    label=µ("Language", "menu"),
                    tag=self._t("menu/language"),
                ):
                    dpg.add_radio_button(
                        list(get_available_languages().values()),
                        default_value=get_active_language(),
                        callback=lambda s, a, u: self._change_language(a),
                    )
                    # dpg.add_separator()
                    # dpg.add_menu_item(
                    #     label=µ("Save Reference Dict"),
                    #     callback=self._save_reference_dict,
                    #     tag=self._t("menu/save_reference_dict"),
                    # )

                (
                    dpg.add_menu_item(
                        label=µ("Settings", "menu"),
                        callback=self._open_settings_dialog,
                        tag=self._t("menu/settings"),
                    ),
                )
                dpg.add_menu_item(
                    label=µ("Open Temp Dir", "menu"),
                    callback=lambda s, a, u: os.startfile(tmp_dir.name),
                    tag=self._t("menu/open_temp"),
                )

                dpg.add_separator()
                with dpg.menu(label=µ("dearpygui", "menu")):
                    dpg.add_menu_item(
                        label=µ("About", "menu"),
                        callback=lambda: dpg.show_tool(dpg.mvTool_About),
                    )
                    dpg.add_menu_item(
                        label=µ("Metrics", "menu"),
                        callback=lambda: dpg.show_tool(dpg.mvTool_Metrics),
                    )
                    dpg.add_menu_item(
                        label=µ("Documentation", "menu"),
                        callback=lambda: dpg.show_tool(dpg.mvTool_Doc),
                    )
                    dpg.add_menu_item(
                        label=µ("Debug", "menu"),
                        callback=lambda: dpg.show_tool(dpg.mvTool_Debug),
                    )
                    dpg.add_menu_item(
                        label=µ("Style Editor", "menu"),
                        callback=lambda: dpg.show_tool(dpg.mvTool_Style),
                    )
                    dpg.add_menu_item(
                        label=µ("Font Manager", "menu"),
                        callback=lambda: dpg.show_tool(dpg.mvTool_Font),
                    )
                    dpg.add_menu_item(
                        label=µ("Item Registry", "menu"),
                        callback=lambda: dpg.show_tool(dpg.mvTool_ItemRegistry),
                    )
                    dpg.add_menu_item(
                        label=µ("Stack Tool", "menu"),
                        callback=lambda: dpg.show_tool(dpg.mvTool_Stack),
                    )

                dpg.add_separator()
                dpg.add_menu_item(
                    label=µ("About", "menu"),
                    callback=self._open_about_dialog,
                    tag=self._t("menu/about"),
                )

        with dpg.handler_registry(tag=self._t("shortcut_handler")):
            dpg.add_key_press_handler(dpg.mvKey_None, callback=self._on_key_press)

        self._regenerate_recent_files_menu()

    def _set_bnk_menus_enabled(self, enabled: bool) -> None:
        for subtag in [
            "menu/file_save",
            "menu/file_save_as",
            "menu/file_repack",
            "menu/bank",
            "menu/create",
        ]:
            if enabled:
                dpg.enable_item(self._t(subtag))
            else:
                dpg.disable_item(self._t(subtag))

    def _setup_content(self) -> None:
        with dpg.group(horizontal=True):
            with dpg.child_window(
                horizontal_scrollbar=False,
                width=300,
                resizable_x=True,
                autosize_y=True,
                border=False,
                tag=self._t("events_window"),
            ):
                with dpg.child_window(border=True, resizable_y=True, height=500):
                    with dpg.tab_bar(tag=self._t("tabs")):
                        with dpg.tab(label=µ("Events"), tag=self._t("tab_events")):
                            with dpg.group(horizontal=True):
                                dpg.add_input_text(
                                    hint=µ("Search on enter"),
                                    width=-30,
                                    on_enter=True,
                                    callback=self._regenerate_events_list,
                                    tag=self._t("events_filter"),
                                )
                                dpg.add_button(
                                    label="?",
                                    small=True,
                                )
                                with dpg.tooltip(dpg.last_item()):
                                    add_paragraphs(
                                        # See https://lucene.apache.org/core/2_9_4/queryparsersyntax.html
                                        µ(
                                            """\
                                            Supports Lucene-style search queries (<field>=<value>). 

                                            - You may use the * wildcard for values
                                            - Field paths are prepended by ** unless quoted
                                            - Use [X..Y] to specify a value range
                                            - Precede your value with tilde ~ to do a fuzzy search
                                            - Terms may be combined using grouping, OR, NOT. 
                                            - Terms separated by a space are assumed to be AND.

                                            You may run queries over the following fields:
                                            - id (or hash), type, name
                                            - any field name
                                            - any field path separated by slashes /

                                            Examples:
                                            - id=*588 OR type=RandomSequenceContainer
                                            - source_id=123456789
                                            - NOT "node_base_params/parent_id"=[100000..200000]
                                            - name=~Play_s*""",
                                            "tips",
                                        ),
                                        color=style.light_blue,
                                    )

                            dpg.add_text(
                                "Showing 0 events", tag=self._t("events_count")
                            )
                            with dpg.table(
                                no_host_extendX=True,
                                resizable=True,
                                borders_innerV=True,
                                policy=dpg.mvTable_SizingFixedFit,
                                header_row=False,
                                tag=self._t("events_table"),
                            ):
                                dpg.add_table_column(
                                    label=µ("Node"),
                                    width_stretch=True,
                                    tag=self._t("events_col_nodes"),
                                )

                        with dpg.tab(label=µ("Globals"), tag=self._t("tab_globals")):
                            dpg.add_input_text(
                                hint="Search on enter",
                                width=-1,
                                on_enter=True,
                                callback=self._regenerate_globals_list,
                                tag=self._t("globals_filter"),
                            )
                            dpg.add_text(
                                "Showing 0 globals", tag=self._t("globals_count")
                            )
                            with dpg.table(
                                no_host_extendX=True,
                                resizable=True,
                                borders_innerV=True,
                                policy=dpg.mvTable_SizingFixedFit,
                                header_row=False,
                                tag=self._t("globals_table"),
                            ):
                                dpg.add_table_column(
                                    label=µ("Node"),
                                    width_stretch=True,
                                    tag=self._t("globals_col_nodes"),
                                )

                        with dpg.tab(label=µ("Sections"), tag=self._t("tab_sections")):
                            with dpg.table(
                                no_host_extendX=True,
                                resizable=True,
                                borders_innerV=True,
                                policy=dpg.mvTable_SizingFixedFit,
                                header_row=False,
                                tag=self._t("sections_table"),
                            ):
                                dpg.add_table_column(
                                    label=µ("Section"),
                                    width_stretch=True,
                                    tag=self._t("sections_col_nodes"),
                                )

                with dpg.child_window(autosize_y=True, border=True):
                    dpg.add_text("Pinned Nodes", tag=self._t("pinned_nodes"))
                    dpg.add_separator()
                    with dpg.table(
                        no_host_extendX=True,
                        header_row=False,
                        resizable=True,
                        policy=dpg.mvTable_SizingFixedFit,
                        scrollY=True,
                        tag=self._t("pinned_objects_table"),
                    ) as self.pinned_objects_table:
                        dpg.add_table_column(
                            label=µ("Pinned Nodes"),
                            width_stretch=True,
                            tag=self._t("pinned_nodes_col_nodes"),
                        )

            dpg.add_child_window(
                width=600,
                resizable_x=True,
                autosize_y=True,
                border=True,
                tag=self._t("attributes"),
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
                    tag=self._t("json"),
                )
                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label=µ("Apply", "button"),
                        callback=self.apply_json,
                        tag=self._t("json_apply"),
                    )
                    dpg.add_button(
                        label=µ("Reload Json", "button"),
                        callback=self.update_json_panel,
                        tag=self._t("json_reload"),
                    )
                    dpg.add_button(
                        label=µ("Reset Node", "button"),
                        callback=self.reset_from_json,
                        tag=self._t("json_reset"),
                    )

        # Shown now, but will be positioned properly by the welcome message
        with dpg.window(
            no_title_bar=True,
            no_move=True,
            no_close=True,
            no_resize=True,
            no_saved_settings=True,
            min_size=(10, 10),
            tag=self._t("notification_window"),
        ):
            with dpg.group(width=-1):
                dpg.add_text(
                    "Hello :3", color=style.red, tag=self._t("notification_text")
                )

        dpg.bind_item_theme(self._t("notification_window"), themes.notification_frame)

        with dpg.handler_registry():
            dpg.add_mouse_click_handler(
                callback=lambda s, a, u: dpg.hide_item(self._t("notification_window"))
            )

    def _setup_context_menus(self) -> None:
        with dpg.window(
            popup=True,
            show=False,
            min_size=(50, 20),
            no_saved_settings=True,
            tag=self._t("context_menu"),
        ):
            dpg.add_menu_item(
                label=µ("Show Graph", "menu"),
                callback=self._open_node_graph,
                tag=self._t("context/show_graph"),
            )
            dpg.add_menu_item(
                label=µ("Pin", "menu"),
                callback=lambda s, a, u: self.add_pinned_object(self._selected_node),
                tag=self._t("context/pin"),
            )

            dpg.add_separator()

            with dpg.menu(label=µ("Copy", "menu"), tag=self._t("context/copy")):
                dpg.add_menu_item(
                    label=µ("Node", "menu"),
                    callback=self.node_copy,
                    tag=self._t("context/copy_node"),
                )
                dpg.add_menu_item(
                    label=µ("Hierarchy", "menu"),
                    callback=self.node_copy_hierarchy,
                    tag=self._t("context/copy_hierarchy"),
                )

            with dpg.menu(label=µ("Paste", "menu"), tag=self._t("context/paste")):
                dpg.add_menu_item(
                    label=µ("Attach", "menu"),
                    callback=self.node_attach,
                    tag=self._t("context/paste_node"),
                )
                dpg.add_menu_item(
                    label=µ("New child", "menu"),
                    callback=self.node_new_child,
                    tag=self._t("context/paste_new"),
                )

            dpg.add_separator()
            with dpg.menu(label=µ("Delete", "menu"), tag=self._t("context/delete")):
                dpg.add_menu_item(
                    label=µ("Node", "menu"),
                    callback=self.node_delete,
                    tag=self._t("context/delete_node"),
                )
                dpg.add_menu_item(
                    label=µ("Tree", "menu"),
                    callback=self.node_delete_tree,
                    tag=self._t("context/delete_node_tree"),
                )

        with dpg.item_handler_registry(tag=self._t("pin_registry")):
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
        dpg.delete_item(self._t("menu/recent_files"), slot=1, children_only=True)
        # dpg.split_frame()

        def load_file_choice(sender: str, choice: int, path: Path) -> None:
            if choice == 0:
                self._save_soundbank()
                self._load_soundbank_with_choice(path)
            elif choice == 1:
                if self._save_soundbank_as():
                    self._load_soundbank_with_choice(path)
            elif choice == 2:
                self._load_soundbank_with_choice(path)

        def load_file(sender: str, app_data: Any, path: Path) -> None:
            if self.bnk:
                # A soundbank is loaded, save before exiting?
                simple_choice_dialog(
                    µ("Save soundbank first?"),
                    [
                        µ("Save"),
                        µ("Save as"),
                        "|",
                        µ("Just do it"),
                    ],
                    load_file_choice,
                    title=µ("Continue?"),
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
                    parent=self._t("menu/recent_files"),
                    callback=load_file,
                    user_data=path,
                )
            else:
                # We need to add menu item stubs, otherwise the additional items will mess up
                # the dearpygui layout
                dpg.add_menu_item(
                    parent=self._t("menu/recent_files"),
                    show=False,
                )

    def get_pinned_objects(self) -> list[str]:
        ret = []

        for row in dpg.get_item_children(self._t("pinned_objects_table"), slot=1):
            ret.append(dpg.get_item_user_data(row))

        return ret

    def add_pinned_object(self, node: int | HIRCNode) -> None:
        if node is None:
            return

        if not isinstance(node, HIRCNode):
            node = self.bnk[node]

        if dpg.does_item_exist(self._t(f"pin_{node.id}")):
            # Already pinned
            return

        def on_select(sender: str):
            # No selection
            dpg.set_value(sender, False)

        with dpg.table_row(
            # For some reason self.pinned_objects_table doesn't work?
            parent=self._t("pinned_objects_table"),
            tag=self._t(f"pin_{node.id}"),
            user_data=node.id,
        ):
            dpg.add_selectable(
                label=str(node),
                span_columns=True,
                callback=on_select,
                user_data=node.id,
            )
            dpg.bind_item_handler_registry(dpg.last_item(), self._t("pin_registry"))

    def remove_pinned_object(self, node: int | HIRCNode) -> None:
        if isinstance(node, HIRCNode):
            node = node.id

        for row in dpg.get_item_children(self._t("pinned_objects_table"), slot=1):
            if dpg.get_item_user_data(row) == node:
                dpg.delete_item(row)
                break

    def remove_all_pinned_objects(self) -> None:
        dpg.delete_item(self._t("pinned_objects_table"), children_only=True, slot=1)

    def pin_lost_objects(self) -> None:
        orphans = self.bnk.find_orphans()
        logger.info(µ("Found {num} orphaned nodes").format(len(orphans)))
        for node in orphans:
            self.add_pinned_object(node)

    def on_pin_selected(self, sender: str, app_data: str, user_data: Any) -> None:
        _, selectable = app_data
        node_id = dpg.get_item_user_data(selectable)
        node = self.bnk.get(node_id)
        if not node:
            logger.error(µ("Node {node} no longer exists", "log").format(node=node_id))
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
            on_close=lambda: dpg.delete_item(popup),
        ) as popup:
            dpg.add_selectable(
                label=µ("Unpin"),
                callback=lambda s, a, u: self.remove_pinned_object(u),
                user_data=node_id,
                tag=self._t("pin/unpin"),
            )
            dpg.add_selectable(
                label=µ("Unpin All"),
                callback=self.remove_all_pinned_objects,
                tag=self._t("pin/unpin_all"),
            )
            dpg.add_separator()
            dpg.add_selectable(
                label=µ("Jump To"),
                callback=lambda s, a, u: self.jump_to_node(u),
                user_data=node_id,
                tag=self._t("jump_to"),
            )

        dpg.set_item_pos(popup, dpg.get_mouse_pos(local=False))

    def show_notification(
        self, msg: str, color: tuple[int, int, int, int] = style.red
    ) -> None:
        w = dpg.get_viewport_width()
        h = (
            dpg.get_viewport_height()
            - dpg.get_item_height(self._t("notification_window"))
            - 32
        )
        # Note: since this is a popup there's no need for a timer to hide it
        dpg.configure_item(
            self._t("notification_window"), show=True, pos=(0, h), min_size=(w, 10)
        )
        dpg.configure_item(self._t("notification_text"), default_value=msg, color=color)

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

        path = save_file_dialog(
            title=µ("Save Soundbank"),
            default_dir=str(self.bnk.bnk_dir),
            filetypes={µ("JSON (.json)", "filetypes"): "*.json"},
        )
        if path:
            loading = loading_indicator(µ("Saving soundbank...", "loading"))
            try:
                logger.info(µ("Saving soundbank to {name}", "log").format(name=path))
                self.bnk.save(path)
                logger.info(µ("Don't forget to repack!", "log"))
                return True
            finally:
                dpg.delete_item(loading)

        return False

    def _repack_soundbank(self) -> None:
        if not self.bnk:
            return

        loading = loading_indicator(µ("Repacking...", "loading"))
        try:
            logger.info(µ("Repacking soundbank", "log"))
            bnk2json = self.config.locate_bnk2json()
            repack_soundbank(bnk2json, self.bnk.bnk_dir)
        except subprocess.CalledProcessError as e:
            error_msg = f"(E{e.returncode})\n{e.output}"
            logger.error(µ("Repack failed: {error}", "log").format(error=error_msg))
        finally:
            dpg.delete_item(loading)

    def _create_empty_soundbank(self) -> None:
        path = choose_folder(title=µ("Choose Empty Directory"))
        if path:
            path = Path(path)
            empty = not bool(next(path.iterdir(), None))
            if not empty:
                logger.error(µ("Directory not empty", "log"))
                return

            bnk = Soundbank.create_empty_soundbank(path, path.name)
            self._load_soundbank(bnk.bnk_dir)

    def _open_soundbank(self) -> None:
        path = open_file_dialog(
            title=µ("Open"),
            filetypes={
                µ("Supported files", "filetypes"): ["*.bnk", "*.json"],
                µ("JSON (.json)", "filetypes"): "*.json",
                µ("Soundbanks (.bnk)", "filetypes"): "*.bnk",
            },
        )

        if path:
            self._load_soundbank_with_choice(Path(path))

    def _load_soundbank_with_choice(self, path: Path) -> None:
        if path.name.endswith(".bnk"):
            unpacked_json = path.parent / path.stem / "soundbank.json"

            def on_unpack_choice(sender: str, choice: int, bnk_path: Path):
                if choice == 0:
                    target = bnk_path.parent / bnk_path.stem / "soundbank.json"
                else:
                    target = bnk_path

                self._load_soundbank(target)

            if unpacked_json.is_file():
                # Soundbank was already unpacked, ask if we should open the json instead
                simple_choice_dialog(
                    µ(
                        "Soundbank {soundbank} was already unpacked. Open the json instead?"
                    ).format(soundbank=path.stem),
                    [µ("Open json"), µ("Unpack again")],
                    on_unpack_choice,
                    user_data=path,
                    title=µ("Bnk or json?"),
                )
                return

        self._load_soundbank(path)

    def _load_soundbank(self, path: Path) -> None:
        if path.is_dir():
            path = path / "soundbank.json"

        if not path.is_file():
            logger.error(µ("File not found: {name}", "log").format(name=path))
            self.config.remove_recent_file(path)
            self.config.save()

            self._regenerate_recent_files_menu()
            return

        if path.name.endswith(".bnk"):
            logger.info(µ("Unpacking soundbank {name}", "log").format(name=path))
            loading = loading_indicator(µ("Unpacking...", "loading"))
            try:
                bnk2json = self.config.locate_bnk2json()
                unpack_soundbank(bnk2json, path)
            finally:
                dpg.delete_item(loading)
                dpg.split_frame()  # to enable the next modal loading indicator

        logger.info(µ("Loading soundbank {name}", "log").format(name=path))
        loading = loading_indicator(µ("Loading soundbank...", "loading"))
        try:
            self.remove_all_pinned_objects()
            dpg.set_value(self._t("events_filter"), "")
            dpg.set_value(self._t("globals_filter"), "")

            self.bnk = Soundbank.from_file(path)
            # NOTE: don't translate to avoid bakemoji on some windows configurations
            dpg.set_viewport_title(f"Banks of Yonder - {self.bnk.name}")
            self.config.add_recent_file(path)
            self.config.save()
            self._regenerate_recent_files_menu()

            self.regenerate()
            self._set_bnk_menus_enabled(True)
            logger.info(
                µ("Loaded soundbank {name} with {num_nodes} nodes").format(
                    name=self.bnk.name, num_nodes=len(self.bnk)
                )
            )
        finally:
            dpg.delete_item(loading)

    def _create_root_entry(self, node: HIRCNode, table: str) -> str:
        bnk = self.bnk

        def register_context_menu(tag: str, node: HIRCNode) -> None:
            registry = self._t(f"ctx_handler_{node.id}")

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
            sender: str, anchor: str, entrypoint: HIRCNode
        ) -> None:
            def delve(node: HIRCNode) -> None:
                references = node.get_references()
                seen = set()

                # TODO children of first lazy node are expanded if last lazy node is expanded
                # Test withcs_c3671
                for _, ref_id in references:
                    if ref_id in seen:
                        continue

                    sub_tag = self._t(f"node_{ref_id}")
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
            tag=self._t(f"node_{node.id}"),
            user_data=node,
        )
        register_context_menu(root_row.selectable, node)

        return root_row.row

    def regenerate(self) -> None:
        dpg.delete_item(self._t("attributes"), children_only=True, slot=1)
        dpg.set_value(self._t("json"), "")

        self._regenerate_events_list()
        self._regenerate_globals_list()
        self._regenerate_sections_list()

        if self._selected_node:
            self.jump_to_node(self._selected_node)
        elif self._selected_section:
            self.select_section(self._selected_section)

    def _regenerate_events_list(self) -> None:
        dpg.delete_item(self._t("events_table"), children_only=True, slot=1)
        self.event_map.clear()

        all_events: list[Event] = list(self.bnk.query("type=Event"))

        filt: str = dpg.get_value(self._t("events_filter")).strip()
        if filt:
            # Find the events associated with visible nodes
            g = self.bnk.get_full_tree()
            selected = self.bnk.query(filt)
            events = set()

            for node in selected:
                if isinstance(node, Event):
                    events.add(node)
                else:
                    for pid in nx.ancestors(g, node.id):
                        parent = self.bnk[pid]
                        if isinstance(parent, Event):
                            events.add(parent)
                            break
            events = list(events)
        else:
            events = all_events

        def evt_sort_key(evt: Event) -> str:
            name = evt.name
            if not name:
                return f"zzz{evt.id}"

            if name.startswith("Play"):
                return f"00_{name}"
            elif name.startswith("Stop"):
                return f"01_{name}"
            return f"99_{name}"

        events.sort(key=evt_sort_key)
        for node in events:
            node_tag = self._create_root_entry(node, self._t("events_table"))
            self.event_map[node.id] = node_tag
            if len(self.event_map) >= self.max_list_nodes:
                break

        dpg.set_value(
            self._t("events_count"),
            f"Showing {len(self.event_map)}/{len(all_events)} events",
        )

    def _regenerate_globals_list(self) -> None:
        dpg.delete_item(self._t("globals_table"), children_only=True, slot=1)
        self.globals_map.clear()

        global_nodes = [
            n
            for n in self.bnk
            if (
                getattr(n, "parent", None) is None
                and not isinstance(n, (Event, Action))
            )
            or isinstance(n, ActorMixer)
        ]

        type_map: dict[str, list[HIRCNode]] = {}
        for node in global_nodes:
            type_map.setdefault(node.type_name, []).append(node)

        filt: str = dpg.get_value(self._t("globals_filter"))
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
                table=self._t("globals_table"),
                tag=self._t(f"globals_{node_type}"),
                # Callback will deselect since no node will be passed in user_data
                on_click_callback=self._on_node_selected,
            ):
                for node in nodes:
                    node_tag = self._create_root_entry(node, self._t("globals_table"))
                    self.globals_map[node.id] = node_tag

                    if len(self.globals_map) >= self.max_list_nodes:
                        break

        dpg.set_value(
            self._t("globals_count"),
            µ("Showing {num}/{total} globals").format(
                num=len(self.globals_map), total=len(global_nodes)
            ),
        )

    def _regenerate_sections_list(self) -> None:
        dpg.delete_item(self._t("sections_table"), children_only=True, slot=1)

        for sec in self.bnk.sections.values():
            with dpg.table_row(parent=self._t("sections_table")):
                dpg.add_selectable(
                    label=sec.name,
                    span_columns=True,
                    callback=self._on_section_selected,
                    user_data=sec.name,
                    tag=self._t(f"sections_{sec.name}"),
                )

    def select_section(self, section: str | Section) -> None:
        sender = None
        if section:
            # Jump to sections tab
            dpg.set_value(self._t("tabs", self._t("tab_sections")))
            sec_name = section if isinstance(section, str) else section.name
            sender = self._t(f"sections_{sec_name}")

        self._on_section_selected(sender, True, sec_name)

    def _on_section_selected(self, sender: str, selected: bool, sec_name: str) -> None:
        # Deselect all other sections
        for sec in self.bnk.sections.values():
            dpg.set_value(self._t(f"sections_{sec.name}"), False)
        dpg.set_value(self._t(f"sections_{sec_name}"), True)

        section = self.bnk.sections.get(sec_name)
        self._selected_section = section
        self._selected_node = None

        self.update_json_panel()

        dpg.delete_item(self._t("attributes"), children_only=True, slot=1)
        if section:
            self._backup = section.copy()

            create_section_widgets(
                self.bnk,
                section,
                lambda s, a, u: self.update_json_panel(),
                tag=self._t("attributes_"),
                parent=self._t("attributes"),
            )

    def _open_context_menu(
        self, sender: str, app_data: Any, user_data: tuple[str, HIRCNode]
    ) -> None:
        item, node = user_data
        self._on_node_selected(item, app_data, node)

        # NOTE hide or show context menu items here if needed

        dpg.set_item_pos(self._t("context_menu"), dpg.get_mouse_pos())
        dpg.show_item(self._t("context_menu"))

    def select_node(self, node: int | HIRCNode) -> None:
        sender = None
        if node:
            node_id = node.id if isinstance(node, HIRCNode) else node
            row = self._t(f"node_{node_id}")
            desc = get_foldable_row_descriptor(row)
            sender = desc.selectable

        self._on_node_selected(sender, True, node)

    def _on_node_selected(
        self, sender: str, app_data: Any, node: int | HIRCNode
    ) -> None:
        # Deselect previous selectable
        if self._selected_root and dpg.does_item_exist(self._selected_root):
            dpg.set_value(self._selected_root, False)

        self._selected_root = sender
        if sender is not None:
            dpg.set_value(sender, True)

        if isinstance(node, int):
            node: HIRCNode = self.bnk[node]

        if isinstance(node, HIRCNode):
            self._backup = node.copy()
            dpg.set_value(self._t("json"), node.json())
        else:
            self._backup = None
            dpg.set_value(self._t("json"), "")

        self._selected_node = node
        self._selected_section = None
        self._set_json_highlight(False)

        dpg.delete_item(self._t("attributes"), children_only=True, slot=1)
        if node:
            create_node_widgets(
                self.bnk,
                node,
                lambda s, a, u: self.update_json_panel(),
                lambda s, a, u: self.jump_to_node(a),
                tag=self._t("attributes_"),
                parent=self._t("attributes"),
            )

    def jump_to_node(self, node: int | HIRCNode) -> None:
        if node in (0, None):
            return

        if isinstance(node, int):
            node_id = node
            node = self.bnk[node_id]
        else:
            node_id = node.id

        if node_id in self.globals_map:
            table = self._t("globals_table")

            # Switch to globals tab
            dpg.set_value(self._t("tabs", self._t("tab_globals")))

            # Unfold the category
            # FIXME: make sure the node row actually exists despite count limits!
            row = self._t(f"globals_{node.type_name}")
            set_foldable_row_status(row, True)

        else:
            table = self._t("events_table")

            # Switch to events tab
            dpg.set_value(self._t("tabs"), self._t("tab_events"))

            if not isinstance(node, Event):
                for evt, sub in self.bnk.find_event_subgraphs_for(node):
                    if not self._selected_node or self._selected_node.id in sub:
                        break
                else:
                    logger.error(
                        µ(
                            "Could not find an event subgraph containing node {node}"
                        ).format(node=node)
                    )
                    return

                path = nx.shortest_path(sub, evt.id, node_id)

                # Unfold the structure
                for n in path:
                    if n == node_id:
                        break

                    row = self._t(f"node_{n}")
                    set_foldable_row_status(row, True)

                dpg.split_frame()

        self.select_node(node)
        self._scroll_to_item(table, node)

    def _scroll_to_item(self, table: str, node: int | HIRCNode) -> None:
        node_id = node.id if isinstance(node, HIRCNode) else node
        num_visible = 0

        for row in dpg.get_item_children(table, slot=1):
            if not is_row_visible(table, row):
                continue

            num_visible += 1
            if dpg.get_item_alias(row) == self._t(f"node_{node_id}"):
                desc = get_foldable_row_descriptor(row)
                _, row_height = dpg.get_item_rect_size(desc.selectable)
                dpg.set_y_scroll(table, row_height * num_visible)
                break
        else:
            logger.error(
                µ("Could not locate root item row for node {node} in {table}").format(
                    node=node, table=table
                )
            )

    def regenerate_attributes(self) -> None:
        self._on_node_selected(self._selected_root, True, self._selected_node)

    def _bank_solve_hirc(self) -> None:
        loading = loading_indicator(µ("Solving...", "loading"))
        try:
            self.bnk.solve()
        finally:
            dpg.delete_item(loading)

    def _bank_verify(self) -> None:
        loading = loading_indicator(µ("Verifying...", "loading"))
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

    def node_copy(self) -> None:
        data = {"yonder_nodes": [self._selected_node]}
        pyperclip.copy(json.dumps(serialize(data), indent=2))
        logger.info(
            µ("Copied node {node} to clipboard").format(node=self._selected_node)
        )

    def node_copy_hierarchy(self) -> None:
        g = self.bnk.get_subtree(self._selected_node, include_external=False)
        nodes = []

        for nid in g:
            node = self.bnk.get(nid)
            if not node:
                logger.warning(
                    µ("Subtree has reference to unknown node {node}", "log").format(
                        node=nid
                    )
                )
                continue

            nodes.append(node)

        data = {"yonder_nodes": nodes}
        pyperclip.copy(json.dumps(serialize(data), indent=2))
        logger.info(
            µ("Copied {node} and {num} descendants to clipboard").format(
                node=self._selected_node, num=len(nodes) - 1
            )
        )

    def node_new_child(self) -> None:
        tag = self._t(f"add_child_to_{self._selected_node.id}")
        if dpg.does_item_exist(tag):
            dpg.show_item(tag)
            dpg.focus_item(tag)
            return

        def on_node_created(node: HIRCNode) -> None:
            self.bnk.add_nodes(node)
            self._selected_node.children.add(node)
            logger.info(
                µ("Attached new node {node} to {parent}").format(
                    node=node, parent=self._selected_node
                )
            )
            # TODO no need to regenerate everything
            self.regenerate()

        create_node_dialog(self.bnk, on_node_created, tag=tag)

        dpg.split_frame()
        center_window(tag)

    def node_attach(self) -> None:
        try:
            data = json.loads(pyperclip.paste())
        except json.JSONDecodeError:
            raise ValueError("Clipboard does not contain a valid hierarchy")

        if "yonder_nodes" not in data:
            raise ValueError("Clipboard does not contain a valid hierarchy")

        nodes = [HIRCNode.from_dict(n) for n in data["yonder_nodes"]]
        id_map = {}

        # Create the ID mappings first
        for n in reversed(nodes):
            old_id = n.id
            new_id = self.bnk.new_id()
            id_map[old_id] = new_id
            n.id = new_id

        # Then update all references, including parent IDs
        for n in nodes:
            for path, ref in n.get_references():
                if ref in id_map:
                    n.set_value(path, id_map[ref])

            if not isinstance(n, Action) and n.parent in id_map:
                n.parent = id_map[n.parent]

        self.bnk.add_nodes(*nodes)
        nodes[0].parent = self._selected_node
        self._selected_node.attach(nodes[0])  # TODO

        logger.info(
            µ("Attached {node} and {num} descendants to {parent}").format(
                node=nodes[0], num=len(nodes) - 1, parent=self._selected_node
            )
        )
        self.regenerate()

    def node_delete(self) -> None:
        if not self._selected_node:
            return

        parent = self.bnk.get_parent(self._selected_node)
        self.bnk.delete_nodes(self._selected_node)
        logger.info(µ("Deleted {node}", "log").format(node=self._selected_node))

        self._on_node_selected(None, True, parent)
        self.regenerate()

    def node_delete_tree(self) -> None:
        if not self._selected_node:
            return

        g = self.bnk.get_subtree(self._selected_node, True, False)
        parent = self.bnk.get_parent(self._selected_node)
        self.bnk.delete_nodes(*g.nodes)

        logger.info(
            µ("Deleted {node} and {num} children").format(
                node=self._selected_node, num=len(g) - 1
            )
        )

        self._on_node_selected(None, True, parent)
        self.regenerate()

    def update_json_panel(self) -> None:
        value = ""
        if self._selected_node:
            value = self._selected_node.json()
        elif self._selected_section:
            if isinstance(self._selected_section, HIRCSection):
                value = self._selected_section.json_short()
            else:
                value = self._selected_section.json()

        dpg.set_value(self._t("json"), value)
        self._set_json_highlight(False)

    def reset_from_json(self) -> None:
        if self._selected_node:
            self._selected_node.merge(self._backup)
            self.select_node(self._selected_node)
        elif self._selected_section:
            self._selected_section.merge(self._backup)
            self.select_section(self._selected_section)

    def apply_json(self) -> None:
        item = self._selected_node or self._selected_section
        if not item:
            return

        data_str = dpg.get_value(self._t("json"))
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError as e:
            raise ValueError("Failed to parse json") from e

        # Just to verify that the data actually makes sense
        tmp = item.from_dict(data)

        if isinstance(self._selected_section, HIRCSection):
            # Work with the dict so we can avoid replacing the HIRC
            del data["body"]["HIRC"]["objects"]
            tmp = data

        item.merge(tmp)
        self.regenerate()

    def _set_json_highlight(self, highlight: bool) -> None:
        self._set_component_highlight(self._t("json"), highlight)
        self._set_component_highlight(self._t("json_apply"), highlight)

    def _open_create_node_dialog(self) -> None:
        tag = self._t("create_node_dialog")
        if dpg.does_item_exist(tag):
            dpg.show_item(tag)
            dpg.focus_item(tag)
            return

        def on_node_created(node: HIRCNode) -> None:
            logger.info(µ("Created node {node}", "log").format(node=node))
            self.bnk.add_nodes(node)
            self.add_pinned_object(node)

        create_node_dialog(self.bnk, on_node_created, tag=tag)

        dpg.split_frame()
        center_window(tag)

    def _open_settings_dialog(self) -> None:
        tag = self._t("settings_dialog")
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

        tag = self._t(f"node_graph_{node.id}")
        if dpg.does_item_exist(tag):
            dpg.show_item(tag)
            dpg.focus_item(tag)
            return

        def on_graph_node_click(
            sender: str, node: int | HIRCNode, user_data: Any
        ) -> None:
            if node in self.bnk:
                self.jump_to_node(node)

        with dpg.window(
            label=f"{node}",
            width=400,
            height=400,
            on_close=lambda: dpg.delete_item(window),
        ) as window:
            add_graph_widget(self.bnk, node, on_graph_node_click, width=-1, height=-1)

    def _open_new_wwise_event_dialog(self) -> None:
        tag = self._t("new_wwise_event_dialog")
        if dpg.does_item_exist(tag):
            dpg.show_item(tag)
            dpg.focus_item(tag)
            return

        def on_events_created(nodes: list[HIRCNode]) -> None:
            logger.info(µ("Created new event {node}", "log").format(node=nodes[0]))
            self.regenerate()
            self.select_node(nodes[0])

        create_wwise_event_dialog(self.bnk, on_events_created, tag=tag)

        dpg.split_frame()
        center_window(tag)

    def _open_simple_sound_dialog(self) -> None:
        tag = self._t("create_simple_sound_dialog")
        if dpg.does_item_exist(tag):
            dpg.show_item(tag)
            dpg.focus_item(tag)
            return

        def on_sound_created(play_evt: Event, stop_evt: Event) -> None:
            logger.info(
                µ("Created new sound {name} with {count} sounds").format(
                    name=play_evt.get_wwise_name(play_evt), count=len(self._soundfiles)
                )
            )
            self.add_pinned_object(play_evt)
            self.add_pinned_object(stop_evt)
            self.regenerate()
            self.jump_to_node(play_evt)

        create_simple_sound_dialog(self.bnk, on_sound_created, tag=tag)

        dpg.split_frame()
        center_window(tag)

    def _open_batch_sound_builder_dialog(self) -> None:
        tag = self._t("batch_sound_builder_dialog")
        if dpg.does_item_exist(tag):
            dpg.show_item(tag)
            dpg.focus_item(tag)
            return

        def on_batch_created(groups: list[tuple[Event, Event]]) -> None:
            # TODO
            pass

        create_batch_sound_builder_dialog(self.bnk, on_batch_created, tag=tag)

    def _open_boss_track_dialog(self) -> None:
        tag = self._t("create_boss_track_dialog")
        if dpg.does_item_exist(tag):
            dpg.show_item(tag)
            dpg.focus_item(tag)
            return

        def on_boss_track_created(bgm_enemy_type: str, nodes: list[HIRCNode]) -> None:
            logger.info(
                µ("Added boss track {bgm_enemy_type}").format(
                    bgm_enemy_type=bgm_enemy_type
                )
            )
            self.add_pinned_object(nodes[0])
            self.regenerate()
            self.jump_to_node(nodes[0])

        create_boss_track_dialog(self.bnk, on_boss_track_created, tag=tag)

        dpg.split_frame()
        center_window(tag)

    def _open_ambience_track_dialog(self) -> None:
        tag = self._t("create_ambience_track_dialog")
        if dpg.does_item_exist(tag):
            dpg.show_item(tag)
            dpg.focus_item(tag)
            return

        def on_ambience_track_created(nodes: list[HIRCNode]) -> None:
            logger.info(µ("Added ambience track {name}", "log").format(name=nodes[0]))

        create_ambience_track_dialog(self.bnk, on_ambience_track_created, tag=tag)

        dpg.split_frame()
        center_window(tag)

    def _open_calc_hash_dialog(self) -> None:
        tag = self._t("calc_hash_dialog")
        if dpg.does_item_exist(tag):
            dpg.show_item(tag)
            dpg.focus_item(tag)
            return

        calc_hash_dialog(tag=tag)

        dpg.split_frame()
        center_window(tag)

    def _open_mass_transfer_dialog(self) -> None:
        tag = self._t("transfer_events_dialog")
        if dpg.does_item_exist(tag):
            dpg.show_item(tag)
            dpg.focus_item(tag)
            return

        mass_transfer_dialog(tag=tag)

        dpg.split_frame()
        center_window(tag)

    def _open_export_sounds_dialog(self) -> None:
        tag = self._t("convert_wavs_dialog")
        if dpg.does_item_exist(tag):
            dpg.show_item(tag)
            dpg.focus_item(tag)
            return

        export_sounds_dialog(tag=tag)

        dpg.split_frame()
        center_window(tag)

    def _open_convert_wavs_dialog(self) -> None:
        tag = self._t("convert_wavs_dialog")
        if dpg.does_item_exist(tag):
            dpg.show_item(tag)
            dpg.focus_item(tag)
            return

        convert_wavs_dialog(None, tag=tag)

        dpg.split_frame()
        center_window(tag)

    def _open_about_dialog(self) -> None:
        tag = self._t("calc_hash_dialog")
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

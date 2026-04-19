from typing import Any, Callable, TypeVar
from pathlib import Path
from dearpygui import dearpygui as dpg

from yonder.enums import CurveInterpolation
from yonder.types.base_types import RTPCGraphPoint
from yonder.gui import style
from yonder.gui.helpers import shorten_path, GraphCurve
from yonder.gui.localization import µ
from yonder.gui.dialogs.file_dialog import open_multiple_dialog, choose_folder
from .dpg_item import DpgItem


_T = TypeVar("_T")


class add_widget_table(DpgItem):
    """A generic editable table widget for Dear PyGui.

    Renders a list of items as table rows via a caller-supplied ``create_row``
    function. Optionally supports adding, removing, selecting, and clearing
    items. If ``new_item`` is not set, add/remove controls are hidden.

    Row selection is implemented with a narrow dedicated button column rather
    than a span_columns selectable, so the remove button remains clickable.

    Parameters
    ----------
    initial_values : list
        Items to populate the table with on construction.
    create_row : callable
        Called as ``create_row(value, index)`` to build each row's DPG items.
    new_item : callable, optional
        Called as ``new_item(done_callback)`` when the add button is clicked.
        ``done_callback`` accepts the new item to append.
    on_add : callable, optional
        Fired as ``on_add(tag, (index, item, all_items), user_data)``.
    on_remove : callable, optional
        Fired as ``on_remove(tag, (index, item, all_items), user_data)``.
    on_select : callable, optional
        Fired as ``on_select(tag, (index, item, all_items), user_data)``.
    header_row : bool
        Show column headers.
    columns : list of str
        Column header labels.
    label : str, optional
        Text label rendered above the table.
    add_item_label : str
        Label for the add button.
    show_clear : bool
        Show a clear-all button next to the add button.
    parent : int or str
        DPG parent item.
    tag : int or str
        Explicit tag; auto-generated if 0 or None.
    user_data : any
        Passed through to all callbacks.
    """

    def __init__(
        self,
        initial_values: list[_T],
        create_row: Callable[[_T, int], None],
        *,
        new_item: Callable[[Callable[[_T], None]], None] = None,
        on_add: Callable[[str, tuple[int, _T, list[_T]], Any], None] = None,
        on_remove: Callable[[str, tuple[int, _T, list[_T]], Any], None] = None,
        on_select: Callable[[str, tuple[int, _T, list[_T]], Any], None] = None,
        header_row: bool = False,
        columns: list[str] = ("Value",),
        selected_row_color: style.RGBA = style.muted_blue,
        label: str = None,
        add_item_label: str = "+",
        show_clear: bool = False,
        parent: str | int = 0,
        tag: str | int = 0,
        user_data: Any = None,
    ) -> None:
        super().__init__(tag)

        self._values: list[_T] = list(initial_values)
        self._create_row = create_row
        self._new_item = new_item
        self._on_add = on_add
        self._on_remove = on_remove
        self._on_select = on_select
        self._selected_row_color = selected_row_color
        self._add_item_label = add_item_label
        self._show_clear = show_clear
        self._user_data = user_data
        self._selected_idx: int = -1
        # Maps row index -> tag of its select-indicator button
        self._sel_buttons: dict[int, int] = {}

        self._build(header_row, columns, label, parent)
        self.refresh()

    # === Build =========================================================

    def _build(
        self,
        header_row: bool,
        columns: list[str],
        label: str,
        parent: str | int,
    ) -> None:
        if label:
            dpg.add_text(label, parent=parent, tag=self.tag)

        with dpg.child_window(
            border=False, autosize_x=True, auto_resize_y=True, parent=parent
        ):
            with dpg.table(
                header_row=header_row,
                policy=dpg.mvTable_SizingFixedFit,
                borders_outerH=True,
                borders_outerV=True,
                tag=self._t("table"),
            ):
                if self._on_select:
                    # Narrow indicator column; never spans other columns
                    dpg.add_table_column(label="", width_fixed=True, init_width_or_weight=14)
                for col in columns:
                    dpg.add_table_column(
                        label=col, width_stretch=True, init_width_or_weight=100
                    )
                if self._new_item:
                    dpg.add_table_column(label="", width_fixed=True, init_width_or_weight=20)

            dpg.add_group(tag=self._t("footer"))
            dpg.add_spacer(height=3)

    # === Internal row management =======================================

    def refresh(self) -> None:
        self._sel_buttons.clear()
        dpg.delete_item(self._t("table"), children_only=True, slot=1)
        for i, val in enumerate(self._values):
            self._add_row(val, i)
        self._add_footer()

    def _add_row(self, val: _T, idx: int) -> None:
        with dpg.table_row(parent=self._t("table")) as row:
            if self._on_select:
                btn = dpg.add_button(
                    label=" ",
                    callback=self._on_select_clicked,
                    user_data=idx,
                    small=True,
                )
                self._sel_buttons[idx] = btn

            self._create_row(val, idx)

            remove_btn = None
            if self._new_item:
                remove_btn = dpg.add_button(
                    label="x",
                    callback=self._on_remove_clicked,
                    user_data=idx,
                    small=True,
                )

        # Bind a clicked handler to every content child (not the indicator or
        # remove button) so clicking text, inputs, etc. also triggers selection.
        # One registry per row; clicked_handler fires for both static text and
        # input widgets. idx is captured via closure since the handler has no
        # user_data forwarding.
        if self._on_select:
            registry = self._t(f"select_handler_{idx}")
            if not dpg.does_item_exist(registry):
                dpg.add_item_handler_registry(tag=registry)

            # DPG calls handlers as (sender, app_data, user_data) even when no
            # user_data is set, passing None — which overrides a default argument.
            def _make_handler(i: int) -> Callable:
                return lambda s, a, u: self._on_select_clicked(s, True, i)

            dpg.add_item_clicked_handler(
                parent=registry,
                callback=_make_handler(idx),
            )

            for child in dpg.get_item_children(row, slot=1):
                if child in (remove_btn, self._sel_buttons.get(idx)):
                    continue
                try:
                    dpg.bind_item_handler_registry(child, registry)
                except Exception:
                    pass  # item types that don't support handlers; skip silently

    def _add_footer(self) -> None:
        if not self._new_item:
            return
        with dpg.table_row(parent=self._t("table")):
            # When a selector column exists we must advance past it so the
            # add/clear buttons land in a cell that spans the content columns.
            if self._on_select:
                dpg.add_table_cell()
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label=self._add_item_label, callback=self._on_add_clicked
                )
                if self._show_clear:
                    dpg.add_button(
                        label=µ("Clear", "button"), callback=self._on_clear_clicked
                    )

    def _update_indicators(self) -> None:
        """Refresh all row indicator labels to reflect the current selection."""
        for idx, btn in self._sel_buttons.items():
            try:
                dpg.set_item_label(btn, ">" if idx == self._selected_idx else " ")
            except Exception:
                pass  # row may have been deleted mid-refresh

    # === DPG callbacks =================================================

    def _on_remove_clicked(self, sender: int, app_data: Any, idx: int) -> None:
        prev = self._values.pop(idx)
        if idx == self._selected_idx:
            self._selected_idx = -1
        elif idx < self._selected_idx:
            self._selected_idx -= 1
        if self._on_remove:
            self._on_remove(self.tag, (idx, prev, self._values), self._user_data)
        self.refresh()

    def _on_add_item_done(self, result: _T) -> None:
        if not result:
            return
        pos = len(self._values)
        self._values.append(result)
        if self._on_add:
            self._on_add(self.tag, (pos, result, self._values), self._user_data)
        self.refresh()

    def _on_add_clicked(self) -> None:
        self._new_item(self._on_add_item_done)

    def _on_clear_clicked(self) -> None:
        self._values.clear()
        self._selected_idx = -1
        if self._on_remove:
            self._on_remove(self.tag, (0, None, self._values), self._user_data)
        self.refresh()

    def _on_select_clicked(self, sender: int, app_data: Any, idx: int) -> None:
        if self._selected_idx >= 0:
            dpg.unhighlight_table_row(self._t("table"), self._selected_idx)

        dpg.highlight_table_row(self._t("table"), idx, self._selected_row_color)

        self._selected_idx = idx
        self._update_indicators()
        if self._on_select:
            self._on_select(
                self.tag, (idx, self._values[idx], self._values), self._user_data
            )

    # === Public ========================================================

    @property
    def items(self) -> list[_T]:
        """Current item list (read-only copy)."""
        return list(self._values)

    @items.setter
    def items(self, items: list[_T]) -> None:
        self._selected_idx = -1
        self._values = list(items)
        self.refresh()

    def append(self, item: _T, *, fire_callbacks: bool = False) -> None:
        """Append an item and refresh the table."""
        pos = len(self._values)
        self._values.append(item)
        if fire_callbacks and self._on_add:
            self._on_add(self.tag, (pos, item, self._values), self._user_data)
        self.refresh()

    def remove(self, idx: int, *, fire_callbacks: bool = False) -> None:
        """Remove the item at ``idx`` and refresh the table."""
        prev = self._values.pop(idx)
        if idx == self._selected_idx:
            self._selected_idx = -1
        elif idx < self._selected_idx:
            self._selected_idx -= 1
        if fire_callbacks and self._on_remove:
            self._on_remove(self.tag, (idx, prev, self._values), self._user_data)
        self.refresh()

    def clear(self, *, fire_callbacks: bool = False) -> None:
        """Remove all items and refresh the table."""
        self._selected_idx = -1
        self._values.clear()
        if fire_callbacks and self._on_remove:
            self._on_remove(self.tag, (0, None, self._values), self._user_data)
        self.refresh()


# ===========================================================================


class add_filepaths_table(DpgItem):
    """A file/folder path list widget built on ``add_widget_table``.

    Provides an add-files (or add-folders) button that opens a native dialog.
    Each path is shown as a read-only shortened text field.

    Parameters
    ----------
    initial_paths : list of Path
        Paths to pre-populate the table with.
    on_value_changed : callable, optional
        Fired as ``on_value_changed(tag, all_paths, user_data)`` after any add
        or remove.
    folders : bool
        Use folder-picker dialog instead of file-picker.
    label : str
        Text label rendered above the table.
    filetypes : dict, optional
        Passed to ``open_multiple_dialog`` when ``folders`` is False.
    on_select : callable, optional
        Fired as ``on_select(tag, path, user_data)`` when a row is clicked.
    show_clear : bool
        Show a clear-all button.
    parent : int or str
        DPG parent item.
    tag : int or str
        Explicit tag; auto-generated if 0.
    user_data : any
        Passed through to callbacks.
    """

    def __init__(
        self,
        initial_paths: list[Path],
        on_value_changed: Callable[[str, list[Path], Any], None] = None,
        *,
        folders: bool = False,
        label: str = "Files",
        filetypes: dict[str, str] = None,
        on_select: Callable[[str, Path, Any], None] = None,
        show_clear: bool = False,
        parent: str | int = 0,
        tag: str | int = 0,
        user_data: Any = None,
    ) -> None:
        super().__init__(tag)

        self._on_value_changed = on_value_changed
        self._on_select_cb = on_select
        self._folders = folders
        self._label = label
        self._filetypes = filetypes
        self._user_data = user_data

        self._table = add_widget_table(
            initial_paths,
            self._create_row,
            new_item=self._add_item,
            on_add=self._on_add,
            on_remove=self._on_remove,
            on_select=self._on_select if on_select else None,
            add_item_label=µ("+ Add Paths") if folders else µ("+ Add Files"),
            show_clear=show_clear,
            label=label,
            parent=parent,
            tag=self.tag,
            user_data=user_data,
        )

    # === Callbacks =====================================================

    def _add_item(self, done: Callable[[Path], None]) -> None:
        if self._folders:
            res = choose_folder(title=self._label)
        else:
            res = open_multiple_dialog(title=self._label, filetypes=self._filetypes)

        if res:
            if isinstance(res, list):
                for p in res:
                    done(Path(p))
            else:
                done(Path(res))

    def _create_row(self, path: Path, idx: int) -> None:
        dpg.add_input_text(
            default_value=shorten_path(path, maxlen=40),
            enabled=False,
            readonly=True,
            width=-1,
        )

    def _on_add(
        self, sender: str, info: tuple[int, Path, list[Path]], cb_user_data: Any
    ) -> None:
        if self._on_value_changed:
            self._on_value_changed(self.tag, info[2], self._user_data)

    def _on_remove(
        self, sender: str, info: tuple[int, Path, list[Path]], cb_user_data: Any
    ) -> None:
        if self._on_value_changed:
            self._on_value_changed(self.tag, info[2], self._user_data)

    def _on_select(
        self, sender: str, info: tuple[int, Path, list[Path]], cb_user_data: Any
    ) -> None:
        if self._on_select_cb:
            self._on_select_cb(self.tag, info[1], self._user_data)

    # === Public ========================================================

    @property
    def paths(self) -> list[Path]:
        return self._table.items

    @paths.setter
    def paths(self, items: list[Path]) -> None:
        self._table.items = items

    def append(self, path: Path, *, fire_callbacks: bool = False) -> None:
        self._table.append(path, fire_callbacks=fire_callbacks)

    def remove(self, idx: int, *, fire_callbacks: bool = False) -> None:
        self._table.remove(idx, fire_callbacks=fire_callbacks)

    def clear(self, *, fire_callbacks: bool = False) -> None:
        self._table.clear(fire_callbacks=fire_callbacks)


# ===========================================================================


class add_player_table(DpgItem):
    """A track list widget where each row embeds a full ``add_wav_player``.

    Supports per-track loop markers, trim markers, and user markers.
    Player instances are accessible via ``players``.

    Parameters
    ----------
    initial_tracks : list of Path, optional
        Audio files to pre-populate the table with.
    on_filepaths_changed : callable, optional
        Fired as ``on_filepaths_changed(tag, (paths, loop_info, trims,
        markers), user_data)`` after any track change.
    label : str
        Text label rendered above the table.
    add_item_label : str
        Label for the add button.
    get_row_label : callable, optional
        Called as ``get_row_label(index)`` to produce a display name per row.
    on_loop_changed : callable, optional
        Fired as ``on_loop_changed(tag, (index, loop_info), user_data)``.
    on_trim_changed : callable, optional
        Fired as ``on_trim_changed(tag, (index, trim_info), user_data)``.
    on_user_marker_changed : callable, optional
        Fired as ``on_user_marker_changed(tag, (index, markers), user_data)``.
    initial_user_markers : list of (str, float), optional
        Markers pre-loaded into each player on track add.
    show_clear : bool
        Show a clear-all button.
    parent : int or str
        DPG parent item.
    tag : int or str
        Explicit tag; auto-generated if 0.
    user_data : any
        Passed through to callbacks.
    """

    def __init__(
        self,
        initial_tracks: list[Path] = None,
        on_filepaths_changed: Callable[
            [str, tuple[list[Path], list, list, list], Any], None
        ] = None,
        *,
        label: str = "Tracks",
        add_item_label: str = "+ Add Track",
        get_row_label: Callable[[int], str] = None,
        on_loop_changed: Callable[
            [str, tuple[int, tuple[float, float, bool]], Any], None
        ] = None,
        on_trim_changed: Callable[
            [str, tuple[int, tuple[float, float]], Any], None
        ] = None,
        on_user_marker_changed: Callable[[str, tuple[int, list], Any], None] = None,
        initial_user_markers: list[tuple[str, float]] = None,
        show_clear: bool = False,
        parent: str | int = 0,
        tag: str | int = 0,
        user_data: Any = None,
    ) -> None:
        from yonder.gui.dialogs.file_dialog import open_file_dialog
        from .wav_player import add_wav_player as _wav_player

        self._wav_player_cls = _wav_player
        self._open_file_dialog = open_file_dialog

        super().__init__(tag)

        self._on_filepaths_changed = on_filepaths_changed
        self._on_loop_changed = on_loop_changed
        self._on_trim_changed = on_trim_changed
        self._on_user_marker_changed = on_user_marker_changed
        self._initial_user_markers = list(initial_user_markers or [])
        self._get_row_label = get_row_label or (
            lambda i: µ("Track #{idx}").format(idx=i)
        )
        self._user_data = user_data

        self.players: list = []  # add_wav_player instances, one per track

        self._table = add_widget_table(
            list(initial_tracks or []),
            self._create_row,
            new_item=self._new_sound,
            on_add=self._on_track_added,
            on_remove=self._on_track_removed,
            add_item_label=add_item_label,
            show_clear=show_clear,
            label=label,
            parent=parent,
            tag=self.tag,
        )

    # === Helpers =======================================================

    def _collect_state(self) -> tuple:
        paths = self._table.items
        loop_info = [p.get_loop_state() for p in self.players]
        trims = [p.get_trims() for p in self.players]
        markers = [p.get_user_marker_pos() for p in self.players]
        return (paths, loop_info, trims, markers)

    # === DPG callbacks =================================================

    def _new_sound(self, done: Callable[[Path], None]) -> None:
        ret = self._open_file_dialog(
            title=µ("Select Audio"),
            filetypes={µ("Audio (.wem, .wav)", "filetypes"): ["*.wem", "*.wav"]},
        )
        if ret:
            done(Path(ret))

    def _on_loop_edit(self, sender: str, new_loop: tuple, idx: int) -> None:
        if self._on_loop_changed:
            self._on_loop_changed(self.tag, (idx, new_loop), self._user_data)

    def _on_trim_edit(self, sender: str, new_trim: tuple, idx: int) -> None:
        if self._on_trim_changed:
            self._on_trim_changed(self.tag, (idx, new_trim), self._user_data)

    def _on_user_marker_edit(self, sender: str, new_marker: tuple, idx: int) -> None:
        if self._on_user_marker_changed:
            markers = self.players[idx].get_user_marker_pos()
            self._on_user_marker_changed(self.tag, (idx, markers), self._user_data)

    def _on_track_added(self, sender: str, info: tuple, cb_user_data: Any) -> None:
        if self._on_filepaths_changed:
            self._on_filepaths_changed(self.tag, self._collect_state(), self._user_data)

    def _on_track_removed(self, sender: str, info: tuple, cb_user_data: Any) -> None:
        idx = info[0]
        self.players.pop(idx)
        if self._on_filepaths_changed:
            self._on_filepaths_changed(self.tag, self._collect_state(), self._user_data)

    def _on_path_changed(self, sender: str, new_path: Path, idx: int) -> None:
        if self._on_filepaths_changed:
            self._on_filepaths_changed(self.tag, self._collect_state(), self._user_data)

    def _create_row(self, path: Path, idx: int) -> None:
        with dpg.tree_node(label=path.stem):
            player = self._wav_player_cls(
                path,
                label=f" <{self._get_row_label(idx)}>",
                on_file_changed=self._on_path_changed,
                loop_markers_enabled=bool(self._on_loop_changed),
                on_loop_changed=self._on_loop_edit,
                trim_enabled=bool(self._on_trim_changed),
                on_trim_marker_changed=self._on_trim_edit,
                user_markers_enabled=bool(self._on_user_marker_changed),
                user_markers=list(self._initial_user_markers),
                on_user_markers_changed=self._on_user_marker_edit,
                show_filepath=True,
                user_data=idx,
            )
            self.players.insert(idx, player)

    # === Public ========================================================

    @property
    def audiofiles(self) -> list[Path]:
        return self._table.items

    @audiofiles.setter
    def audiofiles(self, items: list[Path]) -> None:
        self._table.items = items

    def append(self, path: Path, *, fire_callbacks: bool = False) -> None:
        self._table.append(path, fire_callbacks=fire_callbacks)

    def remove(self, idx: int, *, fire_callbacks: bool = False) -> None:
        self._table.remove(idx, fire_callbacks=fire_callbacks)

    def clear(self, *, fire_callbacks: bool = False) -> None:
        self._table.clear(fire_callbacks=fire_callbacks)


# ===========================================================================


class add_player_table_compact(DpgItem):
    """A compact track list with a single shared ``add_wav_player`` below.

    Selecting a row loads that track into the shared player without starting
    playback. Does not support loop markers, trims, or user markers.

    Parameters
    ----------
    initial_tracks : list of Path, optional
        Audio files to pre-populate the table with.
    on_filepaths_changed : callable, optional
        Fired as ``on_filepaths_changed(tag, paths, user_data)`` after any
        track list change.
    label : str
        Text label rendered above the table.
    add_item_label : str
        Label for the add button.
    get_row_label : callable, optional
        Called as ``get_row_label(index)`` to produce a display name per row.
    show_clear : bool
        Show a clear-all button.
    parent : int or str
        DPG parent item.
    tag : int or str
        Explicit tag; auto-generated if 0.
    user_data : any
        Passed through to callbacks.
    """

    def __init__(
        self,
        initial_tracks: list[Path] = None,
        on_filepaths_changed: Callable[[str, list[Path], Any], None] = None,
        *,
        label: str = "Tracks",
        add_item_label: str = "+ Add Track",
        get_row_label: Callable[[int], str] = None,
        show_clear: bool = False,
        parent: str | int = 0,
        tag: str | int = 0,
        user_data: Any = None,
    ) -> None:
        from .wav_player import add_wav_player

        super().__init__(tag)

        self._on_filepaths_changed = on_filepaths_changed
        self._get_row_label = get_row_label or (
            lambda i: µ("Track #{idx}").format(idx=i)
        )
        self._user_data = user_data
        self.player = None  # single shared add_wav_player instance

        with dpg.group(parent=parent):
            self._table = add_widget_table(
                list(initial_tracks or []),
                self._create_row,
                new_item=self._new_sound,
                on_add=self._on_track_added,
                on_remove=self._on_track_removed,
                on_select=self._on_track_selected,
                add_item_label=add_item_label,
                show_clear=show_clear,
                label=label,
                tag=self.tag,
            )
            # Shared player — created empty, loaded on row selection
            self.player = add_wav_player(None, allow_change_file=False)

    # === DPG callbacks =================================================

    def _new_sound(self, done: Callable[[Path], None]) -> None:
        from yonder.gui.dialogs.file_dialog import open_multiple_dialog

        ret = open_multiple_dialog(
            title=µ("Select Audio"),
            filetypes={µ("Audio (.wem, .wav)", "filetypes"): ["*.wem", "*.wav"]},
        )
        if ret:
            for f in ret:
                done(Path(f))

    def _create_row(self, path: Path, idx: int) -> None:
        dpg.add_input_text(
            default_value=shorten_path(path, maxlen=40),
            enabled=False,
            readonly=True,
            width=-1,
        )

    def _on_track_selected(self, sender: str, info: tuple, cb_user_data: Any) -> None:
        _, path, _ = info
        self.player.set_file(path)

    def _on_track_added(self, sender: str, info: tuple, cb_user_data: Any) -> None:
        if self._on_filepaths_changed:
            self._on_filepaths_changed(self.tag, self._table.items, self._user_data)

    def _on_track_removed(self, sender: str, info: tuple, cb_user_data: Any) -> None:
        if self._on_filepaths_changed:
            self._on_filepaths_changed(self.tag, self._table.items, self._user_data)

    # === Public ========================================================

    @property
    def audiofiles(self) -> list[Path]:
        return self._table.items

    @audiofiles.setter
    def audiofiles(self, items: list[Path]) -> None:
        self._table.items = items

    def append(self, path: Path, *, fire_callbacks: bool = False) -> None:
        self._table.append(path, fire_callbacks=fire_callbacks)

    def remove(self, idx: int, *, fire_callbacks: bool = False) -> None:
        self._table.remove(idx, fire_callbacks=fire_callbacks)

    def clear(self, *, fire_callbacks: bool = False) -> None:
        self._table.clear(fire_callbacks=fire_callbacks)


# ===========================================================================


class add_curves_table(DpgItem):
    """A curve list widget where each row embeds an ``add_interpolation_curve``.

    Optionally shows a curve-type combo per row. The outer group owns the
    tag; the inner table uses a derived tag.

    Parameters
    ----------
    initial_curves : list of GraphCurve, optional
        Curves to pre-populate the table with.
    curve_types : list of str, optional
        Available type names shown in the per-row combo.
    on_curves_changed : callable, optional
        Fired as ``on_curves_changed(tag, all_curves, user_data)``.
    label : str
        Text label rendered above the table.
    add_item_label : str
        Label for the add button.
    curve_type_label : str
        DPG label for the curve-type combo.
    show_clear : bool
        Show a clear-all button.
    parent : int or str
        DPG parent item.
    tag : int or str
        Explicit tag for the outer group; auto-generated if 0.
    user_data : any
        Passed through to callbacks.
    """

    def __init__(
        self,
        initial_curves: list[GraphCurve] = None,
        curve_types: list[str] = None,
        on_curves_changed: Callable[[str, list[GraphCurve], Any], None] = None,
        *,
        label: str = "Curves",
        add_item_label: str = "+ Add Curve",
        curve_type_label: str = "Type",
        show_clear: bool = False,
        parent: str | int = 0,
        tag: str | int = 0,
        user_data: Any = None,
    ) -> None:
        super().__init__(tag)

        self._curves: list[GraphCurve] = list(initial_curves or [])
        self._curve_types = curve_types
        self._curve_type_label = curve_type_label
        self._on_curves_changed = on_curves_changed
        self._user_data = user_data

        self._table = add_widget_table(
            self._curves,
            self._create_row,
            new_item=self._new_curve,
            on_add=self._on_add_curve,
            on_remove=self._on_remove_curve,
            add_item_label=add_item_label,
            show_clear=show_clear,
            label=label,
            tag=self.tag,
        )

    # === DPG callbacks =================================================

    def _on_curve_type_changed(self, sender: str, curve_type: str, idx: int) -> None:
        self._curves[idx].curve_type = curve_type
        if self._on_curves_changed:
            self._on_curves_changed(self.tag, self._curves, self._user_data)

    def _on_curve_changed(self, sender: str, curve: GraphCurve, idx: int) -> None:
        self._curves[idx] = curve
        if self._on_curves_changed:
            self._on_curves_changed(self.tag, self._curves, self._user_data)

    def _on_add_curve(self, sender: str, info: tuple, cb_user_data: Any) -> None:
        self._curves.clear()
        self._curves.extend(info[2])
        if self._on_curves_changed:
            self._on_curves_changed(self.tag, self._curves, self._user_data)

    def _on_remove_curve(self, sender: str, info: tuple, cb_user_data: Any) -> None:
        self._curves.clear()
        self._curves.extend(info[2])
        if self._on_curves_changed:
            self._on_curves_changed(self.tag, self._curves, self._user_data)

    def _new_curve(self, done: Callable[[GraphCurve], None]) -> None:
        done(
            GraphCurve(
                self._curve_types[0] if self._curve_types else None,
                [
                    RTPCGraphPoint(0.0, 0.0, CurveInterpolation.Constant),
                    RTPCGraphPoint(1.0, 1.0, CurveInterpolation.Constant),
                ],
            )
        )

    def _create_row(self, curve: GraphCurve, idx: int) -> None:
        from .interpolation_curve import add_interpolation_curve

        with dpg.tree_node(label=f"Curve #{idx}"):
            with dpg.group(horizontal=True):
                if self._curve_types:
                    dpg.add_combo(
                        self._curve_types,
                        default_value=curve.curve_type,
                        label=self._curve_type_label,
                        callback=self._on_curve_type_changed,
                        user_data=idx,
                    )
            add_interpolation_curve(curve, self._on_curve_changed, user_data=idx)

    # === Public ========================================================

    @property
    def curves(self) -> list[GraphCurve]:
        return list(self._curves)

    @curves.setter
    def curves(self, items: list[GraphCurve]) -> None:
        self._table.items = items

    def append(self, curve: GraphCurve, *, fire_callbacks: bool = False) -> None:
        self._table.append(curve, fire_callbacks=fire_callbacks)

    def remove(self, idx: int, *, fire_callbacks: bool = False) -> None:
        self._table.remove(idx, fire_callbacks=fire_callbacks)

    def clear(self, *, fire_callbacks: bool = False) -> None:
        self._table.clear(fire_callbacks=fire_callbacks)
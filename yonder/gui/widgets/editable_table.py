from typing import Any, Callable, TypeVar
from pathlib import Path
from dearpygui import dearpygui as dpg

from yonder.enums import CurveInterpolation
from yonder.types.base_types import RTPCGraphPoint
from yonder.gui.helpers import shorten_path, GraphCurve
from yonder.gui.dialogs.file_dialog import open_multiple_dialog, choose_folder


_T = TypeVar("_T")


def add_widget_table(
    initial_values: list[_T],
    create_row: Callable[[_T, int], None],
    *,
    new_item: Callable[[Callable[[list[_T]], None]], None] = None,
    on_add: Callable[[str, tuple[int, _T, list[_T]], Any], None] = None,
    on_remove: Callable[[str, tuple[int, _T, list[_T]], Any], None] = None,
    on_select: Callable[[str, tuple[int, _T, list[_T]], Any], None] = None,
    header_row: bool = False,
    columns: list[str] = ("Value",),
    label: str = None,
    add_item_label: str = "+",
    show_clear: bool = False,
    parent: str | int = 0,
    tag: str | int = 0,
    user_data: Any = None,
) -> str:
    # NOTE: if new_item is not set, both adding and removing items is disabled

    if tag in (None, 0, ""):
        tag = dpg.generate_uuid()

    current_values: list[_T] = list(initial_values)

    def refresh() -> None:
        dpg.delete_item(tag, children_only=True, slot=1)
        for i, val in enumerate(current_values):
            add_row(val, i)
        add_footer()

    def on_remove_clicked(sender: int, app_data: Any, idx: int) -> None:
        prev = current_values.pop(idx)
        if on_remove:
            on_remove(tag, (idx, prev, current_values), user_data)
        refresh()

    def on_add_item_done(result: list[_T]) -> None:
        if not result:
            return

        pos = len(current_values)
        current_values.append(result)
        if on_add:
            on_add(tag, (pos, result, current_values), user_data)
        refresh()

    def on_add_clicked() -> None:
        new_item(on_add_item_done)

    def on_clear_clicked() -> None:
        current_values.clear()
        if on_remove:
            on_remove(tag, (0, None, current_values), user_data)
        refresh()

    def on_row_selected(sender: str, selected: bool, idx: int) -> None:
        if selected:
            on_select(tag, (idx, current_values[idx], current_values), user_data)

    def add_row(val: _T, idx: int) -> None:
        with dpg.table_row(parent=tag):
            if on_select:
                dpg.add_selectable(span_columns=True, callback=on_row_selected, user_data=idx)

            create_row(val, idx)

            if new_item:
                dpg.add_button(label="x", callback=on_remove_clicked, user_data=idx)

    def add_footer() -> None:
        if new_item:
            with dpg.table_row(parent=tag):
                with dpg.group(horizontal=True):
                    dpg.add_button(label=add_item_label, callback=on_add_clicked)
                    if show_clear:
                        dpg.add_button(label="Clear", callback=on_clear_clicked)

    # The actual widgets
    if label:
        dpg.add_text(label)

    with dpg.child_window(border=False, autosize_x=True, auto_resize_y=True, parent=parent):
        with dpg.table(
            header_row=header_row,
            policy=dpg.mvTable_SizingFixedFit,
            borders_outerH=True,
            borders_outerV=True,
            resizable=True,
            tag=tag,
        ):
            if on_select:
                dpg.add_table_column(label="")

            for col in columns:
                dpg.add_table_column(
                    label=col, width_stretch=True, init_width_or_weight=100
                )
            
            if new_item:
                dpg.add_table_column(label="")

        dpg.add_group(tag=f"{tag}_footer")
        dpg.add_spacer(height=3)

    refresh()
    return tag


def add_filepaths_table(
    initial_paths: list[Path],
    on_value_changed: Callable[[str, list[Path], Any], None],
    *,
    folders: bool = False,
    label: str = "Files",
    filetypes: dict[str, str] = None,
    on_select: Callable[[str, Path, Any], None] = None,
    show_clear: bool = False,
    parent: str | int = 0,
    tag: str | int = 0,
    user_data: Any = None,
) -> str:
    if not tag:
        tag = dpg.generate_uuid()

    def add_item(done: Callable[[Path], None]) -> None:
        if folders:
            res = choose_folder(title=label)
        else:
            res = open_multiple_dialog(title=label, filetypes=filetypes)

        if res:
            if isinstance(res, list):
                for p in res:
                    done(Path(p))
            else:
                done(Path(res))

    def create_row(path: Path, idx: int):
        txt = dpg.add_input_text(
            default_value=shorten_path(path, maxlen=40),
            enabled=False,
            readonly=True,
            width=-1,
        )
        return (txt,)

    def _on_add(sender: str, info: tuple[int, Path, list[Path]], user_data: Any) -> None:
        if on_value_changed:
            on_value_changed(tag, info[2], user_data)

    def _on_remove(sender: str, info: tuple[int, Path, list[Path]], user_data: Any) -> None:
        if on_value_changed:
            on_value_changed(tag, info[2], user_data)

    def _on_select(sender: str, info: tuple[int, Path, list[Path]], user_data: Any) -> None:
        if on_select:
            on_select(tag, info[1], user_data)

    return add_widget_table(
        initial_paths,
        create_row,
        new_item=add_item,
        on_add=_on_add,
        on_remove=_on_remove,
        on_select=_on_select,
        add_item_label="+ Add Paths" if folders else "+ Add Files",
        show_clear=show_clear,
        label=label,
        parent=parent,
        tag=tag,
        user_data=user_data,
    )


def add_player_table(
    initial_tracks: list[Path] = None,
    on_filepaths_changed: Callable[
        [
            str,
            tuple[
                list[Path],  # filepaths
                list[tuple[float, float, bool]],  # loop info
                list[tuple[float, float]],  # trims
                list[tuple[str, float]],  # user markers
            ],
            Any,
        ],
        None,
    ] = None,
    *,
    label: str = "Tracks",
    add_item_label: str = "+ Add Track",
    get_row_label: Callable[[int], str] = None,
    on_loop_changed: Callable[
        [str, tuple[int, tuple[float, float, bool]], Any], None
    ] = None,
    on_trim_changed: Callable[[str, tuple[int, tuple[float, float]], Any], None] = None,
    on_user_marker_changed: Callable[
        [str, tuple[int, tuple[str, float]], Any], None
    ] = None,
    initial_user_markers: list[tuple[str, float]] = None,
    show_clear: bool = False,
    parent: str | int = 0,
    tag: str | int = 0,
    user_data: Any = None,
) -> str:
    if not tag:
        tag = dpg.generate_uuid()

    from yonder.gui.dialogs.file_dialog import open_file_dialog
    from .wav_player import add_wav_player

    tracks: list[Path] = list(initial_tracks) if initial_tracks else []
    loop_info: list[tuple[float, float, bool]] = []
    user_markers: list[list[tuple[str, float]]] = []
    trims: list[tuple[float, float]] = []

    if not get_row_label:
        get_row_label = lambda i: f"Track #{i}"

    def new_sound(done: Callable[[Path], None]) -> None:
        ret = open_file_dialog(
            title="Select Audio",
            filetypes={"Audio (.wem, .wav)": ["*.wem", "*.wav"]},
        )
        if ret:
            done(Path(ret))

    def on_loop_edit(
        sender: str, new_loop_info: tuple[float, float, bool], idx: int
    ) -> None:
        loop_info[idx] = new_loop_info
        on_loop_changed(tag, (idx, new_loop_info), user_data)

    def on_trim_edit(sender: str, new_trim_info: tuple[float, float], idx: int) -> None:
        trims[idx] = new_trim_info
        on_trim_changed(tag, (idx, new_trim_info), user_data)

    def on_user_marker_edit(
        sender: str, new_marker_info: tuple[str, float], idx: int
    ) -> None:
        markers = user_markers[idx]
        for i, m in enumerate(markers):
            if m[0] == new_marker_info[0]:
                markers[i] = new_marker_info
                break

        on_user_marker_changed(tag, (idx, markers), user_data)

    def on_track_added(
        sender: str, info: tuple[int, Path, list[Path]], cb_user_data: Any
    ) -> None:
        nonlocal tracks

        pos, _, all_items = info
        tracks[:] = all_items[:]

        loop_info.insert(pos, (0.0, 1.0, True))
        user_markers.insert(pos, list(initial_user_markers or []))
        trims.insert(pos, (0.0, 0.0))

        data = (all_items, loop_info, trims, user_markers)
        on_filepaths_changed(sender, data, user_data)

    def on_track_removed(
        sender: str, info: tuple[int, Path, list[Path]], cb_user_data: Any
    ) -> None:
        pos, _, all_items = info
        tracks.pop(pos)

        loop_info.pop(pos)
        user_markers.pop(pos)
        trims.pop(pos)

        data = (all_items, loop_info, trims, user_markers)
        on_filepaths_changed(sender, data, user_data)

    def create_row(path: Path, idx: int) -> None:
        with dpg.tree_node(label=path.stem):
            add_wav_player(
                path,
                label=f" <{get_row_label(idx)}>",
                on_file_changed=on_path_changed,
                loop_markers_enabled=bool(on_loop_changed),
                on_loop_changed=on_loop_edit,
                trim_enabled=bool(on_trim_changed),
                on_trim_marker_changed=on_trim_edit,
                user_markers_enabled=bool(on_user_marker_changed),
                user_markers=list(initial_user_markers or []),
                on_user_markers_changed=on_user_marker_edit,
                show_filepath=True,
                user_data=idx,
            )

    def on_path_changed(sender: str, new_path: Path, idx: int) -> None:
        tracks[idx] = new_path
        data = (tracks, loop_info, trims, user_markers)
        on_filepaths_changed(sender, data, user_data)

    return add_widget_table(
        [],
        create_row,
        new_item=new_sound,
        on_add=on_track_added,
        on_remove=on_track_removed,
        add_item_label=add_item_label,
        show_clear=show_clear,
        label=label,
        parent=parent,
        tag=tag,
    )


def add_curves_table(
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
) -> str:
    from .interpolation_curve import add_interpolation_curve

    if not tag:
        tag = dpg.generate_uuid()

    curves: list[GraphCurve] = list(initial_curves or [])

    def on_curve_type_changed(sender: str, curve_type: str, curve_idx: int) -> None:
        curves[curve_idx].curve_type = curve_type

        if on_curves_changed:
            on_curves_changed(tag, curves, user_data)

    def on_curve_changed(sender: str, curve: GraphCurve, curve_idx: int) -> None:
        curves[curve_idx] = curve

        if on_curves_changed:
            on_curves_changed(tag, curves, user_data)

    def on_add_curve(
        sender: str,
        info: tuple[int, GraphCurve, list[GraphCurve]],
        cb_user_data: Any,
    ) -> None:
        curves.clear()
        curves.extend(info[2])

        if on_curves_changed:
            on_curves_changed(tag, curves, user_data)

    def on_remove_curve(
        sender: str,
        info: tuple[int, GraphCurve, list[GraphCurve]],
        cb_user_data: Any,
    ) -> None:
        curves.clear()
        curves.extend(info[2])

        if on_curves_changed:
            on_curves_changed(tag, curves, user_data)

    def new_curve(done: Callable[[GraphCurve], None]) -> None:
        done(
            GraphCurve(
                curve_types[0] if curve_types else None,
                [
                    RTPCGraphPoint(0.0, 0.0, CurveInterpolation.Constant),
                    RTPCGraphPoint(1.0, 1.0, CurveInterpolation.Constant),
                ],
            )
        )

    def create_row(curve: GraphCurve, idx: int):
        with dpg.tree_node(label=f"Curve #{idx}"):
            with dpg.group(horizontal=True):
                if curve_types:
                    dpg.add_combo(
                        curve_types,
                        default_value=curve.curve_type,
                        label=curve_type_label,
                        callback=on_curve_type_changed,
                        user_data=idx,
                    )
            add_interpolation_curve(curve, on_curve_changed, user_data=idx)

    with dpg.group(tag=tag, parent=parent):
        if label:
            dpg.add_text(label)

        add_widget_table(
            curves,
            create_row,
            new_item=new_curve,
            on_add=on_add_curve,
            on_remove=on_remove_curve,
            add_item_label=add_item_label,
            show_clear=show_clear,
            tag=tag,
        )

    return tag

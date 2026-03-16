from typing import Any, Callable, TypeVar
from pathlib import Path
from dearpygui import dearpygui as dpg

from yonder.gui.helpers import shorten_path
from yonder.gui.dialogs.file_dialog import open_multiple_dialog, choose_folder


_T = TypeVar("_T")


def add_widget_table(
    initial_values: list[_T],
    new_item: Callable[[], _T | tuple[_T]],
    create_row: Callable[[_T, int], None],
    on_items_changed: Callable[[str, list[_T], Any], None],
    *,
    add_item_label: str = "+",
    label: str = None,
    tag: str | int = 0,
    user_data: Any = None,
) -> str:
    if tag in (None, 0, ""):
        tag = dpg.generate_uuid()

    current_values: list[_T] = list(initial_values)

    def refresh() -> None:
        dpg.delete_item(tag, children_only=True, slot=1)
        for i, val in enumerate(current_values):
            add_row(val, i)
        add_footer()

    def on_remove_clicked(sender: int, app_data: Any, idx: int) -> None:
        current_values.pop(idx)
        refresh()
        on_items_changed(tag, list(current_values), user_data)

    def on_add_clicked() -> None:
        result = new_item()
        if not result:
            return

        if not isinstance(result, list):
            result = [result]

        current_values.extend(result)
        refresh()
        on_items_changed(tag, list(current_values), user_data)

    def add_row(val: _T, idx: int) -> None:
        with dpg.table_row(parent=tag):
            create_row(val, idx)
            dpg.add_button(label="-", callback=on_remove_clicked, user_data=idx)

    def add_footer() -> None:
        with dpg.table_row(parent=tag):
            dpg.add_button(label=add_item_label, callback=on_add_clicked)

    # The actual widgets
    if label:
        dpg.add_text(label)

    with dpg.table(
        header_row=False,
        policy=dpg.mvTable_SizingFixedFit,
        borders_outerH=True,
        borders_outerV=True,
        tag=tag,
    ):
        dpg.add_table_column(
            label="Value", width_stretch=True, init_width_or_weight=100
        )
        dpg.add_table_column(label="")

        refresh()

    return tag


def add_filepaths_table(
    initial_paths: list[Path],
    on_value_changed: Callable[[str, list[Path], Any], None],
    *,
    folders: bool = False,
    label: str = "Files",
    filetypes: dict[str, str] = None,
    tag: str | int = 0,
    user_data: Any = None,
) -> str:
    def add_item() -> Path:
        if folders:
            res = choose_folder(title=label)
        else:
            res = open_multiple_dialog(title=label, filetypes=filetypes)

        if res:
            if isinstance(res, list):
                return [Path(p) for p in res]
            return Path(res)

        return None

    def create_row(path: Path, idx: int):
        txt = dpg.add_input_text(
            default_value=shorten_path(path, maxlen=40),
            enabled=False,
            readonly=True,
            width=-1,
        )
        return (txt, )

    return add_widget_table(
        initial_paths,
        add_item,
        create_row,
        on_value_changed,
        add_item_label="+ Add Paths" if folders else "+ Add Files",
        label=label,
        tag=tag,
        user_data=user_data,
    )


def add_player_table(
    initial_tracks: list[Path] = None,
    on_items_changed: Callable[[str, list[Path], Any], None] = None,
    *,
    label: str = "Tracks",
    add_item_label: str = "+ Add Track",
    get_row_label: Callable[[int], str] = None,
    tag: str | int = 0,
    user_data: Any = None,
) -> str:
    from yonder.gui.dialogs.file_dialog import open_file_dialog
    from .player_widget import add_wav_player

    tracks: list[Path] = list(initial_tracks) if initial_tracks else []
    if not get_row_label:
        get_row_label = lambda i: f"Track #{i}"

    def add_sound() -> Path:
        ret = open_file_dialog(
            title="Select Audio",
            filetypes={"Audio (.wem, .wav)": ["*.wem", "*.wav"]},
        )
        if ret:
            return Path(ret)

    def create_row(path: Path, idx: int) -> None:
        add_wav_player(
            path,
            label=get_row_label(idx),
            on_file_changed=on_path_changed,
            show_filepath=True,
            user_data=idx,
        )

    def on_path_changed(sender: str, new_path: Path, idx: int) -> None:
        tracks[idx] = new_path

    return add_widget_table(
        [],
        add_sound,
        create_row,
        on_items_changed=on_items_changed,
        add_item_label=add_item_label,
        label=label,
        tag=tag,
        user_data=user_data,
    )


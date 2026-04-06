from typing import Any, Callable
from pathlib import Path
from dearpygui import dearpygui as dpg

from yonder.gui import style
from yonder.gui.widgets import add_wav_player


def edit_markers_dialog(
    sound: Path,
    *,
    title: str = "Edit Loop Markers",
    accept_on_okay: bool = False,
    loop_markers_enabled: bool = False,
    loop_start: float = 1.0,
    loop_end: float = -1.0,
    on_loop_changed: Callable[[str, tuple[float, float, bool], Any], None] = None,
    user_markers_enabled: bool = False,
    user_markers: dict[int | str, float] = None,
    on_user_marker_changed: Callable[[str, dict[int | str, float], Any], None] = None,
    trim_enabled: bool = False,
    begin_trim: float = 0.0,
    end_trim: float = 0.0,
    on_trim_marker_changed: Callable[[str, tuple[float, float], Any], None] = None,
    tag: str = None,
    user_data: Any = None,
) -> str:
    if not tag:
        tag = dpg.generate_uuid()

    if not user_markers:
        user_markers = {}

    loop_info = (loop_start, loop_end, True)
    trims: tuple[float, float] = (begin_trim, end_trim)

    def dlg_on_loop_changed(
        sender: str, info: tuple[float, float, bool], cb_user_data: Any
    ) -> None:
        nonlocal loop_info
        if accept_on_okay:
            loop_info = info
        else:
            on_loop_changed(tag, info, user_data)

    def dlg_on_user_marker_changed(
        sender: str, info: tuple[int, float], cb_user_data: Any
    ) -> None:
        if accept_on_okay:
            user_markers[info[0]] = info[1]
        else:
            on_user_marker_changed(tag, info, user_data)

    def dlg_on_trim_marker_changed(
        sender: str, info: tuple[float, float], cb_user_data: Any
    ) -> None:
        nonlocal trims
        if accept_on_okay:
            trims = info
        else:
            on_trim_marker_changed(tag, info, user_data)

    def show_message(
        msg: str = None, color: tuple[int, int, int, int] = style.red
    ) -> None:
        if not msg:
            dpg.hide_item(f"{tag}_notification")
            return

        dpg.configure_item(
            f"{tag}_notification",
            default_value=msg,
            color=color,
            show=True,
        )

    def on_okay():
        if loop_markers_enabled and on_loop_changed:
            on_loop_changed(tag, loop_info, user_data)

        if user_markers_enabled and on_user_marker_changed:
            on_user_marker_changed(tag, user_markers, user_data)

        if trim_enabled and on_trim_marker_changed:
            on_trim_marker_changed(tag, trims, user_data)

        dpg.delete_item(window)

    with dpg.window(
        label=title,
        width=700,
        height=350,
        autosize=False,
        no_saved_settings=True,
        tag=tag,
        on_close=lambda: dpg.delete_item(window),
    ) as window:
        dpg.add_spacer(height=10)

        add_wav_player(
            sound,
            allow_change_file=False,
            edit_markers_inplace=True,
            loop_markers_enabled=loop_markers_enabled,
            loop_start=loop_start,
            loop_end=loop_end,
            on_loop_changed=dlg_on_loop_changed,
            user_markers_enabled=user_markers_enabled,
            user_markers=user_markers,
            on_user_markers_changed=dlg_on_user_marker_changed,
            trim_enabled=trim_enabled,
            begin_trim=begin_trim,
            end_trim=end_trim,
            on_trim_marker_changed=dlg_on_trim_marker_changed,
            max_points=10000,
            width=-1,
            height=-60,
        )

        dpg.add_separator()
        dpg.add_text(show=False, tag=f"{tag}_notification", color=style.red)

        if accept_on_okay:
            with dpg.group(horizontal=True):
                dpg.add_button(label="Okay", callback=on_okay, tag=f"{tag}_button_okay")
                dpg.add_button(
                    label="Cancel",
                    callback=lambda: dpg.delete_item(window),
                )

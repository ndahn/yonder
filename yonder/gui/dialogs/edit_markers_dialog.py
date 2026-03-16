from typing import Any, Callable
from pathlib import Path
from dearpygui import dearpygui as dpg

from yonder.gui import style
from yonder.gui.widgets import add_wav_player


def edit_looppoints_dialog(
    sound: Path,
    loop_start: float,
    loop_end: float,
    on_loop_changed: Callable[[str, tuple[float, float, bool], Any], None] = None,
    *,
    title: str = "Edit Loop Points",
    tag: str = None,
    user_data: Any = None,
) -> str:
    if not tag:
        tag = dpg.generate_uuid()

    loop_info: tuple[float, float, bool] = None

    def on_markers_changed(sender: str, new_loop_info: tuple[float, float, bool], user_data: Any) -> None:
        nonlocal loop_info
        loop_info = new_loop_info

    def show_message(msg: str, color: tuple[int, int, int, int] = style.red) -> None:
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
        if loop_info:
            if on_loop_changed:
                on_loop_changed(tag, loop_info, user_data)

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
        add_wav_player(
            sound,
            allow_change_file=False,
            loop_markers_enabled=True,
            loop_start=loop_start,
            loop_end=loop_end,
            on_loop_changed=on_markers_changed,
            max_points=10000,
            width=-1,
            height=-60,
        )

        dpg.add_separator()
        dpg.add_text(show=False, tag=f"{tag}_notification", color=style.red)

        with dpg.group(horizontal=True):
            dpg.add_button(label="Okay", callback=on_okay, tag=f"{tag}_button_okay")
            dpg.add_button(
                label="Cancel",
                callback=lambda: dpg.delete_item(window),
            )

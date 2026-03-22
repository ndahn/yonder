from typing import Any, Callable
from dearpygui import dearpygui as dpg

from yonder.gui import style
from yonder.gui.helpers import center_window
from yonder.gui.widgets import add_paragraphs


def choice_dialog(
    message: str,
    choices: list[str],
    callback: Callable[[str, str, Any], None],
    *,
    title: str = "Pick one",
    text_color: style.Color = style.white,
    close_on_pick: bool = True,
    tag: str = None,
    user_data: Any = None,
) -> str:
    if not tag:
        tag = dpg.generate_uuid()

    def on_choice(sender: str, app_data: Any, choice: str) -> None:
        # Delete first, otherwise chaining into other modal dialogs won't work
        if close_on_pick:
            dpg.delete_item(dialog)
            dpg.split_frame()

        callback(tag, choice, user_data)

    with dpg.window(
        label=title,
        modal=True,
        on_close=lambda: dpg.delete_item(dialog),
        no_saved_settings=True,
        autosize=True,
        tag=tag,
    ) as dialog:
        add_paragraphs(message, 40, color=text_color)
        
        dpg.add_separator()
        dpg.add_spacer(height=5)

        with dpg.group(horizontal=True):
            for choice in choices:
                if choice == "|":
                    dpg.add_text("|")
                elif choice in "<>^v":
                    arrows = {
                        "<": dpg.mvDir_Left,
                        ">": dpg.mvDir_Right,
                        "^": dpg.mvDir_Up,
                        "v": dpg.mvDir_Down,
                    }
                    dpg.add_button(
                        arrow=True,
                        direction=arrows[choice],
                        callback=on_choice,
                        user_data=choice,
                    )
                else:
                    dpg.add_button(label=choice, callback=on_choice, user_data=choice)

    dpg.split_frame()
    center_window(dialog)

    return tag

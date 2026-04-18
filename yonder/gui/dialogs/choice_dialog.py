from typing import Any, Callable
from dearpygui import dearpygui as dpg

from yonder.gui import style
from yonder.gui.helpers import center_window
from yonder.gui.widgets import add_paragraphs
from yonder.gui.widgets import DpgItem


_undefined = object()


class simple_choice_dialog(DpgItem):
    def __init__(self,
        message: str,
        choices: list[str],
        callback: Callable[[str, int, Any], None],
        *,
        cancel_val: Any = _undefined,
        title: str = "Pick one",
        text_color: style.Color = style.white,
        close_on_pick: bool = True,
        modal: bool = True,
        tag: str = None,
        user_data: Any = None,
    ) -> str:
        super().__init__(tag)

        def on_choice(sender: str, app_data: Any, choice: int) -> None:
            # Delete first, otherwise chaining into other modal dialogs won't work
            if close_on_pick:
                dpg.delete_item(dialog)
                dpg.split_frame()

            callback(tag, choice, user_data)

        def on_cancel() -> None:
            dpg.delete_item(dialog)
            dpg.split_frame()
            if cancel_val is not _undefined:
                callback(tag, cancel_val, user_data)

        with dpg.window(
            label=title,
            modal=modal,
            on_close=on_cancel,
            no_saved_settings=True,
            autosize=True,
            tag=self.tag,
        ) as dialog:
            if message:
                add_paragraphs(message, 40, color=text_color)
                dpg.add_separator()
                dpg.add_spacer(height=5)

            with dpg.group(horizontal=True):
                choice_idx = 0
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
                            user_data=choice_idx,
                        )
                        choice_idx += 1
                    else:
                        dpg.add_button(label=choice, callback=on_choice, user_data=choice_idx)
                        choice_idx += 1

        dpg.split_frame()
        center_window(dialog)


class simple_combo_dialog(DpgItem):
    def __init__(self,
        message: str,
        choices: list[str],
        callback: Callable[[str, str, Any], None],
        *,
        cancel_val: Any = _undefined,
        title: str = "Pick one",
        text_color: style.Color = style.white,
        modal: bool = True,
        tag: str = None,
        user_data: Any = None,
    ) -> str:
        if not tag:
            tag = dpg.generate_uuid()

        def on_okay() -> None:
            choice = dpg.get_value(self._t("choice"))

            # Delete first, otherwise chaining into other modal dialogs won't work
            dpg.delete_item(dialog)
            dpg.split_frame()
            callback(tag, choice, user_data)

        def on_cancel() -> None:
            dpg.delete_item(dialog)
            dpg.split_frame()
            if cancel_val is not _undefined:
                callback(tag, cancel_val, user_data)

        with dpg.window(
            label=title,
            modal=modal,
            on_close=on_cancel,
            no_saved_settings=True,
            autosize=True,
            tag=self.tag,
        ) as dialog:
            if message:
                add_paragraphs(message, 40, color=text_color)
                dpg.add_separator()
                dpg.add_spacer(height=5)

            dpg.add_combo(
                choices,
                fit_width=True,
                tag=self._t("choice"),
            )

            with dpg.group(horizontal=True):
                dpg.add_button(label="Okay", callback=on_okay, tag=self._t("okay"))

        dpg.split_frame()
        center_window(dialog)

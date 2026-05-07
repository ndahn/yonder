from typing import Any, Callable
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.util import logger
from yonder.gui import style
from yonder.gui.localization import µ
from yonder.gui.widgets.hash_widget import add_hash_widget
from yonder.gui.widgets import DpgItem


class rename_bank_dialog(DpgItem):
    def __init__(
        self,
        bnk: Soundbank,
        on_bank_renamed: Callable[[str, Soundbank, Any], None] = None,
        *,
        title: str = "Rename Bank",
        tag: str = None,
        user_data: Any = None,
    ) -> str:
        super().__init__(tag)

        def on_okay() -> None:
            if hash_widget.hash_value == bnk.bank_id:
                dpg.delete_item(window)
                return

            new_hash = hash_widget.known_value
            rename_dir = dpg.get_value(self._t("rename_dir"))
            logger.info(f"Changing bank_id to {new_hash}")
            bnk.rename(new_hash, rename_dir)

            if on_bank_renamed:
                on_bank_renamed(self.tag, bnk, user_data)

            dpg.delete_item(window)

        with dpg.window(
            label=title,
            modal=True,
            width=340,
            height=160,
            no_saved_settings=True,
            on_close=lambda: dpg.delete_item(window),
        ) as window:
            hash_widget = add_hash_widget(bnk.bank_id, None, horizontal=False)
            dpg.add_checkbox(
                label=µ("Rename folder"),
                default_value=True,
                tag=self._t("rename_dir"),
            )

            dpg.add_separator()
            dpg.add_spacer(height=2)
            dpg.add_button(label=µ("Commence"), callback=on_okay)

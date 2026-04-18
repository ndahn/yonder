from dearpygui import dearpygui as dpg

from yonder.gui import style
from yonder.gui.localization import translate as t
from yonder.gui.widgets.hash_widget import add_hash_widget
from yonder.gui.widgets import DpgItem


class calc_hash_dialog(DpgItem):
    def __init__(
        self,
        default_value: int = 0,
        *,
        title: str = "Calc Hash",
        tag: str = None,
    ) -> str:
        super().__init__(tag)

        with dpg.window(
            label=title,
            width=320,
            height=130,
            no_saved_settings=True,
            tag=self.tag,
            on_close=lambda: dpg.delete_item(window),
        ) as window:
            add_hash_widget(default_value, None, horizontal=False)
            dpg.add_separator()
            dpg.add_text(
                "Calculates an FNV-1a 32bit hash",
                color=style.blue,
                tag=self._t("calc_hash/tips"),
            )

        return tag

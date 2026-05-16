from typing import Callable
from pathlib import Path
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.util import logger
from yonder.gui import style
from yonder.gui.localization import µ
from yonder.gui.widgets import add_generic_widget, add_paragraphs, loading_indicator
from yonder.gui.widgets import DpgItem


class new_soundbank_dialog(DpgItem):
    def __init__(
        self,
        on_soundbank_created: Callable[[Soundbank], None] = None,
        *,
        title: str = "New Soundbank",
        tag: str = None,
    ) -> str:
        super().__init__(tag)

        self._on_soundbank_created = on_soundbank_created
        self._build(title)

    # === Internal =====================================

    def _on_okay(self) -> None:
        name: str = dpg.get_value(self._t("name"))
        if not name:
            self.show_message(µ("Name cannot be empty"))
            return

        path: str = dpg.get_value(self._t("path"))
        if not path:
            self.show_message(µ("No path specified"))
            return

        bnk_dir= Path(path) / name
        if not bnk_dir.is_dir():
            bnk_dir.mkdir(parents=True, exist_ok=True)
        
        if list(bnk_dir.glob("*")):
            self.show_message(µ("{name} exists and is not empty").format(name=name))
            return

        self.show_message()
        logger.info(µ("Creating new soundbank {name}").format(name=name))

        with loading_indicator(µ("Working")):
            bnk = Soundbank.create_empty_soundbank(path, name)
        
        if self._on_soundbank_created:
            self._on_soundbank_created(bnk)

        dpg.delete_item(self.tag)

    def _build(self, title: str):
        with dpg.window(
            label=title,
            width=400,
            height=320,
            autosize=True,
            no_saved_settings=True,
            tag=self.tag,
            on_close=lambda: dpg.delete_item(window),
        ) as window:
            add_generic_widget(
                str,
                µ("Name"),
                default="cs_c0010",
                tag=self._t("name"),
                no_spaces=True,
            )
            add_generic_widget(
                Path,
                None,
                hint=µ("Soundbank path"),
                file_mode="folder",
                tag=self._t("path"),
            )

            dpg.add_separator()
            add_paragraphs(
                µ(
                    """\
                        - Creates a new empty soundbank with only the basics
                        - Should be used instead of editing cs_main where possible
                        - For the Tarnished add the new bank to NpcParam 80000000
                        - Some names may not work for unknown reasons (e.g. cs_c0100)
                        - Renaming a .bnk file/folder is not enough, use Bank->Rename
                    """,
                    "tips",
                ),
                color=style.light_blue,
            )

            dpg.add_separator()
            dpg.add_spacer(height=2)
            dpg.add_text(show=False, tag=self._t("notification"), color=style.red)

            with dpg.group(horizontal=True):
                dpg.add_button(label=µ("Onto Eternity!"), callback=self._on_okay)

    # === Public ========================================================

    def show_message(self, msg: str = None, color: style.RGBA = style.red) -> None:
        """Show or hide the notification label below the separator.

        Pass ``msg=None`` to hide it.
        """
        if not msg:
            dpg.hide_item(self._t("notification"))
            return

        dpg.configure_item(
            self._t("notification"),
            default_value=msg,
            color=color,
            show=True,
        )

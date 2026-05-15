from typing import Any, Callable
from dearpygui import dearpygui as dpg

from yonder import Soundbank, HIRCNode
from yonder.util import logger
from yonder.gui import style
from yonder.gui.localization import µ
from yonder.gui.widgets.hash_widget import add_hash_widget
from yonder.gui.widgets import DpgItem


class rename_node_dialog(DpgItem):
    def __init__(
        self,
        bnk: Soundbank,
        node: HIRCNode,
        on_node_renamed: Callable[[HIRCNode], None] = None,
        *,
        title: str = "Rename Node",
        tag: str = None,
    ) -> str:
        super().__init__(tag)

        def on_okay() -> None:
            if hash_widget.hash_value == bnk.bank_id:
                dpg.delete_item(window)
                return

            new_hash = hash_widget.known_value
            logger.info(
                µ("Renaming node {old_id} to {new_id}").format(
                    old_id=node.id, new_id=new_hash
                )
            )
            bnk.rename_node(node, new_hash)

            if on_node_renamed:
                on_node_renamed(node)

            dpg.delete_item(window)

        with dpg.window(
            label=title,
            modal=True,
            width=340,
            height=160,
            no_saved_settings=True,
            tag=self.tag,
            on_close=lambda: dpg.delete_item(window),
        ) as window:
            hash_widget = add_hash_widget(node.id, None, horizontal=False)

            dpg.add_separator()
            dpg.add_spacer(height=2)
            dpg.add_button(label=µ("Commence"), callback=on_okay)

from dearpygui import dearpygui as dpg

from yonder.gui import style
from yonder.gui.widgets.hash_widget import add_hash_widget


def calc_hash_dialog(
    default_value: int = 0,
    *,
    title: str = "Calc Hash",
    tag: str = None,
) -> str:
    if not tag:
        tag = dpg.generate_uuid()
    elif dpg.does_item_exist(tag):
        dpg.delete_item(tag)

    with dpg.window(
        label=title,
        width=400,
        height=400,
        autosize=True,
        no_saved_settings=True,
        tag=tag,
        on_close=lambda: dpg.delete_item(window),
    ) as window:
        add_hash_widget(default_value, None, horizontal=False)
        dpg.add_separator()
        dpg.add_text("Calculates an FNV-1a 32bit hash", color=style.blue)

    return tag

import webbrowser
from dearpygui import dearpygui as dpg

from yonder.util import resource_dir
from yonder.gui import style


def add_kofi_button(pos: tuple = tuple(), *, tag: str = 0) -> str:
    if not tag:
        tag = dpg.generate_uuid()

    if not dpg.does_item_exist("icon_kofi"):
        with dpg.texture_registry():
            kofi = resource_dir() / "kofi_white.png"
            w, h, _, data = dpg.load_image(str(kofi))
            dpg.add_static_texture(w, h, data, tag="icon_kofi")

    # Tooltips don't work on buttons with absolute position
    # See https://github.com/hoffstadt/DearPyGui/issues/2651
    with dpg.group(pos=pos):
        dpg.add_image_button(
            "icon_kofi",
            width=24,
            height=24,
            tint_color=(255, 255, 255, 200),
            callback=lambda: webbrowser.open("https://ko-fi.com/managarm"),
            tag=tag,
        )
        dpg.bind_item_theme(dpg.last_item(), style.themes.transparent_button)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text("Buy me a ko-fi?")

    return tag

from dearpygui import dearpygui as dpg

from yonder.util import resource_dir
from yonder.gui import style
from yonder.gui.helpers import center_window


def add_splash(*, tag: str = None, **window_args) -> str:
    if not dpg.does_item_exist("yonder_splash"):
        with dpg.texture_registry():
            img_path = resource_dir() / "maris.png"
            w, h, ch, data = dpg.load_image(str(img_path))
            dpg.add_static_texture(w, h, data, tag="yonder_splash")

    with dpg.window(
        width=400,
        height=300,
        no_saved_settings=True,
        on_close=lambda: dpg.delete_item(dialog),
        no_scrollbar=True,
        no_scroll_with_mouse=True,
        no_resize=True,
        no_background=True,
        no_title_bar=True,
        tag=tag,
        **window_args,
    ) as dialog:
        from yonder import __version__

        with dpg.group():
            dpg.add_image("yonder_splash", width=400, height=275)
            dpg.add_text(f"Banks of Yonder v{__version__}", color=style.white, pos=(100, 240))

    center_window(dialog)
    return dialog

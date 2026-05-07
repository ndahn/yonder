from dearpygui import dearpygui as dpg
import webbrowser

from yonder.util import resource_dir
from yonder.gui import style
from yonder.gui.localization import µ
from yonder.gui.widgets import DpgItem


class about_dialog(DpgItem):
    def __init__(self, *, tag: str = None, **window_args):
        super().__init__(tag)

        if not dpg.does_item_exist("yonder_about"):
            with dpg.texture_registry():
                img_path = resource_dir() / "maris_banner.png"
                w, h, ch, data = dpg.load_image(str(img_path))
                dpg.add_static_texture(w, h, data, tag="yonder_about")

        if not dpg.does_item_exist("icon_kofi"):
            with dpg.texture_registry():
                kofi = resource_dir() / "kofi_white.png"
                w, h, _, data = dpg.load_image(str(kofi))
                dpg.add_static_texture(w, h, data, tag="icon_kofi")

        with dpg.window(
            width=500,
            height=230,
            label=µ("About"),
            no_saved_settings=True,
            on_close=lambda: dpg.delete_item(dialog),
            no_scrollbar=True,
            no_scroll_with_mouse=True,
            no_resize=True,
            tag=self.tag,
            **window_args,
        ) as dialog:
            from yonder import __version__

            with dpg.group(horizontal=True):
                dpg.add_image("yonder_about", width=500, height=230)

                with dpg.group(pos=(15, 35)):
                    dpg.add_text(f"Banks of Yonder v{__version__}", color=style.white)
                    dpg.add_spacer(height=5)

                    dpg.add_text(
                        µ("Written by Nikolas Dahn"),
                        color=style.light_grey,
                    )
                    dpg.add_button(
                        label="https://github.com/ndahn/yonder",
                        small=True,
                        callback=lambda: webbrowser.open(
                            "https://github.com/ndahn/yonder"
                        ),
                    )
                    dpg.bind_item_theme(dpg.last_item(), style.themes.link_button)

                    dpg.add_text(
                        µ("Bugs, questions, feature request?"),
                        color=style.light_grey,
                    )
                    dpg.add_text(
                        µ("Find me on ?ServerName? @Managarm!"),
                        color=style.light_grey,
                    )

                # Tooltips don't work on buttons with absolute position
                # See https://github.com/hoffstadt/DearPyGui/issues/2651
                with dpg.group(pos=(15, 190)):
                    dpg.add_image_button(
                        "icon_kofi",
                        width=24,
                        height=24,
                        tint_color=(255, 255, 255, 200),
                        callback=lambda: webbrowser.open("https://ko-fi.com/managarm"),
                    )
                    dpg.bind_item_theme(dpg.last_item(), style.themes.transparent_button)
                    with dpg.tooltip(dpg.last_item()):
                        dpg.add_text("Buy me a ko-fi?")

        dpg.bind_item_theme(dialog, style.themes.no_padding)

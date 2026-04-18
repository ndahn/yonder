from dearpygui import dearpygui as dpg
import webbrowser

from yonder.util import resource_dir
from yonder.gui import style
from yonder.gui.localization import translate as t
from yonder.gui.widgets import DpgItem


class about_dialog(DpgItem):
    def __init__(self, *, tag: str = None, **window_args):
        super().__init__(tag)

        color = (48, 48, 48, 255)

        if not dpg.does_item_exist("yonder_splash"):
            with dpg.texture_registry():
                img_path = resource_dir() / "misty_cliffs.jpg"
                w, h, ch, data = dpg.load_image(str(img_path))
                dpg.add_static_texture(w, h, data, tag="yonder_splash")

        with dpg.window(
            width=410,
            height=230,
            label=t("About", "about"),
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
                dpg.add_image("yonder_splash", width=410, height=230)

                with dpg.group(pos=(10, 30)):
                    dpg.add_text(f"Banks of Yonder v{__version__}", color=color)

                    dpg.add_text(
                        "Written by Nikolas Dahn", color=color, tag=self._t("about/written_by")
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
                        "Bugs, questions, feature request?", 
                        color=color,
                        tag=self._t("about/contact1"),
                    )
                    dpg.add_text(
                        "Find me on ?ServerName? @Managarm!",
                        color=color,
                        tag=self._t("contact"),
                    )

        dpg.bind_item_theme(dialog, style.themes.no_padding)

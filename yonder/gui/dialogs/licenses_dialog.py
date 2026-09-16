from dearpygui import dearpygui as dpg
import webbrowser

from yonder.gui import style
from yonder.gui.localization import µ
from yonder.gui.widgets import DpgItem


class licenses_dialog(DpgItem):
    def __init__(self, *, tag: str = None, **window_args):
        super().__init__(tag)

        colorgen = style.HighContrastColorGenerator(
            initial_hue=0.57,
            hue_step=-0.07,
        )

        with dpg.window(
            autosize=True,
            label=µ("Licenses"),
            no_saved_settings=True,
            on_close=lambda: dpg.delete_item(dialog),
            no_scrollbar=True,
            no_scroll_with_mouse=True,
            no_resize=True,
            tag=self.tag,
            **window_args,
        ) as dialog:
            with dpg.child_window(auto_resize_x=True, auto_resize_y=True):
                theme = style.themes.make_link_theme(0.5, style.light_blue)
                dpg.add_button(
                    label="Yonder / GPLv3",
                    width=200,
                    callback=lambda: webbrowser.open(
                        "https://ndahn.github.io/yonder/"
                    ),
                )
                dpg.bind_item_theme(dpg.last_item(), theme)

                dpg.add_spacer(height=2)
                dpg.add_separator()
                dpg.add_spacer(height=3)

                theme = style.themes.make_link_theme(0.5, next(colorgen))
                dpg.add_button(
                    label="Rewwise / MIT",
                    width=200,
                    callback=lambda: webbrowser.open(
                        "https://github.com/vswarte/rewwise"
                    ),
                )
                dpg.bind_item_theme(dpg.last_item(), theme)

                theme = style.themes.make_link_theme(0.5, next(colorgen))
                dpg.add_button(
                    label="vgmstream (c)",
                    width=200,
                    callback=lambda: webbrowser.open(
                        "https://github.com/vgmstream/vgmstream"
                    ),
                )
                dpg.bind_item_theme(dpg.last_item(), theme)

                theme = style.themes.make_link_theme(0.5, next(colorgen))
                dpg.add_button(
                    label="Fromsoftware-rs / Apache 2.0",
                    width=200,
                    callback=lambda: webbrowser.open(
                        "https://github.com/vswarte/fromsoftware-rs/"
                    ),
                )
                dpg.bind_item_theme(dpg.last_item(), theme)

                theme = style.themes.make_link_theme(0.5, next(colorgen))
                dpg.add_button(
                    label="Material Icons / Apache 2.0",
                    width=200,
                    callback=lambda: webbrowser.open(
                        "https://github.com/google/material-design-icons/"
                    ),
                )
                dpg.bind_item_theme(dpg.last_item(), theme)

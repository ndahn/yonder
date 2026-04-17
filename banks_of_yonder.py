from dearpygui import dearpygui as dpg

from yonder.util import resource_dir
from yonder.gui.style import init_themes
from yonder.gui.localization import load_translations, apply_dpg_decorators
from yonder.gui.yonder import BanksOfYonder


def dpg_init():
    # Default font
    with dpg.font_registry():
        font_path = resource_dir() / "NotoSansMonoCJKsc-Regular.otf"
        with dpg.font(str(font_path), 18) as default_font:
            dpg.add_font_range_hint(dpg.mvFontRangeHint_Default)
            dpg.add_font_range_hint(dpg.mvFontRangeHint_Chinese_Simplified_Common)

        dpg.bind_font(default_font)

    # Themes
    init_themes()

    # Localization
    load_translations()
    apply_dpg_decorators()


if __name__ == "__main__":
    dpg.create_context()
    dpg_init()
    dpg.create_viewport(title="Banks of Yonder", width=1300, height=800)

    with dpg.window() as main_window:
        app = BanksOfYonder()

    dpg.set_primary_window(main_window, True)

    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()

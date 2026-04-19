from dearpygui import dearpygui as dpg

from yonder.gui import style


def loading_indicator(
    label: str, color: tuple[int, int, int, int] = style.light_blue
) -> str:
    dpg.split_frame()

    with dpg.window(
        modal=True,
        min_size=(50, 20),
        no_close=True,
        no_move=True,
        no_collapse=True,
        no_title_bar=True,
        no_resize=True,
        no_scroll_with_mouse=True,
        no_scrollbar=True,
        no_saved_settings=True,
    ) as dialog:
        with dpg.group(horizontal=True):
            dpg.add_loading_indicator(color=color)
            with dpg.group():
                dpg.add_spacer(height=5)
                dpg.add_text(label, tag=f"{dialog}_label")

    return dialog

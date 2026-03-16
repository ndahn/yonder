from typing import Any
from pathlib import Path
from dearpygui import dearpygui as dpg

from yonder.gui import style
from yonder.gui.helpers import shorten_path
from yonder.gui.config import get_config
from yonder.gui.widgets import add_generic_widget, add_filepaths_table


def settings_dialog(
    *,
    title: str = "Settings",
    tag: str = None,
) -> str:
    if not tag:
        tag = dpg.generate_uuid()
    elif dpg.does_item_exist(tag):
        dpg.delete_item(tag)

    config = get_config()

    def on_bankdirs_changed(sender: str, paths: list[Path], user_data: Any) -> None:
        config.bankdirs = [str(p) for p in paths]

    def on_hashdicts_changed(sender: str, paths: list[Path], user_data: Any) -> None:
        config.hash_dicts = [str(p) for p in paths]

    def show_message(msg: str = None, color: tuple[int, int, int, int] = style.red) -> None:
        if not msg:
            dpg.hide_item(f"{tag}_notification")
            return

        dpg.configure_item(
            f"{tag}_notification",
            default_value=msg,
            color=color,
            show=True,
        )

    def on_okay() -> None:
        config.save()
        config.refresh()
        dpg.delete_item(window)

    with dpg.window(
        label=title,
        width=400,
        height=400,
        autosize=True,
        no_saved_settings=True,
        tag=tag,
        on_close=lambda: dpg.delete_item(window),
    ) as window:
        with dpg.tree_node(label="External Tools", default_open=True):
            w = add_generic_widget(
                Path,
                "bnk2json",
                lambda s, a, u: setattr(config, "bnk2json_exe", a),
                default=shorten_path(config.bnk2json_exe),
                filetypes={"bnk2json.exe": "bnk2json.exe"},
            )
            with dpg.tooltip(w):
                dpg.add_text(
                    "For unpacking and repacking soundbanks", color=style.light_blue
                )

            w = add_generic_widget(
                Path,
                "wwise",
                lambda s, a, u: setattr(config, "wwise_exe", a),
                default=shorten_path(config.wwise_exe),
                filetypes={"WwiseConsole.exe": "WwiseConsole.exe"},
            )
            with dpg.tooltip(w):
                dpg.add_text("For wonverting wav to wem", color=style.light_blue)

            w = add_generic_widget(
                Path,
                "vgmstream",
                lambda s, a, u: setattr(config, "vgmstream_exe", a),
                default=shorten_path(config.vgmstream_exe),
                filetypes={"vgmstream-cli.exe": "vgmstream-cli.exe"},
            )
            with dpg.tooltip(w):
                dpg.add_text(
                    "For converting wem to wav and playback", color=style.light_blue
                )

        with dpg.tree_node(label="Data Sources", default_open=True):
            w = add_filepaths_table(
                config.bankdirs,
                on_bankdirs_changed,
                folders=True,
                label="Soundbank folders",
            )
            with dpg.tooltip(w):
                dpg.add_text("Used to locate external sounds", color=style.light_blue)

            dpg.add_spacer(height=3)

            w = add_filepaths_table(
                config.hash_dicts,
                on_hashdicts_changed,
                label="Hash dictionaries",
                filetypes={"Text files (.txt)": "*.txt"},
            )
            with dpg.tooltip(w):
                dpg.add_text("Used for reversing hashes", color=style.light_blue)

        dpg.add_spacer(height=3)
        dpg.add_separator()
        dpg.add_text(show=False, tag=f"{tag}_notification", color=style.red)

        with dpg.group(horizontal=True):
            dpg.add_button(label="Save", callback=on_okay, tag=f"{tag}_button_okay")

    return tag

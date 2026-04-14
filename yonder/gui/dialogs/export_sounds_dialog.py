from typing import Any
from pathlib import Path
import shutil
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.wem import wem2wav
from yonder.gui import style
from yonder.gui.config import get_config
from yonder.gui.widgets import add_generic_widget, loading_indicator


def export_sounds_dialog(
    *,
    title: str = "Export Soundbank Sounds",
    tag: str = None,
) -> str:
    if not tag:
        tag = dpg.generate_uuid()
    elif dpg.does_item_exist(tag):
        dpg.delete_item(tag)

    bnk: Soundbank = None
    output_dir: Path = None

    def on_soundbank_selected(sender: str, path: Path, user_data: Any) -> None:
        nonlocal bnk
        try:
            bnk = Soundbank.from_file(path)
        except Exception as e:
            show_message(str(e))

    def on_outputdir_selected(sender: str, path: Path, user_data: Any) -> None:
        nonlocal output_dir
        output_dir = path

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
        if not bnk:
            show_message("No soundbank loaded")
            return

        if not output_dir or not output_dir.is_dir():
            show_message("Invalid output directory")
            return

        show_message()
        export_full = dpg.get_value(f"{tag}_export_full")
        convert_to_wav = dpg.get_value(f"{tag}_convert_to_wav")

        loading = loading_indicator("Converting...")
        try:
            config = get_config()
            if export_full:
                wems = []
                for w in bnk.wems():
                    path = next(config.find_external_sounds(w), None)
                    if path:
                        wems.append(path)
            else:
                wems = [bnk.bnk_dir / f"{w}.wem" for w in bnk.wems()]

            if convert_to_wav:
                try:
                    vgmstream = config.locate_vgmstream()
                except ValueError as e:
                    show_message(str(e))
                    return

                wem2wav(vgmstream, wems, output_dir)
            else:
                for w in wems:
                    shutil.copy(w, output_dir)

            show_message("Yay!", color=style.blue)
            dpg.set_item_label(f"{tag}_button_okay", "Again?")
        finally:
            dpg.delete_item(loading)

    with dpg.window(
        label=title,
        width=400,
        height=400,
        autosize=True,
        no_saved_settings=True,
        tag=tag,
        on_close=lambda: dpg.delete_item(window),
    ) as window:
        add_generic_widget(
            Path,
            "Soundbank",
            on_soundbank_selected,
            filetypes={"Soundbanks (.bnk, .json)": ["*.bnk", "*.json"]},
        )
        add_generic_widget(
            Path,
            "Output dir",
            on_outputdir_selected,
            file_mode="folder",
        )

        dpg.add_spacer(height=5)

        dpg.add_checkbox(
            label="Export full sounds for streamed",
            default_value=True,
            tag=f"{tag}_export_full",
        )
        dpg.add_checkbox(
            label="Convert to wav",
            default_value=True,
            tag=f"{tag}_convert_to_wav",
        )

        dpg.add_separator()
        dpg.add_text(show=False, tag=f"{tag}_notification", color=style.red)

        with dpg.group(horizontal=True):
            dpg.add_button(label="Yoink!", callback=on_okay, tag=f"{tag}_button_okay")

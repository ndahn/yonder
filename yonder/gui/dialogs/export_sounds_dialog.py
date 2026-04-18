from typing import Any
from pathlib import Path
import shutil
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.wem import wem2wav
from yonder.gui import style
from yonder.gui.localization import translate as t
from yonder.gui.config import get_config
from yonder.gui.widgets import DpgItem, add_generic_widget, loading_indicator


class export_sounds_dialog(DpgItem):
    def __init__(
        self,
        *,
        title: str = "Export Soundbank Sounds",
        tag: str = None,
    ) -> str:
        super().__init__(tag)

        self._bnk: Soundbank = None
        self._output_dir: Path = None

        self._build(title)

    def _on_soundbank_selected(self, sender: str, path: Path, user_data: Any) -> None:
        try:
            self._bnk = Soundbank.from_file(path)
        except Exception as e:
            self.show_message(str(e))

    def _on_outputdir_selected(self, sender: str, path: Path, user_data: Any) -> None:
        self._output_dir = path

    def show_message(self, msg: str = None, color: style.RGBA = style.red) -> None:
        if not msg:
            dpg.hide_item(self._t("notification"))
            return

        dpg.configure_item(
            self._t("notification"),
            default_value=msg,
            color=color,
            show=True,
        )

    def _on_okay(self) -> None:
        if not self._bnk:
            self.show_message(
                t("No soundbank loaded", "export_sounds/msg_no_soundbank")
            )
            return

        if not self._output_dir or not self._output_dir.is_dir():
            self.show_message(
                t("Invalid output directory", "export_sounds/msg_invalid_output_dir")
            )
            return

        self.show_message()
        export_full = dpg.get_value(self._t("export_sounds/export_full"))
        convert_to_wav = dpg.get_value(self._t("export_sounds/convert_to_wav"))

        loading = loading_indicator(t("Converting...", "progress/converting"))
        try:
            config = get_config()
            if export_full:
                wems = []
                for w in self._bnk.wems():
                    path = next(config.find_external_sounds(w), None)
                    if path:
                        wems.append(path)
            else:
                wems = [self._bnk.bnk_dir / f"{w}.wem" for w in self._bnk.wems()]

            if convert_to_wav:
                try:
                    vgmstream = config.locate_vgmstream()
                except ValueError as e:
                    self.show_message(str(e))
                    return

                wem2wav(vgmstream, wems, self._output_dir)
            else:
                for w in wems:
                    shutil.copy(w, self._output_dir)

            self.show_message("Yay!", color=style.blue)
            dpg.set_item_label(
                self._t("export_sounds/button_okay"), t("Again?", "again")
            )
        finally:
            dpg.delete_item(loading)

    def _build(self, title: str):
        with dpg.window(
            label=title,
            width=400,
            height=400,
            autosize=True,
            no_saved_settings=True,
            tag=self.tag,
            on_close=lambda: dpg.delete_item(window),
        ) as window:
            add_generic_widget(
                Path,
                "Soundbank",
                self._on_soundbank_selected,
                filetypes={
                    t("Soundbanks (.bnk, .json)", "soundbank_files"): [
                        "*.bnk",
                        "*.json",
                    ]
                },
            )
            add_generic_widget(
                Path,
                "Output dir",
                self._on_outputdir_selected,
                file_mode="folder",
                tag=self._t("export_sounds/output_dir"),
            )

            dpg.add_spacer(height=5)

            dpg.add_checkbox(
                label="Export full sounds for streamed",
                default_value=True,
                tag=self._t("export_sounds/export_full"),
            )
            dpg.add_checkbox(
                label="Convert to wav",
                default_value=True,
                tag=self._t("export_sounds/convert_to_wav"),
            )

            dpg.add_separator()
            dpg.add_text(show=False, tag=self._t("notification"), color=style.red)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Yoink!",
                    callback=self._on_okay,
                    tag=self._t("export_sounds/button_okay"),
                )

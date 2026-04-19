from typing import Any, Callable
from pathlib import Path
from dearpygui import dearpygui as dpg

from yonder.wem import wav2wem, trim_silence, set_volume, create_prefetch_snippet
from yonder.gui import style
from yonder.gui.config import get_config
from yonder.gui.widgets import (
    add_generic_widget,
    add_filepaths_table,
    loading_indicator,
)
from yonder.gui.helpers import shorten_path
from yonder.gui.localization import µ
from yonder.gui.widgets import DpgItem


class convert_wavs_dialog(DpgItem):
    def __init__(
        self,
        callback: Callable[[list[Path]], None] = None,
        *,
        title: str = "Convert Wave Files",
        tag: str = None,
    ) -> str:
        if not tag:
            tag = dpg.generate_uuid()
        elif dpg.does_item_exist(tag):
            dpg.delete_item(tag)

        self.output_dir: Path = None
        self.wav_paths: list[Path] = []
        self.callback = callback

        self._build(title)

    # === DPG callbacks ========================================================

    def _on_wavs_changed(self, sender: str, paths: list[Path], user_data: Any) -> None:
        self.wav_paths.clear()
        self.wav_paths.extend(paths)

        if paths and self.output_dir is None:
            self.output_dir = paths[0].parent
            dpg.set_value(self._t("output_dir"), shorten_path(self.output_dir))

    def _on_outputdir_selected(self, sender: str, path: Path, user_data: Any) -> None:
        self.output_dir = path

    def _on_okay(self) -> None:
        if not self.wav_paths:
            self.show_message(µ("No wave files selected", "msg"))
            return

        if not self.output_dir or not self.output_dir.is_dir():
            self.show_message(µ("Invalid output directory", "msg"))
            return

        if dpg.get_value(self._t("convert_to_wem")):
            try:
                wwise_exe = get_config().locate_wwise()
            except Exception:
                self.show_message(µ("Wwise exe not found", "msg"))
                return

        self.show_message()

        loading = loading_indicator(µ("Converting..."))
        try:
            out_files = list(self.wav_paths)

            if dpg.get_value(self._t("trim_silence")):
                dpg.set_value(
                    f"{loading}_label",
                    µ("Trimming silence..."),
                )
                silence_threshold = dpg.get_value(self._t("silence_threshold"))

                # TODO batch processing
                for i, wav in enumerate(out_files):
                    trim_silence(
                        wav, silence_threshold, out_file=self.output_dir / wav.name
                    )
                    out_files[i] = self.output_dir / wav.name

            if dpg.get_value(self._t("create_prefetch_snippet")):
                dpg.set_value(
                    f"{loading}_label",
                    µ("Creating prefetch snippets..."),
                )
                snippet_length = dpg.get_value(self._t("snippet_legnth"))

                # TODO batch processing
                for i, wav in enumerate(out_files):
                    create_prefetch_snippet(
                        wav, snippet_length, out_file=self.output_dir / wav.name
                    )
                    out_files[i] = self.output_dir / wav.name

            if dpg.get_value(self._t("adjust_volume")):
                dpg.set_value(
                    f"{loading}_label",
                    µ("Adjusting volume..."),
                )
                target_volume = dpg.get_value(self._t("target_volume"))

                # TODO batch processing
                for i, wav in enumerate(out_files):
                    set_volume(wav, target_volume, out_file=self.output_dir / wav.name)
                    out_files[i] = self.output_dir / wav.name

            if dpg.get_value(self._t("convert_to_wem")):
                dpg.set_value(
                    f"{loading}_label",
                    µ("Converting {num} files...").format(num=len(out_files)),
                )
                out_files = wav2wem(wwise_exe, out_files, out_dir=self.output_dir)
        finally:
            dpg.delete_item(loading)

        if self.callback:
            self.callback(out_files)

        self.show_message(µ("Yay!", "msg"), color=style.blue)
        dpg.set_item_label(self._t("convert/button_okay"), µ("Again?"))

    # === Build ========================================================

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
            add_filepaths_table(
                [],
                self._on_wavs_changed,
                label=µ("Wave files"),
                filetypes={µ("Wave (.wav)", "filetypes"): "*.wav"},
                tag=self._t("wavs_table"),
            )

            dpg.add_spacer(height=5)

            add_generic_widget(
                Path,
                "Output dir",
                self._on_outputdir_selected,
                file_mode="folder",
                tag=self._t("output_dir"),
            )

            dpg.add_spacer(height=5)

            with dpg.group(horizontal=True):
                dpg.add_checkbox(
                    label="",
                    default_value=False,
                    tag=self._t("adjust_volume"),
                )
                dpg.add_slider_float(
                    label=µ("Target volume"),
                    default_value=-3.0,
                    min_value=-96.0,
                    max_value=96.0,
                    tag=self._t("target_volume"),
                )

            with dpg.group(horizontal=True):
                dpg.add_checkbox(
                    label="",
                    default_value=False,
                    tag=self._t("trim_silence"),
                )
                dpg.add_slider_float(
                    label=µ("Silence threshold"),
                    default_value=0.0,
                    min_value=-10.0,
                    max_value=10.0,
                    tag=self._t("silence_threshold"),
                )

            with dpg.group(horizontal=True):
                dpg.add_checkbox(
                    label="",
                    default_value=False,
                    tag=self._t("create_prefetch_snippet"),
                )
                dpg.add_slider_float(
                    label=µ("Snippet length"),
                    default_value=1.0,
                    min_value=-0.5,
                    max_value=10.0,
                    tag=self._t("snippet_length"),
                )

            dpg.add_spacer(height=5)

            dpg.add_checkbox(
                label=µ("Convert to .wem"),
                default_value=True,
                tag=self._t("convert_to_wem"),
            )

            dpg.add_separator()
            dpg.add_text(show=False, tag=self._t("notification"), color=style.red)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label=µ("Beat it!", "button"),
                    callback=self._on_okay,
                    tag=self._t("convert/button_okay"),
                )

    # === Public ========================================================

    def show_message(self, msg: str = None, color: style.RGBA = style.red) -> None:
        """Show or hide the notification label below the separator.

        Pass ``msg=None`` to hide it.
        """
        if not msg:
            dpg.hide_item(self._t("notification"))
            return

        dpg.configure_item(
            self._t("notification"),
            default_value=msg,
            color=color,
            show=True,
        )

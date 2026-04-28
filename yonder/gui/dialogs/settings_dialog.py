from typing import Any
from pathlib import Path
from dearpygui import dearpygui as dpg

from yonder.gui import style
from yonder.gui.localization import µ
from yonder.gui.helpers import shorten_path, dpg_section
from yonder.gui.config import get_config
from yonder.gui.widgets import DpgItem, add_generic_widget, add_filepaths_table


class settings_dialog(DpgItem):
    def __init__(
        self,
        *,
        title: str = "Settings",
        tag: str = None,
    ) -> str:
        super().__init__(tag)
        self._build(title)

    def _on_bankdirs_changed(
        self, sender: str, paths: list[Path], user_data: Any
    ) -> None:
        get_config().bankdirs = [str(p) for p in paths]

    def _on_hashdicts_changed(sender: str, paths: list[Path], user_data: Any) -> None:
        get_config().hash_dicts = [str(p) for p in paths]

    def _on_okay(self) -> None:
        config = get_config()
        config.save()
        config.refresh()
        dpg.delete_item(self.tag)

    def _build(self, title: str):
        config = get_config()

        with dpg.window(
            label=title,
            width=480,
            height=600,
            autosize=True,
            min_size=(480, 200),
            no_saved_settings=True,
            tag=self.tag,
            on_close=lambda: dpg.delete_item(window),
        ) as window:
            with dpg.tree_node(label=µ("General"), default_open=True):
                dpg.add_slider_double(
                    label=µ("Playback Volume"),
                    default_value=config.playback_volume,
                    min_value=0.1,
                    max_value=2.0,
                    clamped=True,
                    no_input=True,
                    callback=lambda s, a, u: setattr(config, "playback_volume", a),
                )

            dpg.add_spacer(height=5)
            with dpg.tree_node(
                label=µ("External Tools"),
                tag=self._t("external_tools"),
            ):
                w = add_generic_widget(
                    Path,
                    "bnk2json",
                    lambda s, a, u: setattr(config, "bnk2json_exe", str(a)),
                    default=shorten_path(config.bnk2json_exe),
                    filetypes={"bnk2json.exe": "bnk2json.exe"},
                )
                with dpg.tooltip(w):
                    dpg.add_text(
                        µ("For unpacking and repacking soundbanks"),
                        color=style.light_blue,
                        tag=self._t("hint_bnk2json"),
                    )

                w = add_generic_widget(
                    Path,
                    "wwise",
                    lambda s, a, u: setattr(config, "wwise_exe", str(a)),
                    default=shorten_path(config.wwise_exe),
                    filetypes={"WwiseConsole.exe": "WwiseConsole.exe"},
                )
                with dpg.tooltip(w):
                    dpg.add_text(
                        µ("For wonverting wav to wem"),
                        color=style.light_blue,
                        tag=self._t("hint_wwise"),
                    )

                w = add_generic_widget(
                    Path,
                    "vgmstream",
                    lambda s, a, u: setattr(config, "vgmstream_exe", str(a)),
                    default=shorten_path(config.vgmstream_exe),
                    filetypes={"vgmstream-cli.exe": "vgmstream-cli.exe"},
                )
                with dpg.tooltip(w):
                    dpg.add_text(
                        µ("For converting wem to wav and playback"),
                        color=style.light_blue,
                        tag=self._t("hint_vgmstream"),
                    )

            dpg.add_spacer(height=5)
            with dpg.tree_node(
                label=µ("Data Sources"),
                tag=self._t("data_sources"),
            ):
                dpg_section(µ("Soundbank folders"), style.muted_blue, spacer=0)
                dpg.add_text(µ("Used to locate external sounds"))
                w = add_filepaths_table(
                    config.bankdirs,
                    self._on_bankdirs_changed,
                    label=None,
                    folders=True,
                    tag=self._t("soundbank_dirs"),
                )

                dpg_section(µ("Hash dictionaries"), style.muted_rose, spacer=0)
                dpg.add_text(µ("Used for reversing hashes"))
                w = add_filepaths_table(
                    config.hash_dicts,
                    self._on_hashdicts_changed,
                    label=None,
                    filetypes={µ("Text files (.txt)"): "*.txt"},
                    tag=self._t("hash_dirs"),
                )

            dpg.add_spacer(height=2)
            dpg.add_separator()
            dpg.add_text(show=False, tag=self._t("notification"), color=style.red)

            dpg.add_spacer(height=4)
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label=µ("Save", "button"),
                    callback=self._on_okay,
                    tag=self._t("button_save"),
                )

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

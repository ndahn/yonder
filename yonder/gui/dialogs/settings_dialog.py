from typing import Any
from pathlib import Path
from dearpygui import dearpygui as dpg

from yonder.gui import style
from yonder.gui.localization import translate as t
from yonder.gui.helpers import shorten_path
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
            width=400,
            height=400,
            autosize=True,
            no_saved_settings=True,
            tag=self.tag,
            on_close=lambda: dpg.delete_item(window),
        ) as window:
            with dpg.tree_node(
                label="External Tools",
                default_open=True,
                tag=self._t("settings/external_tools"),
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
                        "For unpacking and repacking soundbanks",
                        color=style.light_blue,
                        tag=self._t("settings/hint_bnk2json"),
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
                        "For wonverting wav to wem",
                        color=style.light_blue,
                        tag=self._t("settings/hint_wwise"),
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
                        "For converting wem to wav and playback",
                        color=style.light_blue,
                        tag=self._t("settings/hint_vgmstream"),
                    )

            with dpg.tree_node(
                label="Data Sources",
                default_open=True,
                tag=self._t("settings/data_sources"),
            ):
                w = add_filepaths_table(
                    config.bankdirs,
                    self._on_bankdirs_changed,
                    folders=True,
                    label="Soundbank folders",
                    tag=self._t("settings/soundbank_dirs"),
                )
                with dpg.tooltip(w):
                    dpg.add_text(
                        "Used to locate external sounds",
                        color=style.light_blue,
                        tag=self._t("settings/hint_soundbank_dirs"),
                    )

                dpg.add_spacer(height=3)

                w = add_filepaths_table(
                    config.hash_dicts,
                    self._on_hashdicts_changed,
                    label="Hash dictionaries",
                    filetypes={t("Text files (.txt)", "text_files"): "*.txt"},
                    tag=self._t("settings/hash_dirs"),
                )
                with dpg.tooltip(w):
                    dpg.add_text(
                        "Used for reversing hashes",
                        color=style.light_blue,
                        tag=self._t("settings/hint_hash_dirs"),
                    )

            dpg.add_spacer(height=3)
            dpg.add_separator()
            dpg.add_text(show=False, tag=self._t("notification"), color=style.red)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Save", callback=self._on_okay, tag=self._t("button_save")
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

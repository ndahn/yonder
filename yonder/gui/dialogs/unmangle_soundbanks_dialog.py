from typing import Any
from pathlib import Path
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.convenience import unmangle_soundbanks
from yonder.game import GameObjects, get_selected_game, guess_game
from yonder.util import unpack_soundbank, repack_soundbank, logger
from yonder.gui import style
from yonder.gui.localization import µ
from yonder.gui.widgets import (
    DpgItem,
    add_paragraphs,
    add_generic_widget,
    loading_indicator,
    yay,
)
from yonder.gui.config import get_config


class unmangle_soundbanks_dialog(DpgItem):
    def __init__(
        self,
        *,
        title: str = "Unmangle Soundbanks",
        tag: str = None,
    ) -> str:
        super().__init__(tag)

        game = get_selected_game()
        game_path = game.get_game_path(None)
        self._banks_path = game_path
        self._detected_game: GameObjects = game if game_path else None
        self._output_path: Path = None

        self._build(title)

    def _on_banks_path_changed(self, sender: str, path: Path, user_data: Any) -> None:
        game = guess_game(path)
        if game:
            self._show_message()
            self._detected_game = game
            self._banks_path = path
            dpg.set_value(self._t("detected_game"), game.name)
            dpg.enable_item(self._t("button_okay"))
        else:
            self._show_message(µ("Could not detect a supported game"))
            self._detected_game = None
            self._banks_path = None
            dpg.set_value(self._t("detected_game"), "-")
            dpg.disable_item(self._t("button_okay"))

    def _on_output_folder_changed(
        self, sender: str, path: Path, user_data: Any
    ) -> None:
        self._output_path = path

    def _locate_bank(self, bnk_name: str) -> Path:
        user = list(self._banks_path.glob(f"**/{bnk_name}.bnk"))
        if user:
            return user[0]

        banks_path = self._detected_game.get_banks_path() / "Game"
        try:
            return next(banks_path.glob(f"**/{bnk_name}.bnk"))
        except StopIteration:
            raise ValueError(f"Could not locate {bnk_name}.bnk")

    def _on_okay(self) -> None:
        if not self._detected_game:
            self._show_message(µ("Select a valid game path first"))
            return

        if not self._output_path:
            self._show_message(µ("No output folder selected"))
            return

        with loading_indicator(µ("Unmangling...")):
            self._show_message()

            try:
                # cs_main
                logger.info("Loading cs_main...")
                main_path: Path = self._locate_bank("cs_main")

                if not main_path.is_dir():
                    bnk2json = get_config().locate_bnk2json()
                    main_path = unpack_soundbank(bnk2json, main_path)

                bnk_main = Soundbank.load(main_path)

                # cs_smain
                logger.info("Loading cs_smain...")
                smain_path: Path = self._locate_bank("cs_smain")

                if not smain_path.is_dir():
                    bnk2json = get_config().locate_bnk2json()
                    smain_path = unpack_soundbank(bnk2json, smain_path)

                bnk_smain = Soundbank.load(smain_path)

                # Unmangle and save
                unmangle_soundbanks(bnk_main, bnk_smain, self._detected_game)

                bnk_main.copy_to(self._output_path)
                bnk_smain.copy_to(self._output_path)

                if dpg.get_value(self._t("repack")):
                    bnk2json = get_config().locate_bnk2json()
                    repack_soundbank(bnk2json, bnk_main)
                    repack_soundbank(bnk2json, bnk_smain)

                logger.info(f"Modified banks have been saved to {self._output_path}")
            except Exception as e:
                self._show_message(str(e))
                raise

        logger.info("Banks unmangled and ready for glory!")
        dpg.delete_item(self.tag)
        yay()

    def _show_message(self, msg: str = None, color: style.RGBA = style.red) -> None:
        """Show or hide the notification label below the separator."""
        if not msg:
            dpg.hide_item(self._t("notification"))
            return

        dpg.configure_item(
            self._t("notification"),
            default_value=msg,
            color=color,
            show=True,
        )

    def _build(self, title: str) -> None:
        with dpg.window(
            label=title,
            autosize=True,
            no_saved_settings=True,
            tag=self.tag,
            on_close=lambda: dpg.delete_item(window),
        ) as window:
            add_generic_widget(
                Path,
                µ("Banks dir"),
                self._on_banks_path_changed,
                default=self._banks_path,
                file_mode="folder",
                tag=self._t("banks_path"),
            )
            with dpg.tooltip(dpg.last_item()):
                dpg.add_text(µ("Your game or mod folder"))

            add_generic_widget(
                Path,
                µ("Output dir"),
                self._on_output_folder_changed,
                default=self._output_path,
                file_mode="folder",
                tag=self._t("output_path"),
            )
            with dpg.tooltip(dpg.last_item()):
                dpg.add_text(µ("Where to save the modified banks"))

            dpg.add_checkbox(
                label=µ("Repack"),
                default_value=True,
                tag=self._t("repack"),
            )

            with dpg.group(horizontal=True):
                dpg.add_text(µ("Detected game: "))
                dpg.add_text(
                    self._detected_game.game.name if self._detected_game else "-",
                    tag=self._t("detected_game"),
                )

            dpg.add_separator()
            add_paragraphs(
                µ(
                    """\
                    Some games have redundant wwise structures in banks they are not supposed to be in. This works because they largely mirror the true structures, but causes issues when the two go out of sync. Worst case any changes you make will be ignored. 
                    
                    This tool will remove those duplicates.
                """,
                    "tips",
                ),
                color=style.light_blue,
            )
            dpg.add_separator()
            dpg.add_text(show=False, tag=self._t("notification"), color=style.red)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label=µ("Unmangle!"),
                    callback=self._on_okay,
                    tag=self._t("button_okay"),
                )

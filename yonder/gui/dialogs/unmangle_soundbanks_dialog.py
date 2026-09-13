from typing import Any
from pathlib import Path
import webbrowser
import shutil
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.convenience import unmangle_soundbanks
from yonder.enums import Game
from yonder.game import get_selected_game, guess_game
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
        self._output_path: Path = None

        self._build(title)

    @property
    def selected_game(self) -> Game:
        try:
            return Game[dpg.get_value(self._t("selected_game"))]
        except ValueError:
            return None

    def _on_banks_path_changed(self, sender: str, path: Path, user_data: Any) -> None:
        game = guess_game(path)
        if game is not None:
            self._show_message()
            self._banks_path = path
            dpg.set_value(self._t("selected_game"), game.name)
            dpg.enable_item(self._t("button_okay"))
        else:
            self._show_message(µ("Could not detect a supported game"))
            self._banks_path = None
            dpg.set_value(self._t("selected_game"), "-")
            dpg.disable_item(self._t("button_okay"))

    def _on_output_folder_changed(
        self, sender: str, path: Path, user_data: Any
    ) -> None:
        self._output_path = path

    def _locate_bank(self, bnk_name: str) -> Path:
        user = list(self._banks_path.glob(f"**/{bnk_name}.bnk"))
        if user:
            return user[0]

        try:
            return next(self._banks_path.glob(f"**/{bnk_name}.bnk"))
        except StopIteration:
            raise ValueError(f"Could not locate {bnk_name}.bnk")

    def _load_bank_copy(self, path: Path) -> Soundbank:
        out_path = self._output_path.resolve()


        # Do all work on a copy
        if path.parent.resolve() != out_path:
            # Clean up any previous files
            dest = out_path / path.stem
            if dest.is_dir():
                shutil.rmtree(dest, ignore_errors=True)

            dest = out_path / (path.stem + ".bnk")
            if dest.is_file():
                dest.unlink()

            # Make a fresh copy
            if path.is_dir():
                shutil.copytree(path, out_path)
            else:
                shutil.copy(path, out_path)

            path = out_path / path.name
        
        if not path.is_dir():
            bnk2json = get_config().locate_bnk2json()
            path = unpack_soundbank(bnk2json, path)

        return Soundbank.load(path)

    def _on_okay(self) -> None:
        game = self.selected_game
        if not game:
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
                bnk_main = self._load_bank_copy(main_path)

                # cs_smain
                logger.info("Loading cs_smain...")
                smain_path: Path = self._locate_bank("cs_smain")
                bnk_smain = self._load_bank_copy(smain_path)

                # Unmangle and save
                unmangle_soundbanks(bnk_main, bnk_smain, game)
                bnk_main.save()
                bnk_smain.save()

                if dpg.get_value(self._t("repack")):
                    try:
                        bnk2json = get_config().locate_bnk2json()
                        repack_soundbank(bnk2json, bnk_main.bnk_dir)
                        repack_soundbank(bnk2json, bnk_smain.bnk_dir)
                    except Exception as e:
                        logger.error(f"Repacking failed: {e}")
                        self._show_message(
                            µ("Unmangling done, but repacking failed"),
                            color=style.yellow,
                        )

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

            with dpg.group(horizontal=True):
                dpg.add_combo(
                    [g.name for g in Game],
                    label=µ("Game"),
                    default_value=get_selected_game().game.name,
                    tag=self._t("selected_game"),
                )

            dpg.add_checkbox(
                label=µ("Repack"),
                default_value=True,
                tag=self._t("repack"),
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
                dpg.add_button(
                    label="?",
                    callback=lambda s, a, u: webbrowser.open(u),
                    user_data="https://ndahn.github.io/yonder/tools/unmangle/",
                )
                with dpg.tooltip(dpg.last_item()):
                    dpg.add_text("https://ndahn.github.io/yonder/tools/unmangle/")

from typing import Any, Callable
from pathlib import Path
from dearpygui import dearpygui as dpg

from yonder import Soundbank, calc_hash
from yonder.convenience import create_simple_sound
from yonder.types import Event, ActorMixer
from yonder.enums import PropID
from yonder.wem import wav2wem
from yonder.gui import style
from yonder.gui.config import get_config
from yonder.gui.localization import translate as t
from yonder.gui.widgets import (
    DpgItem,
    add_properties_table,
    add_node_reference,
    add_player_table,
)


class create_simple_sound_dialog(DpgItem):
    """A dialog for creating a simple sound event from one or more audio files.

    Collects a name, actor mixer reference, optional properties, and a list of
    sound files. On confirm, converts any ``.wav`` files to ``.wem``, calls
    ``create_simple_sound``, and passes the resulting play/stop events to
    ``callback``.

    Parameters
    ----------
    bnk : Soundbank
        Target soundbank; used for ID allocation and duplicate checking.
    callback : callable
        Called as ``callback(play_event, stop_event)`` on success.
    default_name : str
        Pre-filled value for the Name field.
    title : str
        Window title bar label.
    tag : int or str, optional
        Explicit tag; auto-generated if None. Existing item is deleted first.
    """

    def __init__(
        self,
        bnk: Soundbank,
        callback: Callable[[Event, Event], None],
        *,
        default_name: str = "s100200300",
        title: str = "Create Simple Sound",
        tag: int | str = None,
    ) -> None:
        if tag and dpg.does_item_exist(tag):
            dpg.delete_item(tag)

        super().__init__(tag if tag else dpg.generate_uuid())

        self._bnk = bnk
        self._callback = callback
        self._properties: dict[PropID, float] = {}
        self._soundfiles: list[Path] = []
        self._window: int | str = None

        self._build(title, default_name)

    # === Build =========================================================

    def _build(self, title: str, default_name: str) -> None:
        with dpg.window(
            label=title,
            width=400,
            height=400,
            autosize=True,
            no_saved_settings=True,
            tag=self._tag,
            on_close=lambda: dpg.delete_item(self._window),
        ) as self._window:
            dpg.add_input_text(
                label="Name",
                default_value=default_name,
                callback=self._update_name_and_id,
                tag=self._t("name"),
            )
            dpg.add_input_text(
                label="Hash",
                default_value=str(calc_hash(default_name)),
                readonly=True,
                enabled=False,
                tag=self._t("hash"),
            )

            # Actor mixer selector
            add_node_reference(
                self._bnk.query,
                "ActorMixer",
                self._on_amx_selected,
                node_type=ActorMixer,
                get_node_details=self._get_amx_details,
                tag=self._t("actor_mixer"),
            )

            # Avoid repeats
            dpg.add_checkbox(
                label="Avoid Repeats",
                default_value=False,
                tag=self._t("avoid_repeats"),
            )

            # Properties
            dpg.add_spacer(height=5)
            add_properties_table(self._properties, self._on_properties_changed)

            # Sounds
            dpg.add_spacer(height=5)
            add_player_table(
                self._soundfiles,
                self._on_soundfiles_changed,
                label="Sounds",
                add_item_label="+ Add Sound",
                get_row_label=lambda i: f"source #{i}",
            )

            dpg.add_separator()
            dpg.add_text(show=False, tag=self._t("notification"), color=style.red)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Summon!",
                    callback=self._on_okay,
                    tag=self._t("simple_sound/button_okay"),
                )

    # === DPG callbacks =================================================

    def _update_name_and_id(self, sender: str, new_name: str, ud: Any) -> None:
        if not new_name:
            return
        dpg.set_value(self._t("hash"), str(calc_hash(new_name)))

    @staticmethod
    def _get_amx_details(node: ActorMixer) -> list[str]:
        return [
            f"parent: {node.parent}",
            f"children: {len(node.children)}",
        ]

    def _on_amx_selected(self, sender: str, amx: ActorMixer, ud: Any) -> None:
        if amx:
            dpg.set_value(self._t("actor_mixer"), amx.id)

    def _on_properties_changed(
        self, sender: str, new_properties: dict[PropID, float], ud: Any
    ) -> None:
        self._properties.clear()
        self._properties.update(new_properties)

    def _on_soundfiles_changed(
        self, sender: str, data: tuple[list[Path], ...], ud: Any
    ) -> None:
        self._soundfiles.clear()
        self._soundfiles.extend(data[0])

    def _on_okay(self) -> None:
        name = dpg.get_value(self._t("name"))
        if not name:
            self.show_message(t("Name not specified", "simple_sound/msg_name_missing"))
            return

        if f"Play_{name}" in self._bnk or f"Stop_{name}" in self._bnk:
            self.show_message(
                t("An event with this name already exists", "simple_sound/msg_name_duplicate")
            )
            return

        amx = int(dpg.get_value(self._t("actor_mixer")))
        if amx <= 0:
            self.show_message(t("ActorMixer not specified", "simple_sound/msg_amx_missing"))
            return

        if not self._soundfiles:
            self.show_message(t("No sounds specified", "simple_sound/msg_sounds_missing"))
            return

        waves = [f for f in self._soundfiles if f.suffix == ".wav"]
        if waves:
            wwise = get_config().locate_wwise()
            converted = wav2wem(wwise, waves)
            for wem in converted:
                for idx, f in enumerate(self._soundfiles):
                    if f.stem == wem.stem:
                        self._soundfiles[idx] = wem

        self.show_message()
        avoid_repeats = dpg.get_value(self._t("avoid_repeats"))

        (play_evt, stop_evt), _, _ = create_simple_sound(
            self._bnk,
            name,
            self._soundfiles,
            amx,
            avoid_repeat_count=avoid_repeats,
            properties=self._properties,
        )

        self._callback(play_evt, stop_evt)
        self.show_message(t("Yay!", "yay"), color=style.blue)
        dpg.set_item_label(self._t("button_okay"), t("Again?", "again"))

    # === Public ========================================================

    def show_message(self, msg: str = None, color: style.Color = style.red) -> None:
        """Show or hide the notification label. Pass ``msg=None`` to hide."""
        if not msg:
            dpg.hide_item(self._t("notification"))
            return

        dpg.configure_item(
            self._t("notification"),
            default_value=msg,
            color=color,
            show=True,
        )

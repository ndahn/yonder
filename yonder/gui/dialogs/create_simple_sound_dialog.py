from typing import Any, Callable
from pathlib import Path
from dearpygui import dearpygui as dpg

from yonder import Soundbank, calc_hash
from yonder.convenience import create_simple_sound
from yonder.node_types import Event, ActorMixer
from yonder.enums import property_defaults
from yonder.util import logger
from yonder.wem import wav2wem
from yonder.gui import style
from yonder.gui.config import get_config
from yonder.gui.widgets import (
    add_properties_table,
    add_node_widget,
    add_player_table,
)


def create_simple_sound_dialog(
    bnk: Soundbank,
    callback: Callable[[Event, Event], None],
    *,
    default_name: str = "s100200300",
    title: str = "Create Simple Sound",
    tag: str = None,
) -> str:
    if not tag:
        tag = dpg.generate_uuid()
    elif dpg.does_item_exist(tag):
        dpg.delete_item(tag)

    properties: dict[str, float] = {
        "Volume": property_defaults["Volume"],
    }
    soundfiles: list[Path] = []

    def update_name_and_id(sender: str, new_name: str, user_data: Any) -> None:
        if not new_name:
            return

        h = calc_hash(new_name)
        dpg.set_value(f"{tag}_hash", str(h))

    def get_amx_details(node: ActorMixer) -> list[str]:
        return [
            f"parent: {node.parent}",
            f"children: {len(node.children)}",
        ]

    def on_amx_selected(sender: str, amx: ActorMixer, user_data: Any) -> None:
        if amx:
            dpg.set_value(f"{tag}_actor_mixer", amx.id)

    def on_properties_changed(
        sender: str, new_properties: dict[str, float], user_data: Any
    ) -> None:
        properties.clear()
        properties.update(new_properties)

    def on_soundfiles_changed(sender: str, paths: list[Path], user_data: Any) -> None:
        soundfiles.clear()
        soundfiles.extend(paths)

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
        name = dpg.get_value(f"{tag}_name")
        if not name:
            show_message("Name not specified")
            return

        if f"Play_{name}" in bnk or f"Stop_{name}" in bnk:
            show_message("An event with this name already exists")
            return

        amx = int(dpg.get_value(f"{tag}_actor_mixer"))
        if amx <= 0:
            show_message("ActorMixer not specified")
            return

        if not soundfiles:
            show_message("No sounds specified")
            return

        waves = {f.stem: i for i, f in enumerate(soundfiles) if f.name.endswith(".wav")}
        if waves:
            logger.info(f"Converting {len(waves)} wave files to wem")
            wwise = get_config().locate_wwise()
            converted_wavs = wav2wem(wwise, waves)
            for wem in converted_wavs:
                idx = waves[wem.stem]
                soundfiles[idx] = wem

        show_message()
        avoid_repeats = dpg.get_value(f"{tag}_avoid_repeats")

        (play_evt, stop_evt), _, _ = create_simple_sound(
            bnk,
            name,
            soundfiles,
            amx,
            avoid_repeats=avoid_repeats,
            properties=properties,
        )

        logger.info(f"Created new sound {name} with {len(soundfiles)} sounds")

        callback(play_evt, stop_evt)
        show_message("Yay!", color=style.blue)
        dpg.set_item_label(f"{tag}_button_okay", "Again?")

    with dpg.window(
        label=title,
        width=400,
        height=400,
        autosize=True,
        no_saved_settings=True,
        tag=tag,
        on_close=lambda: dpg.delete_item(window),
    ) as window:
        dpg.add_input_text(
            label="Name",
            default_value=default_name,
            callback=update_name_and_id,
            tag=f"{tag}_name",
        )
        dpg.add_input_text(
            label="Hash",
            default_value=str(calc_hash(default_name)),
            readonly=True,
            enabled=False,
            tag=f"{tag}_hash",
        )

        # Actor mixer selector
        add_node_widget(
            bnk.query,
            "ActorMixer",
            on_amx_selected,
            node_type=ActorMixer,
            get_node_details=get_amx_details,
            tag=f"{tag}_actor_mixer",
        )

        # Avoid repeats
        dpg.add_checkbox(
            label="Avoid Repeats",
            default_value=False,
            tag=f"{tag}_avoid_repeats",
        )

        # Properties
        dpg.add_spacer(height=5)
        add_properties_table(properties, on_properties_changed)

        # WEMs
        dpg.add_spacer(height=5)
        add_player_table(
            soundfiles,
            on_soundfiles_changed,
            label="Sounds",
            add_item_label="+ Add Sound",
            get_row_label=lambda i: f"source #{i}",
        )

        dpg.add_separator()
        dpg.add_text(show=False, tag=f"{tag}_notification", color=style.red)

        with dpg.group(horizontal=True):
            dpg.add_button(label="Summon!", callback=on_okay, tag=f"{tag}_button_okay")

    return tag

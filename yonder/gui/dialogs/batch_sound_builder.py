from typing import Any, Callable
import re
from pathlib import Path
from dataclasses import dataclass, field
from dearpygui import dearpygui as dpg

from yonder import Soundbank, calc_hash
from yonder.convenience import create_simple_sound
from yonder.types import Event, ActorMixer
from yonder.query import query_nodes
from yonder.enums import PropID, RandomMode, PlaybackMode, SoundType
from yonder.util import logger
from yonder.wem import wav2wem
from yonder.gui import style
from yonder.gui.config import get_config
from yonder.gui.widgets import (
    add_widget_table,
    add_properties_table,
    add_filepaths_table,
    add_node_widget,
    add_wav_player,
)
from .file_dialog import open_multiple_dialog


@dataclass
class BatchGroup:
    name: str = None
    actormixer: int = 0
    soundtype: SoundType = SoundType.Sfx
    playback_mode: PlaybackMode = PlaybackMode.Random
    randomization: RandomMode = RandomMode.Standard
    properties: dict[PropID, float] = field(default_factory=dict)
    soundfiles: list[Path] = field(default_factory=list)


def create_batch_sound_builder_dialog(
    bnk: Soundbank,
    callback: Callable[[Event, Event], None],
    *,
    title: str = "Create Simple Sound",
    tag: str = None,
) -> str:
    if not tag:
        tag = dpg.generate_uuid()
    elif dpg.does_item_exist(tag):
        dpg.delete_item(tag)

    groups: list[BatchGroup] = []
    selected_group: int = 0
    actormixers: list[ActorMixer] = list(bnk.query("type=ActorMixer"))

    # === Helpers =====================

    def soundtype_choice_to_enum(choice: str) -> SoundType:
        val = re.findall(r"\((\w)\)")[0]
        return SoundType(val)

    def new_group_name(group_idx: int) -> str:
        if bnk.name:
            parts = re.split(r"c(?=\d{4})")
            if parts[0] != bnk.name:
                base_id = int(parts[-1]) * 10**6 + 10000 + group_idx * 1000
                return f"{base_id:09}"

        return f"{(group_idx + 1) * 1000:09}"

    def make_setter(key: str, transformer: Callable[[Any], Any] = None) -> Callable:
        def setter(sender: str, val: Any, user_data: Any) -> None:
            if transformer:
                val = transformer(val)
            setattr(groups[selected_group], key, val)
        return setter

    # === Value Updates ===============

    def on_soundtype_changed(sender: str, choice: str, user_data: Any) -> None:
        g = groups[selected_group]
        g.soundtype = soundtype_choice_to_enum(choice)

        old_name = dpg.get_value(f"{tag}_name")
        if re.match(rf"[{SoundType.values()}]\d+", old_name):
            new_name = g.soundtype.value + old_name[1:]
            dpg.set_value(f"{tag}_name", new_name)

    def on_name_changed(sender: str, name: str, user_data: Any) -> None:
        g = groups[selected_group]

        if re.match(rf"[{SoundType.values()}]\d\{8,10}", name):
            g.soundtype = Soundbank(name[0])
            dpg.set_value(f"{tag}_soundtype", str(g.soundtype))
            name = name[1:]

        if not name.isalnum():
            show_message("Name has non-standard format", color=style.yellow)
        else:
            show_message()

        g.name = name

    # === Table Management ===============

    def group_to_row(group: BatchGroup, idx: int) -> None:
        name = f"{group.soundtype.value}{group.name}"
        dpg.add_text(name)

    def select_group(idx: int) -> None:
        nonlocal selected_group
        selected_group = idx
        g = groups[idx]

        # Standard widgets
        dpg.set_value(f"{tag}_name", g.name)
        dpg.set_value(f"{tag}_soundtype", str(g.soundtype))
        dpg.set_value(f"{tag}_playback_mode", str(g.playback_mode))
        dpg.set_value(f"{tag}_randomization", str(g.randomization))

        # Custom widgets
        dpg.set_value(f"{tag}_actormixer", f"#{g.actormixer}")
        dpg.set_value(f"{tag}_properties", g.properties)  # TODO
        dpg.set_value(f"{tag}_soundfiles", g.soundfiles)  # TODO

    # === Batch Operations ==========
    
    def batch_apply_soundtype() -> None:
        choice = dpg.get_value(f"{tag}_batch_soundtype")
        soundtype = soundtype_choice_to_enum(choice)
        for g in groups:
            g.soundtype = soundtype

        dpg.set_value(f"{tag}_soundtype", str(soundtype))

    def batch_groups_from_files() -> None:
        ret = open_multiple_dialog(
            title="Select Audio Files",
            filetypes={"Wave (.wav)": "*.wav", "WEM (.wem)": "*.wem"},
        )

        if ret:
            choice = dpg.get_value(f"{tag}_batch_soundtype")
            soundtype = soundtype_choice_to_enum(choice)
            for f in ret:
                g = BatchGroup(new_group_name(), soundtype=soundtype, soundfiles=[f])
                groups.append(g)

            # TODO regenerate groups list

    # === User Things ===============

    def show_message(
        msg: str = None, color: tuple[int, int, int, int] = style.red
    ) -> None:
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
        # TODO
        pass

        created_pairs: list[tuple[Event, Event]] = []
        for idx, g in enumerate(groups):
            (play_evt, stop_evt), _, _ = create_simple_sound(
                bnk,
                g.soundtype.value + g.name,
                wems[idx],
                g.actormixer,
                avoid_repeats=avoid_repeats,
                # TODO playback mode, random mode
                properties=g.properties,
            )
            created_pairs.append((play_evt, stop_evt))

        if callback:
            callback(created_pairs)

        show_message("Yay!", color=style.blue)
        dpg.set_item_label(f"{tag}_button_okay", "Again?")

    # === GUI Content =============

    with dpg.window(
        label=title,
        width=1060,
        height=760,
        autosize=True,
        no_saved_settings=True,
        tag=tag,
        on_close=lambda: dpg.delete_item(window),
    ) as window:
        with dpg.group(horizontal=True):
            with dpg.child_window(
                width=320, height=560, resizable_x=True, autosize_y=True
            ):
                add_widget_table(
                    groups,
                    group_to_row,
                    new_item=lambda cb: cb(BatchGroup(new_group_name())),
                    on_add=lambda s, a, u: groups.append(a[1]),
                    on_remove=lambda s, a, u: groups.pop(a[0]),
                    on_select=lambda s, a, u: select_group(a[0]),
                    label="Groups",
                    add_item_label="Add Group",
                )

                dpg.add_spacer(height=3)

                with dpg.group():
                    dpg.add_text("Bulk operations", color=style.pink)
                    dpg.add_separator()

                    with dpg.group(horizontal=True):
                        dpg.add_combo(
                            [str(st) for st in SoundType],
                            tag=f"{tag}_batch_soundtype",
                        )
                        dpg.add_button(
                            arrow=True,
                            direction=dpg.mvDir_Right,
                            callback=batch_apply_soundtype,
                        )

                    dpg.add_button(
                        label="Groups from Files",
                        callback=batch_groups_from_files,
                    )

            with dpg.child_window(
                width=-1,
                height=560,
                resizable_x=True,
                autosize_y=True,
            ):
                with dpg.group(horizontal=True):
                    dpg.add_combo(
                        [str(st) for st in SoundType],
                        callback=on_soundtype_changed,
                        tag=f"{tag}_soundtype",
                    )
                    dpg.add_input_text(
                        label="Name",
                        callback=on_name_changed,
                        tag=f"{tag}_name",
                    )

                add_node_widget(
                    lambda f: query_nodes(actormixers, f),
                    "ActorMixer",
                    make_setter("actormixer", lambda n: n.id),
                    tag=f"{tag}_actormixer",
                )

                dpg.add_combo(
                    [p.name for p in PlaybackMode],
                    label="Playback Mode",
                    callback=make_setter("playback_mode", lambda v: PlaybackMode[v]),
                    tag=f"{tag}_playbackmode",
                )
                dpg.add_combo(
                    [r.name for r in RandomMode],
                    label="Randomization",
                    callback=make_setter("randomization", lambda v: RandomMode[v]),
                    tag=f"{tag}_randomization",
                )

                with dpg.tree_node(label="Properties"):
                    add_properties_table(
                        {},
                        make_setter("properties"),
                        label=None,
                        tag=f"{tag}_properties",
                    )

                with dpg.group():
                    add_filepaths_table(
                        [],
                        make_setter("soundfiles"),
                        on_select=lambda p: player.set_file(p),
                        filetypes={"Wave (.wav)": "*.wav", "WEM (.wem)": "*.wem"},
                        show_clear=True,
                        label="Sound Files",
                        tag=f"{tag}_soundfiles",
                    )
                    player = add_wav_player(
                        None,
                        label="Preview",
                        allow_change_file=False,
                        height=50,
                        tag=f"{tag}_player",
                    )

        dpg.add_separator()
        dpg.add_text(show=False, tag=f"{tag}_notification", color=style.red)

        with dpg.group(horizontal=True):
            dpg.add_button(
                label="For the Horde!", callback=on_okay, tag=f"{tag}_button_okay"
            )

    groups.append(BatchGroup(new_group_name(), properties={PropID.Volume: -3.0}))
    select_group(0)
    return tag

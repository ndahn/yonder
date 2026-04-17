from typing import Any, Callable
import re
from pathlib import Path
from dataclasses import dataclass, field
import shutil
from dearpygui import dearpygui as dpg

from yonder import Soundbank, calc_hash
from yonder.convenience import create_simple_sound
from yonder.types import Event, ActorMixer
from yonder.query import query_nodes
from yonder.enums import PropID, RandomMode, PlaybackMode, SoundType
from yonder.util import logger
from yonder.wem import wav2wem
from yonder.gui.localization import AutoStr, dpg_translate
from yonder.gui import style
from yonder.gui.config import get_config
from yonder.gui.widgets import (
    add_widget_table,
    add_properties_table,
    add_player_table_compact,
    add_node_reference,
)
from .file_dialog import open_multiple_dialog


@dataclass
class BatchGroup:
    name: str = None
    actormixer: int = 0
    soundtype: SoundType = SoundType.Sfx
    playback_mode: PlaybackMode = PlaybackMode.Random
    random_mode: RandomMode = RandomMode.Standard
    properties: dict[PropID, float] = field(default_factory=dict)
    soundfiles: list[Path] = field(default_factory=list)


def create_batch_sound_builder_dialog(
    bnk: Soundbank,
    callback: Callable[[Event, Event], None],
    *,
    title: str = AutoStr("Batch Sound Builder", "title", "batch_sound_dialog"),
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

    def new_group_name(group_idx: int = None) -> str:
        if group_idx is None:
            group_idx = len(groups)

        if bnk.name:
            parts = re.split(r"c(?=\d{4})")
            if parts[0] != bnk.name:
                base_id = int(parts[-1]) * 10**6 + 10000 + group_idx
                return f"{base_id:09}"

        return f"{(group_idx + 1) * 1000:09}"

    def make_name(prefix: str, soundtype: SoundType, name: int | str) -> str:
        ret = prefix or "" + soundtype.value

        if isinstance(name, str) and name.isnumeric():
            name = int(name)

        if isinstance(name, int):
            name = f"{name:09d}"

        return ret + name

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

        if re.match(rf"[{SoundType.values()}]\d+", name):
            g.soundtype = Soundbank(name[0])
            dpg.set_value(f"{tag}_soundtype", str(g.soundtype))
            name = name[1:]

        if not name.isnumeric():
            show_message(
                AutoStr(
                    "Name has non-standard format", "msg_bad_name", "batch_sound_dialog"
                ),
                color=style.yellow,
            )
        else:
            show_message()

        g.name = name.strip()

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
        dpg.set_value(f"{tag}_random_mode", str(g.random_mode))

        # Custom widgets
        w_actormixer.selected_node = g.actormixer
        dpg.set_value(f"{tag}_properties", g.properties)  # TODO
        w_soundfiles.set_items(g.soundfiles)

    # === Batch Operations ==========

    def batch_apply_soundtype() -> None:
        choice = dpg.get_value(f"{tag}_batch_soundtype")
        soundtype = soundtype_choice_to_enum(choice)
        for g in groups:
            g.soundtype = soundtype

        dpg.set_value(f"{tag}_soundtype", str(soundtype))

    def batch_groups_from_files() -> None:
        ret = open_multiple_dialog(
            title=AutoStr("Select Audio Files", "select_audio_files"),
            filetypes={
                AutoStr("Wave (.wav)", "filetype_wav"): "*.wav",
                AutoStr("WEM (.wem)", "filetype_wem"): "*.wem",
            },
        )

        if ret:
            choice = dpg.get_value(f"{tag}_batch_soundtype")
            soundtype = soundtype_choice_to_enum(choice)
            for f in ret:
                g = BatchGroup(new_group_name(), soundtype=soundtype, soundfiles=[f])
                groups.append(g)
                w_groups.append(g)

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
        if not groups:
            show_message(
                AutoStr("No groups defined", "msg_no_groups", "batch_sound_dialog")
            )
            return

        names_seen: set[str] = set()

        # Verify all groups are valid
        if not groups[0].actormixer:
            show_message(
                AutoStr(
                    "ActorMixer of first group cannot be empty",
                    "msg_first_actormixer_empty",
                    "batch_sound_dialog",
                )
            )
            return

        for idx, g in enumerate(groups):
            if not g.soundfiles:
                show_message(
                    AutoStr(
                        "Group {name} has no files",
                        "msg_empty_group",
                        "batch_sound_dialog",
                        name=g.name,
                    )
                )
                continue

            for idx, f in enumerate(g.soundfiles):
                try:
                    int(f.stem)
                except ValueError:
                    # rename files with non-int names using calc_hash
                    new_file = f.parent / (str(calc_hash(f.stem)) + f.suffix)
                    shutil.copy(str(f), str(new_file))
                    logger.info(
                        AutoStr(
                            "Renamed {old_name} to {new_name}",
                            "renamed_file",
                            old_name=f.name,
                            new_name=new_file.name,
                        )
                    )
                    g.soundfiles[idx] = new_file

            if g.name:
                if make_name("Play_", g.soundtype, g.name) in bnk:
                    show_message(
                        AutoStr(
                            "Group {name} already exists in soundbank",
                            "msg_event_exists",
                            "batch_sound_dialog",
                            name=g.name,
                        )
                    )
                    return
            else:
                sound_id = int(g.soundfiles[0].stem)
                while True:
                    name = make_name("Play_", g.soundtype, sound_id)
                    if name not in bnk and name not in names_seen:
                        break

                    sound_id += 1

                g.name = str(sound_id)
                logger.info(
                    AutoStr(
                        "Group {idx} has been assigned name {name}",
                        "msg_group_autoname",
                        "batch_sound_dialog",
                        idx=idx,
                        name=name,
                    )
                )

            names_seen.add(g.name)

        # Check for duplicate names
        for g in groups:
            if g.name in names_seen:
                show_message(
                    AutoStr(
                        "Duplicate group {name}",
                        "msg_duplicate_group",
                        "batch_sound_dialog",
                    )
                )
                return

        # Convert wavs to wems
        all_waves = []
        for g in groups:
            all_waves.extend([f for f in g.soundfiles if f.suffix.lower() == ".wav"])
        if all_waves:
            logger.info(
                AutoStr(
                    "Converting {num} wave files to wem",
                    "convert_waves",
                    num=len(all_waves),
                )
            )
            wwise = get_config().locate_wwise()
            converted = wav2wem(wwise, all_waves)
            stem2wem = {w.stem: w for w in converted}
            for g in groups:
                g.soundfiles = [stem2wem.get(f.stem, f) for f in g.soundfiles]

        # Create the sound events
        created_pairs: list[tuple[Event, Event]] = []
        for idx, g in enumerate(groups):
            amx = g.actormixer
            if amx == 0:
                amx = groups[0].actormixer

            (play_evt, stop_evt), _, _ = create_simple_sound(
                bnk,
                make_name("", g.soundtype, g.name),
                g.soundfiles,
                amx,
                playback_mode=g.playback_mode,
                random_mode=g.random_mode,
                properties=g.properties,
            )
            created_pairs.append((play_evt, stop_evt))

        if callback:
            callback(created_pairs)

        show_message(AutoStr("Yay!", "yay"), color=style.blue)
        dpg.set_item_label(f"{tag}_button_okay", "Again?")

    # === GUI Content =============

    with dpg.window(
        label=title,
        width=1020,
        height=620,
        autosize=False,
        no_saved_settings=True,
        tag=tag,
        on_close=lambda: dpg.delete_item(window),
    ) as window:
        with dpg.group(horizontal=True):
            with dpg.child_window(
                width=320, height=560, auto_resize_x=True, auto_resize_y=True
            ):
                w_groups = add_widget_table(
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
                autosize_x=True,
                auto_resize_y=True,
            ):
                with dpg.group(horizontal=True):
                    dpg.add_combo(
                        [str(st) for st in SoundType],
                        callback=on_soundtype_changed,
                        tag=f"{tag}_soundtype",
                    )
                    dpg.add_input_text(
                        label="Name",
                        hint=AutoStr(
                            "Leave empty to generate from first audio file",
                            "empty_name_hint",
                            "batch_sound_dialog",
                        ),
                        callback=on_name_changed,
                        tag=f"{tag}_name",
                    )

                w_actormixer = add_node_reference(
                    lambda f: query_nodes(actormixers, f),
                    "ActorMixer",
                    make_setter("actormixer", lambda n: n.id),
                    tag=f"{tag}_actormixer",
                )

                dpg.add_combo(
                    [p.name for p in PlaybackMode],
                    label="Playback Mode",
                    callback=make_setter("playback_mode", lambda v: PlaybackMode[v]),
                    tag=f"{tag}_playback_mode",
                )
                dpg.add_combo(
                    [r.name for r in RandomMode],
                    label="Random Mode",
                    callback=make_setter("random_mode", lambda v: RandomMode[v]),
                    tag=f"{tag}_random_mode",
                )

                with dpg.tree_node(label="Properties"):
                    w_properties = add_properties_table(
                        {},
                        make_setter("properties"),
                        label=None,
                        tag=f"{tag}_properties",
                    )

                with dpg.group():
                    w_soundfiles = add_player_table_compact(
                        [],
                        make_setter("soundfiles"),
                        label="Sound Files",
                        add_item_label=AutoStr("+ Add Sound", "add_sound"),
                        show_clear=True,
                    )

        dpg.add_separator()
        dpg.add_text(show=False, tag=f"{tag}_notification", color=style.red)

        with dpg.group(horizontal=True):
            dpg.add_button(
                label="For the Horde!",
                callback=on_okay,
                tag=f"{tag}_button_okay",
            )

    groups.append(BatchGroup(new_group_name(), properties={PropID.Volume: -3.0}))
    select_group(0)

    dpg_translate(tag, "batch_sound_dialog")
    return tag

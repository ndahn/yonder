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
from yonder.gui.localization import translate as t
from yonder.gui import style
from yonder.gui.config import get_config
from yonder.gui.widgets import (
    add_widget_table,
    add_properties_table,
    add_player_table_compact,
    add_node_reference,
)
from .dialog import Dialog
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


class create_batch_sound_builder_dialog(Dialog):
    def __init__(
        self,
        bnk: Soundbank,
        callback: Callable[[Event, Event], None],
        default_value: list[BatchGroup] = None,
        *,
        title: str = "Batch Sound Builder",
        tag: str = None,
    ):
        super().__init__(tag)

        self._bnk = bnk
        self._callback = callback
        self._groups: list[BatchGroup] = []
        self._selected_group: int = 0
        self._actormixers: list[ActorMixer] = list(bnk.query("type=ActorMixer"))
        self._title = title

        self._w_groups = None
        self._w_actormixer = None
        self._w_soundfiles = None
        self._w_properties = None

        if default_value:
            self._groups = default_value
        else:
            self._groups.append(
                BatchGroup(self._new_group_name(), properties={PropID.Volume: -3.0})
            )

        self._build()
        self.select_group(0)

    # === Helpers =====================

    def _soundtype_choice_to_enum(self, choice: str) -> SoundType:
        val = re.findall(r"\((\w)\)", choice)[0]
        return SoundType(val)

    def _new_group_name(self, group_idx: int = None) -> str:
        if group_idx is None:
            group_idx = len(self._groups)

        if self._bnk.name:
            parts = re.split(r"c(?=\d{4})")
            if parts[0] != self._bnk.name:
                base_id = int(parts[-1]) * 10**6 + 10000 + group_idx
                return f"{base_id:09}"

        return f"{(group_idx + 1) * 1000:09}"

    def _make_name(self, prefix: str, soundtype: SoundType, name: int | str) -> str:
        ret = prefix or "" + soundtype.value

        if isinstance(name, str) and name.isnumeric():
            name = int(name)

        if isinstance(name, int):
            name = f"{name:09d}"

        return ret + name

    def _make_setter(
        self, key: str, transformer: Callable[[Any], Any] = None
    ) -> Callable:
        def setter(sender: str, val: Any, user_data: Any) -> None:
            if transformer:
                val = transformer(val)
            setattr(self._groups[self._selected_group], key, val)

        return setter

    # === Value Updates ===============

    def _on_soundtype_changed(self, sender: str, choice: str, user_data: Any) -> None:
        g = self._groups[self._selected_group]
        g.soundtype = self._soundtype_choice_to_enum(choice)

        old_name = dpg.get_value(self._t("name"))
        if re.match(rf"[{SoundType.values()}]\d+", old_name):
            new_name = g.soundtype.value + old_name[1:]
            dpg.set_value(self._t("name"), new_name)

    def _on_name_changed(self, sender: str, name: str, user_data: Any) -> None:
        g = self._groups[self._selected_group]

        if re.match(rf"[{SoundType.values()}]\d+", name):
            g.soundtype = Soundbank(name[0])
            dpg.set_value(self._t("soundtype"), str(g.soundtype))
            name = name[1:]

        if not name.isnumeric():
            self._show_message(
                t("Name has non-standard format", "batch_sound_dialog/msg_bad_name"),
                color=style.yellow,
            )
        else:
            self._show_message()

        g.name = name.strip()

    # === Table Management ===============

    def _group_to_row(self, group: BatchGroup, idx: int) -> None:
        name = f"{group.soundtype.value}{group.name}"
        dpg.add_text(name)

    def select_group(self, idx: int) -> None:
        self._selected_group = idx
        g = self._groups[idx]

        # Standard widgets
        dpg.set_value(self._t("name"), g.name)
        dpg.set_value(self._t("soundtype"), str(g.soundtype))
        dpg.set_value(self._t("playback_mode"), str(g.playback_mode))
        dpg.set_value(self._t("random_mode"), str(g.random_mode))

        # Custom widgets
        self._w_actormixer.selected_node = g.actormixer
        self._w_properties.properties = g.properties
        self._w_soundfiles.audiofiles = g.soundfiles

    # === Batch Operations ==========

    def _batch_apply_soundtype(self) -> None:
        choice = dpg.get_value(self._t("batch_sound_builder/batch_soundtype"))
        soundtype = self._soundtype_choice_to_enum(choice)
        for g in self._groups:
            g.soundtype = soundtype

        dpg.set_value(self._t("soundtype"), str(soundtype))

    def _batch_groups_from_files(self) -> None:
        ret = open_multiple_dialog(
            title=t("Select Audio Files", "select_audio_files"),
            filetypes={
                t("Wave (.wav)", "filetype_wav"): "*.wav",
                t("WEM (.wem)", "filetype_wem"): "*.wem",
            },
        )

        if ret:
            choice = dpg.get_value(self._t("batch_sound_builder/batch_soundtype"))
            soundtype = self.selfsoundtype_choice_to_enum(choice)
            for f in ret:
                g = BatchGroup(
                    self._new_group_name(), soundtype=soundtype, soundfiles=[f]
                )
                self._groups.append(g)
                self._w_groups.append(g)

    # === User Things ===============

    def _show_message(
        self, msg: str = None, color: tuple[int, int, int, int] = style.red
    ) -> None:
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
        if not self._groups:
            self._show_message(
                t("No groups defined", "batch_sound_dialog/msg_no_groups")
            )
            return

        names_seen: set[str] = set()

        # Verify all groups are valid
        if not self._groups[0].actormixer:
            self._show_message(
                t(
                    "ActorMixer of first group cannot be empty",
                    "batch_sound_dialog/msg_first_actormixer_empty",
                )
            )
            return

        for idx, g in enumerate(self._groups):
            if not g.soundfiles:
                self._show_message(
                    t(
                        "Group {name} has no files",
                        "batch_sound_dialog/msg_empty_group",
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
                        t(
                            "Renamed {old_name} to {new_name}",
                            "renamed_file",
                            old_name=f.name,
                            new_name=new_file.name,
                        )
                    )
                    g.soundfiles[idx] = new_file

            if g.name:
                if self._make_name("Play_", g.soundtype, g.name) in self._bnk:
                    self._show_message(
                        t(
                            "Group {name} already exists in soundbank",
                            "batch_sound_dialog/msg_event_exists",
                            name=g.name,
                        )
                    )
                    return
            else:
                sound_id = int(g.soundfiles[0].stem)
                while True:
                    name = self._make_name("Play_", g.soundtype, sound_id)
                    if name not in self._bnk and name not in names_seen:
                        break

                    sound_id += 1

                g.name = str(sound_id)
                logger.info(
                    t(
                        "Group {idx} has been assigned name {name}",
                        "batch_sound_dialog/msg_group_autoname",
                        idx=idx,
                        name=name,
                    )
                )

            names_seen.add(g.name)

        # Check for duplicate names
        for g in self._groups:
            if g.name in names_seen:
                self._show_message(
                    t(
                        "Duplicate group {name}",
                        "batch_sound_dialog/msg_duplicate_group",
                    )
                )
                return

        # Convert wavs to wems
        all_waves = []
        for g in self._groups:
            all_waves.extend([f for f in g.soundfiles if f.suffix.lower() == ".wav"])
        if all_waves:
            logger.info(
                t(
                    "Converting {num} wave files to wem",
                    "convert_waves",
                    num=len(all_waves),
                )
            )
            wwise = get_config().locate_wwise()
            converted = wav2wem(wwise, all_waves)
            stem2wem = {w.stem: w for w in converted}
            for g in self._groups:
                g.soundfiles = [stem2wem.get(f.stem, f) for f in g.soundfiles]

        # Create the sound events
        created_pairs: list[tuple[Event, Event]] = []
        for idx, g in enumerate(self._groups):
            amx = g.actormixer
            if amx == 0:
                amx = self._groups[0].actormixer

            (play_evt, stop_evt), _, _ = create_simple_sound(
                self._bnk,
                self._make_name("", g.soundtype, g.name),
                g.soundfiles,
                amx,
                playback_mode=g.playback_mode,
                random_mode=g.random_mode,
                properties=g.properties,
            )
            created_pairs.append((play_evt, stop_evt))

        if self._callback:
            self._callback(created_pairs)

        self._show_message(t("Yay!", "yay"), color=style.blue)
        dpg.set_item_label(
            self._t("batch_sound_builder/button_okay"), t("Again?", "button_again")
        )

    # === GUI Content =============
    def _build(self):
        with dpg.window(
            label=self._title,
            width=1020,
            height=620,
            autosize=False,
            no_saved_settings=True,
            tag=self.tag,
            on_close=lambda: dpg.delete_item(window),
        ) as window:
            with dpg.group(horizontal=True):
                with dpg.child_window(
                    width=320, height=560, auto_resize_x=True, auto_resize_y=True
                ):
                    self._w_groups = add_widget_table(
                        self._groups,
                        self._group_to_row,
                        new_item=lambda cb: cb(BatchGroup(self._new_group_name())),
                        on_add=lambda s, a, u: self._groups.append(a[1]),
                        on_remove=lambda s, a, u: self._groups.pop(a[0]),
                        on_select=lambda s, a, u: self.select_group(a[0]),
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
                                tag=self._t("batch_sound_builder/batch_soundtype"),
                            )
                            dpg.add_button(
                                arrow=True,
                                direction=dpg.mvDir_Right,
                                callback=self._batch_apply_soundtype,
                            )

                        dpg.add_button(
                            label="Groups from Files",
                            callback=self._batch_groups_from_files,
                            tag=self._t("batch_sound_builder/groups_from_files"),
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
                            callback=self._on_soundtype_changed,
                            tag=self._t("soundtype"),
                        )
                        dpg.add_input_text(
                            label="Name",
                            hint=t(
                                "Leave empty to generate from first audio file",
                                "batch_sound_dialog/empty_name_hint",
                            ),
                            callback=self._on_name_changed,
                            tag=self._t("name"),
                        )

                    self._w_actormixer = add_node_reference(
                        lambda f: query_nodes(self._actormixers, f),
                        "ActorMixer",
                        self._make_setter("actormixer", lambda n: n.id),
                        tag=self._t("actormixer"),
                    )

                    dpg.add_combo(
                        [p.name for p in PlaybackMode],
                        label="Playback Mode",
                        callback=self._make_setter(
                            "playback_mode", lambda v: PlaybackMode[v]
                        ),
                        tag=self._t("playback_mode"),
                    )
                    dpg.add_combo(
                        [r.name for r in RandomMode],
                        label="Random Mode",
                        callback=self._make_setter(
                            "random_mode", lambda v: RandomMode[v]
                        ),
                        tag=self._t("random_mode"),
                    )

                    with dpg.tree_node(label="Properties"):
                        self._w_properties = add_properties_table(
                            {},
                            self._make_setter("properties"),
                            label=None,
                            tag=self._t("properties"),
                        )

                    with dpg.group():
                        self._w_soundfiles = add_player_table_compact(
                            [],
                            self._make_setter("soundfiles"),
                            label="Sound Files",
                            add_item_label=t("+ Add Sound", "add_sound"),
                            show_clear=True,
                        )

            dpg.add_separator()
            dpg.add_text(show=False, tag=self._t("notification"), color=style.red)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="For the Horde!",
                    callback=self._on_okay,
                    tag=self._t("batch_sound_builder/button_okay"),
                )

    @property
    def groups(self) -> list[BatchGroup]:
        return self._groups

    @groups.setter
    def groups(self, value: list[BatchGroup]):
        self._groups = value

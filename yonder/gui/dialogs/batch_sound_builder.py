from typing import Any, Callable
import re
from pathlib import Path
from dataclasses import dataclass, field
import shutil
from dearpygui import dearpygui as dpg

from yonder import Soundbank, Hash, calc_hash
from yonder.convenience import create_simple_sound
from yonder.types import Event, ActorMixer
from yonder.query import query_nodes
from yonder.enums import PropID, RandomMode, PlaybackMode, SoundType
from yonder.util import logger
from yonder.wem import wav2wem
from yonder.gui import style
from yonder.gui.helpers import dpg_section
from yonder.gui.localization import µ
from yonder.gui.config import get_config
from yonder.gui.widgets import (
    DpgItem,
    add_widget_table,
    add_properties_table,
    add_player_table_compact,
    add_node_reference,
    add_paragraphs,
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


class create_batch_sound_builder_dialog(DpgItem):
    def __init__(
        self,
        bnk: Soundbank,
        callback: Callable[[list[tuple[Event, Event]]], None],
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

        self._w_groups: add_widget_table = None
        self._w_actormixer: add_node_reference = None
        self._w_soundfiles: add_player_table_compact = None
        self._w_properties: add_properties_table = None

        if default_value:
            self._groups = default_value
        else:
            self._groups.append(BatchGroup(self._new_group_name()))

        self._build()
        self.select_group(0)
        self._w_groups.select(0)

    # === Helpers =====================

    def _soundtype_choice_to_enum(self, choice: str) -> SoundType:
        val = re.findall(r"\((\w)\)", choice)[0]
        return SoundType(val)

    def _new_group_name(self, group_idx: int = None) -> str:
        if group_idx is None:
            group_idx = len(self._groups)

        if self._bnk.name:
            parts = re.split(r"c(?=\d{4})", self._bnk.name)
            if parts[0] != self._bnk.name:
                base_id = int(parts[-1]) * 10**6 + 10000 + group_idx
                return f"{base_id:09}"

        return f"{(group_idx + 1) * 1000:09}"

    def _make_name(self, prefix: str, soundtype: SoundType, name: Hash) -> str:
        ret = (prefix or "") + soundtype.value

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

        # If the name starts with a sound-type letter, parse and strip it
        if re.match(rf"[{SoundType.values()}]\d+", name):
            g.soundtype = SoundType(name[0])
            dpg.set_value(self._t("soundtype"), str(g.soundtype))
            name = name[1:]

        name = name.strip()

        if not name.isnumeric():
            self.show_message(
                µ("Name has non-standard format", "msg"),
                color=style.yellow,
            )
        else:
            self.show_message()

        g.name = name
        self._w_groups.refresh()

    def _on_soundfiles_changed(
        self, sender: str, soundfiles: list[Path], user_data: Any
    ) -> None:
        g = self._groups[self._selected_group]
        g.soundfiles = soundfiles
        self._w_groups.refresh()

    # === Table Management ===============

    def _group_to_row(self, group: BatchGroup, idx: int) -> None:
        name = f"{group.soundtype.value}{group.name or '?'}"
        file_count = len(group.soundfiles)
        # Show name and a brief file count hint
        dpg.add_text(name)
        dpg.add_text(
            f"({file_count})",
            color=style.light_grey if file_count else style.red,
        )

    def select_group(self, idx: int) -> None:
        self._selected_group = idx
        g = self._groups[idx]

        dpg.set_value(
            self._t("group_label"),
            µ("Group {idx}: {name}").format(idx=idx, name=g.name),
        )
        dpg.set_value(self._t("name"), g.name or "")
        dpg.set_value(self._t("soundtype"), str(g.soundtype))
        dpg.set_value(self._t("playback_mode"), str(g.playback_mode))
        dpg.set_value(self._t("random_mode"), str(g.random_mode))

        self._w_actormixer.selected_node = g.actormixer
        self._w_properties.properties = g.properties
        self._w_soundfiles.audiofiles = g.soundfiles

        if g.soundfiles:
            self._w_soundfiles.select(0)
        else:
            self._w_soundfiles.select(None)

    # === Batch Operations ==========

    def _batch_apply_soundtype(self) -> None:
        choice = dpg.get_value(self._t("batch_sound_builder/batch_soundtype"))
        soundtype = self._soundtype_choice_to_enum(choice)
        for g in self._groups:
            g.soundtype = soundtype

        dpg.set_value(self._t("soundtype"), str(soundtype))
        # Refresh the group list so display names update
        self._w_groups.refresh()

    def _batch_groups_from_files(self) -> None:
        ret = open_multiple_dialog(
            title=µ("Select Audio Files"),
            filetypes={
                µ("Audio Files (.wav, .wem)", "filetypes"): ["*.wav", "*.wem"],
                µ("Wave (.wav)", "filetypes"): "*.wav",
                µ("WEM (.wem)", "filetypes"): "*.wem",
            },
        )

        if not ret:
            return

        choice = dpg.get_value(self._t("batch_sound_builder/batch_soundtype"))
        soundtype = self._soundtype_choice_to_enum(choice)
        for f in ret:
            g = BatchGroup(self._new_group_name(), soundtype=soundtype, soundfiles=[f])
            self._w_groups.append(g)
            self._groups.append(g)

    # === User Things ===============

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

    def _on_okay(self) -> None:
        if not self._groups:
            self.show_message(µ("No groups defined", "msg"))
            return

        if not self._groups[0].actormixer:
            self.show_message(µ("ActorMixer of first group cannot be empty", "msg"))
            return

        names_seen: set[str] = set()

        for idx, g in enumerate(self._groups):
            if not g.soundfiles:
                self.show_message(
                    µ("Group {name} has no files", "msg").format(name=g.name)
                )
                return

            # Rename files whose stems are not integers using calc_hash
            for file_idx, f in enumerate(g.soundfiles):
                try:
                    int(f.stem)
                except ValueError:
                    new_file = f.parent / (str(calc_hash(f.stem)) + f.suffix)
                    shutil.copy(str(f), str(new_file))
                    logger.info(f"Renamed {f.name} to {new_file.name}")
                    g.soundfiles[file_idx] = new_file

            if g.name:
                event_name = self._make_name("Play_", g.soundtype, g.name)
                if event_name in self._bnk:
                    self.show_message(
                        µ("Group {name} already exists in soundbank", "msg").format(
                            name=g.name
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
                logger.info(f"Group {idx} assigned name {name}")

            if g.name in names_seen:
                self.show_message(
                    µ("Duplicate group {name}", "msg").format(name=g.name)
                )
                return

            names_seen.add(g.name)

        # Convert wavs to wems
        all_waves = [
            f for g in self._groups for f in g.soundfiles if f.suffix.lower() == ".wav"
        ]
        if all_waves:
            wwise = get_config().locate_wwise()
            converted = wav2wem(wwise, all_waves)
            stem2wem = {w.stem: w for w in converted}
            for g in self._groups:
                g.soundfiles = [stem2wem.get(f.stem, f) for f in g.soundfiles]

        # Create sound events
        created_pairs: list[tuple[Event, Event]] = []
        for g in self._groups:
            amx = g.actormixer or self._groups[0].actormixer

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

        self.show_message(µ("Yay!", "msg"), color=style.blue)
        dpg.set_item_label(self._t("batch_sound_builder/button_okay"), µ("Again?"))

    # === GUI Content =============
    def _build(self):
        with dpg.window(
            label=self._title,
            width=920,
            height=670,
            autosize=False,
            no_saved_settings=True,
            tag=self.tag,
            on_close=lambda: dpg.delete_item(self.tag),
        ):
            with dpg.group(horizontal=True):
                # Left panel: group list + bulk ops
                with dpg.child_window(
                    width=260, height=500, auto_resize_x=False, auto_resize_y=True
                ):
                    dpg_section(µ("Groups"), color=style.muted_orange, spacer=0)
                    self._w_groups = add_widget_table(
                        self._groups,
                        self._group_to_row,
                        new_item=lambda cb: cb(BatchGroup(self._new_group_name())),
                        on_add=lambda s, a, u: self._groups.append(a[1]),
                        on_remove=lambda s, a, u: self._groups.pop(a[0]),
                        on_select=lambda s, a, u: self.select_group(a[0]),
                        selected_row_color=style.muted_orange,
                        height=300,
                        add_item_label=µ("Add Group"),
                        columns=[µ("Name"), µ("Files")],
                        header_row=True,
                    )

                    dpg_section(µ("Bulk Operations"), color=style.muted_purple, spacer=0)
                    with dpg.group(horizontal=True):
                        dpg.add_combo(
                            [str(st) for st in SoundType],
                            default_value=str(SoundType.Sfx),
                            tag=self._t("batch_sound_builder/batch_soundtype"),
                            width=140,
                        )
                        dpg.add_button(
                            label=µ("Apply"),
                            callback=self._batch_apply_soundtype,
                        )

                    dpg.add_button(
                        label=µ("Groups from Files", "button"),
                        callback=self._batch_groups_from_files,
                        tag=self._t("batch_sound_builder/groups_from_files"),
                    )

                # Right panel: per-group settings
                with dpg.child_window(
                    width=-1,
                    height=500,
                    auto_resize_y=True,
                ):
                    dpg_section(
                        "",
                        color=style.muted_blue,
                        spacer=0,
                        tag=self._t("group_label"),
                    )

                    # Name + type on one row
                    with dpg.group(horizontal=True):
                        dpg.add_combo(
                            [str(st) for st in SoundType],
                            default_value=str(SoundType.Sfx),
                            callback=self._on_soundtype_changed,
                            tag=self._t("soundtype"),
                            width=120,
                        )
                        dpg.add_input_text(
                            label=µ("Name"),
                            hint=µ("Leave empty to generate from first audio file"),
                            callback=self._on_name_changed,
                            tag=self._t("name"),
                            width=192,
                        )

                    dpg.add_spacer(height=4)

                    self._w_actormixer = add_node_reference(
                        lambda f: query_nodes(self._actormixers, f),
                        "ActorMixer",
                        self._make_setter("actormixer", lambda n: n.id),
                        tag=self._t("actormixer"),
                    )

                    dpg.add_combo(
                        [p.name for p in PlaybackMode],
                        label=µ("Playback Mode"),
                        callback=self._make_setter(
                            "playback_mode", lambda v: PlaybackMode[v]
                        ),
                        tag=self._t("playback_mode"),
                        width=160,
                    )
                    dpg.add_combo(
                        [r.name for r in RandomMode],
                        label=µ("Random Mode"),
                        callback=self._make_setter(
                            "random_mode", lambda v: RandomMode[v]
                        ),
                        tag=self._t("random_mode"),
                        width=160,
                    )

                    dpg.add_spacer(height=4)

                    with dpg.tree_node(label=µ("Properties")):
                        self._w_properties = add_properties_table(
                            {},
                            self._make_setter("properties"),
                            label=None,
                            tag=self._t("properties"),
                        )

                    dpg.add_spacer(height=4)

                    self._w_soundfiles = add_player_table_compact(
                        [],
                        self._on_soundfiles_changed,
                        label=µ("Sound Files"),
                        add_item_label=µ("+ Add Sounds"),
                        selected_row_color=style.muted_blue,
                        show_clear=True,
                    )

            dpg.add_separator()
            add_paragraphs(
                µ(
                    """\
                        - Quickly build many simple sounds
                        - Each group will have a play/stop event
                        - Will use ActorMixer of first group if not specified
                    """,
                    "tips",
                ),
                color=style.light_blue,
            )

            dpg.add_separator()
            dpg.add_spacer(height=2)
            dpg.add_text(show=False, tag=self._t("notification"), color=style.red)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label=µ("For the Horde!", "button"),
                    callback=self._on_okay,
                    tag=self._t("batch_sound_builder/button_okay"),
                )

    @property
    def groups(self) -> list[BatchGroup]:
        return self._groups

    @groups.setter
    def groups(self, value: list[BatchGroup]):
        self._groups = value

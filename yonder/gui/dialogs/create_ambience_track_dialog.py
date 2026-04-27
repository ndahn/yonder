from __future__ import annotations
from typing import Any, Callable
from pathlib import Path
from dataclasses import dataclass, field
from dearpygui import dearpygui as dpg

from yonder import Soundbank, HIRCNode
from yonder.hash import lookup_name, calc_hash
from yonder.types import MusicSwitchContainer
from yonder.convenience import create_ambience
from yonder.wem import wav2wem
from yonder.gui import style
from yonder.gui.localization import µ
from yonder.gui.config import get_config
from yonder.gui.widgets import (
    DpgItem,
    add_node_reference,
    add_paragraphs,
    add_wav_player,
    add_widget_table,
)
from yonder.gui.widgets.node_reference import get_details_musicswitchcontainer
from .edit_state_path_dialog import edit_state_path_dialog
from .file_dialog import open_file_dialog


# === Data model ============================================================


@dataclass
class TrackEntry:
    """One row in the condition grid: a leaf value and one condition per arg.

    ``conditions[arg] = None`` means wildcard for that argument.
    """

    leaf_value: Any = None
    conditions: dict[str, str | None] = field(default_factory=dict)


@dataclass
class DecisionNode:
    """Internal tree node produced by ``build_tree``. Treat as output only.

    Branch nodes: children populated, leaf_value=None.
    Leaf nodes:   leaf_value set, children empty, value may be None (wildcard).
    """

    arg: str = ""
    value: str | None = None
    children: list[DecisionNode] = field(default_factory=list)
    leaf_value: Any = None

    @property
    def is_leaf(self) -> bool:
        return self.leaf_value is not None

    def format_tree(self, indent: int = 0) -> str:
        """Produce a compact text representation of a DecisionNode tree."""
        pad = "  " * indent
        if self.is_leaf:
            name = self.leaf_value.name if self.leaf_value else "<none>"
            return f"{pad} -> {name}\n"

        val = self.value if self.value is not None else _WILDCARD
        head = f"{pad}[{self.arg} = {val}]\n" if self.arg else ""
        return head + "".join(c.format_tree(indent + 1) for c in self.children)


def build_tree(
    entries: list[TrackEntry],
    active_args: list[str],
) -> DecisionNode:
    """Construct a uniform-depth DecisionNode tree from flat TrackEntry rows.

    All leaves sit at depth ``len(active_args)``. Each level groups entries
    by their condition value for that level's arg; None is the wildcard branch.
    """
    root = DecisionNode()

    def _insert(node: DecisionNode, entry: TrackEntry, depth: int) -> None:
        if depth == len(active_args):
            node.children.append(DecisionNode(leaf_value=entry.leaf_value))
            return

        arg = active_args[depth]
        val = entry.conditions.get(arg, _WILDCARD)
        branch = next(
            (c for c in node.children if c.arg == arg and c.value == val), None
        )

        if branch is None:
            branch = DecisionNode(arg=arg, value=val)
            node.children.append(branch)

        _insert(branch, entry, depth + 1)

    for entry in entries:
        _insert(root, entry, 0)

    return root


_WILDCARD = "*"


class create_ambience_track_dialog(DpgItem):
    """Dialog to create a new ambience location.

    Creates a branch in an existing master MusicSwitchContainer and a new
    location MusicSwitchContainer with its own decision tree.

    Parameters
    ----------
    bnk : Soundbank
        Soundbank to modify.
    location_args : dict[str, list[str]]
        States the location may select on and standard values to offer.
    on_created : callable
        Fired as ``on_created(nodes)`` with the new HIRCNodes on success.
    title : str
        Window title.
    tag : str, optional
        Explicit DPG tag.
    """

    def __init__(
        self,
        bnk: Soundbank,
        on_created: Callable[[list[HIRCNode]], None],
        *,
        initial_location_args: list[str] = ("OutdoorIndoor",),
        get_values_for_arg: Callable[[int], list[int]] = None,
        lock_first_arg: bool = True,
        title: str = "New Ambience Location",
        tag: str = None,
    ) -> None:
        super().__init__(tag)

        self.bnk = bnk
        self.location_args = list(initial_location_args or [])
        self.on_created = on_created

        self.msc: MusicSwitchContainer = None
        self.master_state_path: list[str] = []
        self._get_values_for_arg = get_values_for_arg
        self._lock_first_arg = lock_first_arg

        self._track_entries: list[TrackEntry] = []
        self._bgm_tracks: list[Path] = []
        self._loop_infos: list[tuple] = []
        self._trim_infos: list[tuple] = []

        self._build(title)

    # === Helpers ===========================================================

    def _get_master_mscs(self, filt: str) -> list[MusicSwitchContainer]:
        valid_msc_arg_hash = calc_hash("Set_State_EnvPlaceType")
        return list(
            self.bnk.query(
                f"type=MusicSwitchContainer arguments:*/group_id={valid_msc_arg_hash} {filt}"
            )
        )

    def _conditions_summary(self, entry: TrackEntry, join: str = " / ") -> str:
        """One-line summary of which conditions are set for a track entry."""
        active = self.location_args
        parts = [entry.conditions.get(arg, _WILDCARD) for arg in active]
        return join.join(parts)

    def _update_summary(self) -> None:
        tree = build_tree(self._track_entries, self.location_args)
        dpg.set_value(
            self._t("summary_text"), tree.format_tree() or µ("<nothing to see here>")
        )

    def _rebuild_master_tab(self) -> None:
        """Regenerate the per-argument input rows after an MSC change."""
        dpg.delete_item(self._t("master_args_group"), children_only=True)

        if not self.msc:
            return

        self.master_state_path = [_WILDCARD] * len(self.msc.arguments)

        for idx, arg in enumerate(self.msc.arguments):
            name = lookup_name(arg.group_id, f"#{arg.group_id}")
            values = []
            if self._get_values_for_arg:
                values = self._get_values_for_arg(arg.group_id)

            with dpg.group(
                horizontal=True,
                parent=self._t("master_args_group"),
            ):
                dpg.add_input_text(
                    default_value=_WILDCARD,
                    width=160,
                    tag=self._t(f"master_val:{idx}"),
                    callback=self._on_master_val_changed,
                    user_data=idx,
                )
                dpg.add_combo(
                    values,
                    no_preview=True,
                    callback=self._on_master_val_changed,
                    user_data=idx,
                )
                dpg.add_text(name)

    def _rebuild_location_rows(self) -> None:
        """Rebuild the per-track header texts from current active args."""
        for idx, entry in enumerate(self._track_entries):
            tag = self._t(f"track_conditions:{idx}")
            if dpg.does_item_exist(tag):
                dpg.set_item_label(tag, self._conditions_summary(entry))

    # === DPG callbacks =====================================================

    def _on_msc_selected(
        self,
        sender: str,
        selected: int | MusicSwitchContainer,
        user_data: Any,
    ) -> None:
        if isinstance(selected, int):
            selected = self.bnk.get(selected)
        self.msc = selected
        self._rebuild_master_tab()
        dpg.show_item(self._t("master_args_group"))
        self.show_message()

    def _on_master_val_changed(self, sender: str, value: str, idx: int) -> None:
        self.master_state_path[idx] = value
        # keep the input_text in sync when the combo fires
        input_tag = self._t(f"master_val:{idx}")
        if dpg.does_item_exist(input_tag) and sender != input_tag:
            dpg.set_value(input_tag, value)

    def _location_arg_to_row(self, arg: str, idx: int) -> None:
        """Render one location-arg row: input + combo(no_preview) + locked hint."""
        values = self._get_values_for_arg(0) if self._get_values_for_arg else []
        locked = self._lock_first_arg and idx == 0
        with dpg.group(horizontal=True):
            dpg.add_input_text(
                default_value=arg,
                width=200,
                enabled=not locked,
                callback=self._on_location_arg_name_changed,
                user_data=idx,
            )
            dpg.add_combo(
                values,
                no_preview=True,
                enabled=not locked,
                callback=self._on_location_arg_name_changed,
                user_data=idx,
            )

    def _new_location_arg(self, done: Callable[[str], None]) -> None:
        arg = "<empty>"
        self.location_args.append(arg)
        done(arg)

    def _on_location_arg_name_changed(self, sender: str, value: str, idx: int) -> None:
        self.location_args[idx] = value
        self._location_states_table.items[idx] = value

        for entry in self._track_entries:
            entry.conditions.setdefault(value, _WILDCARD)

        self._rebuild_location_rows()
        self._update_summary()

    def _location_branch_to_row(self, entry: TrackEntry, idx: int) -> None:
        label = self._conditions_summary(entry)

        with dpg.tree_node(label=label, tag=self._t(f"track_conditions:{idx}")):
            with dpg.group(horizontal=True):
                dpg.add_text(µ("Track #{idx}").format(idx=idx))
                dpg.add_button(
                    label=µ("State Path", "button"),
                    callback=self._on_edit_conditions,
                    user_data=idx,
                )

            track_path = self._bgm_tracks[idx] if idx < len(self._bgm_tracks) else None
            add_wav_player(
                track_path,
                on_file_changed=self._make_track_changed_cb(idx),
                on_loop_changed=self._make_loop_changed_cb(idx),
                on_trims_changed=self._make_trim_changed_cb(idx),
            )

    def _new_location_branch(self, done: Callable[[TrackEntry], None]) -> None:
        ret = open_file_dialog(
            title="Select Audio File",
            default_file=str(self._audio) if self._audio else None,
            filetypes={µ("Audio Files (.wav, .wem)", "filetypes"): ["*.wav", "*.wem"]},
        )
        if ret:
            done(
                TrackEntry(
                    leaf_value=ret,
                    conditions={a: _WILDCARD for a in self.location_args},
                )
            )

    def _on_add_location_branch(
        self,
        sender: str,
        info: tuple[int, TrackEntry, list[TrackEntry]],
        user_data: Any,
    ) -> None:
        entry = info[1]
        self._track_entries.append(entry)
        self._bgm_tracks.append(entry.leaf_value)
        self._loop_infos.append((0.0, 0.0, False))
        self._trim_infos.append((0.0, 0.0))
        self._update_summary()

    def _on_remove_location_branch(
        self,
        sender: str,
        info: tuple[int, TrackEntry, list[TrackEntry]],
        user_data: Any,
    ) -> None:
        idx = info[0]
        self._track_entries.pop(idx)
        self._bgm_tracks.pop(idx)
        self._loop_infos.pop(idx)
        self._trim_infos.pop(idx)
        self._update_summary()

    def _on_add_location_arg(
        self,
        sender: str,
        info: tuple[int, str, list[str]],
        user_data: Any,
    ) -> None:
        arg = info[1]
        if arg and arg not in self.location_args:
            self.location_args = list(self.location_args) + [arg]
            # seed new key into existing entries so no data is lost
            for entry in self._track_entries:
                entry.conditions.setdefault(arg, _WILDCARD)

        self._rebuild_location_rows()
        self._update_summary()

    def _on_remove_location_arg(
        self,
        sender: str,
        info: tuple[int, str, list[str]],
        user_data: Any,
    ) -> None:
        idx = info[0]
        if self._lock_first_arg and idx == 0:
            return

        self.location_args = [a for i, a in enumerate(self.location_args) if i != idx]
        self._rebuild_location_rows()
        self._update_summary()

    def _on_tracks_changed(
        self,
        sender: str,
        data: tuple[list[Path], list[tuple], list[tuple]],
        user_data: Any,
    ) -> None:
        new_tracks, new_loops, new_trims = data[0], data[1], data[2]

        # grow or shrink _track_entries to match
        while len(self._track_entries) < len(new_tracks):
            self._track_entries.append(
                TrackEntry(
                    leaf_value=new_tracks[len(self._track_entries)],
                    conditions={a: _WILDCARD for a in self.location_args},
                )
            )
        if len(self._track_entries) > len(new_tracks):
            self._track_entries = self._track_entries[: len(new_tracks)]

        # update leaf_value to stay in sync with player table
        for entry, path in zip(self._track_entries, new_tracks):
            entry.leaf_value = path

        self._bgm_tracks = new_tracks
        self._loop_infos = new_loops
        self._trim_infos = new_trims

        self._rebuild_location_rows()
        self._update_summary()

    def _on_loop_changed(
        self, sender: str, data: tuple[int, tuple], user_data: Any
    ) -> None:
        idx, info = data
        self._loop_infos[idx] = info

    def _on_trim_changed(
        self, sender: str, data: tuple[int, tuple], user_data: Any
    ) -> None:
        idx, trim = data
        self._trim_infos[idx] = trim

    def _on_edit_conditions(self, sender: str, app_data: Any, idx: int) -> None:
        """Open the state-path editor for one track entry."""
        entry = self._track_entries[idx]
        active = self.location_args
        # build a synthetic state_path list aligned to the location args
        current_path = [entry.conditions.get(a, _WILDCARD) for a in active]

        def _on_path_selected(_sender: str, state_path: list[str], _ud: Any) -> None:
            for arg, val in zip(active, state_path):
                entry.conditions[arg] = val

            entry.leaf_value = (
                self._bgm_tracks[idx] if idx < len(self._bgm_tracks) else None
            )

            tag = self._t(f"track_conditions:{idx}")
            if dpg.does_item_exist(tag):
                dpg.set_item_label(tag, self._conditions_summary(entry))

            self._update_summary()

        edit_state_path_dialog(
            self.bnk,
            active,
            _on_path_selected,
            state_path=current_path,
            hide_node_id=True,
        )

    def _on_okay(self) -> None:
        if not self.msc:
            self.show_message(µ("Select MusicSwitchContainer first", "msg"))
            return

        if not self._bgm_tracks:
            self.show_message(µ("Add at least one track", "msg"))
            return

        self.show_message()

        # convert .wav → .wem
        waves = [f for f in self._bgm_tracks if f.suffix == ".wav"]
        if waves:
            wwise = get_config().locate_wwise()
            converted = {p.stem: q for p, q in zip(waves, wav2wem(wwise, waves))}
            for entry in self._track_entries:
                if entry.leaf_value and entry.leaf_value.suffix == ".wav":
                    entry.leaf_value = converted.get(
                        entry.leaf_value.stem, entry.leaf_value
                    )
            self._bgm_tracks = [e.leaf_value for e in self._track_entries]

        tree = build_tree(self._track_entries, self.location_args)
        loop_info = [(li[0] * 1000, li[1] * 1000) for li in self._loop_infos]

        # TODO
        nodes = create_ambience(
            self.bnk,
            master_msc=self.msc,
            master_state_path=self.master_state_path,
            location_tree=tree,
            tracks=self._bgm_tracks,
            loop_markers=loop_info,
        )

        if self.on_created:
            self.on_created(nodes)

        self.show_message(µ("Success!", "msg"), color=style.blue)
        dpg.set_item_label(self._t("btn_okay"), µ("Yay!"))
        dpg.set_item_callback(
            self._t("btn_okay"),
            lambda s, a, u: dpg.delete_item(self.tag),
        )

    # === Build =============================================================

    def _build(self, title: str) -> None:
        with dpg.window(
            label=title,
            width=640,
            height=460,
            no_saved_settings=True,
            tag=self.tag,
            on_close=lambda: dpg.delete_item(self.tag),
        ):
            with dpg.tab_bar():
                self._build_tab_master()
                self._build_tab_location()
                self._build_tab_summary()

            dpg.add_spacer(height=2)
            dpg.add_text(
                "",
                tag=self._t("notification"),
                show=False,
                color=style.red,
            )

    def _build_tab_master(self) -> None:
        with dpg.tab(label=µ("Master branch")):
            dpg.add_text(µ("MusicSwitchContainer"))
            add_node_reference(
                self._get_master_mscs,
                "MusicSwitchContainer",
                self._on_msc_selected,
                get_node_details=get_details_musicswitchcontainer,
                node_type=MusicSwitchContainer,
            )

            dpg.add_child_window(
                autosize_x=True,
                auto_resize_y=True,
                tag=self._t("master_args_group"),
                show=False,
            )

            add_paragraphs(
                µ(
                    "Set the state path that selects your ambience",
                    "tips",
                ),
                color=style.light_blue,
            )

    def _build_tab_location(self) -> None:
        with dpg.tab(label=µ("Location tree")):
            with dpg.tree_node(label="Ambience states"):
                self._location_states_table = add_widget_table(
                    list(self.location_args),
                    self._location_arg_to_row,
                    new_item=self._new_location_arg,
                    on_add=self._on_add_location_arg,
                    on_remove=self._on_remove_location_arg,
                    add_item_label=µ("+ Add State"),
                    show_clear=False,
                )

            dpg.add_spacer(height=4)
            add_widget_table(
                [],
                self._location_branch_to_row,
                new_item=self._new_location_branch,
                on_add=self._on_add_location_branch,
                on_remove=self._on_remove_location_branch,
                add_item_label=µ("+ Add Branch"),
                show_clear=True,
            )

    def _build_tab_summary(self) -> None:
        with dpg.tab(label=µ("Summary")):
            add_paragraphs(
                µ("Location decision tree:", "tips"),
            )

            dpg.add_spacer(height=3)
            with dpg.child_window(height=-50):
                dpg.add_text(
                    µ("<nothing to see here>"),
                    tag=self._t("summary_text"),
                    color=style.light_green,
                )

            dpg.add_spacer(height=4)
            dpg.add_button(
                label=µ("Let there be light!", "button"),
                callback=self._on_okay,
                tag=self._t("btn_okay"),
            )

    def _make_track_changed_cb(self, idx: int) -> Callable:
        def cb(sender: str, track: Path, user_data: Any) -> None:
            if track:
                self._bgm_tracks[idx] = track
                self._track_entries[idx].leaf_value = track
                self._update_summary()

        return cb

    def _make_loop_changed_cb(self, idx: int) -> Callable:
        def cb(sender: str, data: tuple, user_data: Any) -> None:
            _, info = data
            if idx < len(self._loop_infos):
                self._loop_infos[idx] = info

        return cb

    def _make_trim_changed_cb(self, idx: int) -> Callable:
        def cb(sender: str, data: tuple, user_data: Any) -> None:
            _, trim = data
            if idx < len(self._trim_infos):
                self._trim_infos[idx] = trim

        return cb

    # === Public ============================================================

    def show_message(self, msg: str = None, color: style.RGBA = style.red) -> None:
        """Show or hide the notification on the Summary tab."""
        tag = self._t("notification")
        if not msg:
            dpg.hide_item(tag)
            return
        dpg.configure_item(tag, default_value=msg, color=color, show=True)

from __future__ import annotations
from typing import Any, Callable
from pathlib import Path
from dearpygui import dearpygui as dpg

from yonder import Soundbank, HIRCNode
from yonder.hash import lookup_name, calc_hash
from yonder.types import MusicSwitchContainer
from yonder.enums import PropID
from yonder.convenience import (
    create_ambience_bgm,
    DecisionNode,
    AmbientBgm,
)
from yonder.game import GameObjects
from yonder.wem import wav2wem
from yonder.gui import style
from yonder.gui.localization import µ
from yonder.gui.config import get_config
from yonder.gui.widgets import (
    DpgItem,
    add_select_node,
    add_paragraphs,
    add_wav_player,
    add_widget_table,
    add_properties_table,
    loading_indicator,
)
from yonder.gui.widgets.select_node import get_details_musicswitchcontainer
from .edit_state_path_dialog import edit_state_path_dialog
from .file_dialog import open_file_dialog


# === Data model ============================================================


def build_tree(
    entries: list[AmbientBgm],
    conditions: list[dict[str, str]],
    active_args: list[str],
) -> DecisionNode:
    """Construct a uniform-depth DecisionNode tree from flat TrackEntry rows.

    All leaves sit at depth ``len(active_args)``. Each level groups entries
    by their condition value for that level's arg; None is the wildcard branch.
    """
    root = DecisionNode()

    def _insert(
        node: DecisionNode,
        entry: AmbientBgm,
        entry_conditions: dict[str, str],
        depth: int,
    ) -> None:
        if depth == len(active_args):
            node.children.append(DecisionNode(leaf_value=entry))
            return

        arg = active_args[depth]
        val = entry_conditions.get(arg, _WILDCARD)
        branch = next(
            (c for c in node.children if c.arg == arg and c.value == val), None
        )

        if branch is None:
            branch = DecisionNode(arg=arg, value=val)
            node.children.append(branch)

        _insert(branch, entry, entry_conditions, depth + 1)

    for entry, cond in zip(entries, conditions):
        _insert(root, entry, cond, 0)

    return root


_WILDCARD = "*"


class create_ambience_bgm_dialog(DpgItem):
    """Dialog to create a new ambience bgm.

    Creates a branch in an existing location MusicSwitchContainer and a new
    ambience MusicSwitchContainer with its own decision tree.

    Parameters
    ----------
    bnk : Soundbank
        Soundbank to modify.
    ambience_args : dict[str, list[str]]
        States the ambience may select on and standard values to offer.
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
        initial_ambience_args: list[str] = ("TimeZone", "FieldBattleState"),
        title: str = "New Ambience Bgm",
        tag: str = None,
    ) -> None:
        super().__init__(tag)

        self.bnk = bnk
        self.ambience_args = list(initial_ambience_args or [])
        self.on_created = on_created

        self.msc: MusicSwitchContainer = None
        self.location_state_path: list[str] = []

        self._bgm_tracks: list[AmbientBgm] = []
        self._state_paths: list[dict[str, str]] = []

        self._build(title)

    # === Helpers ===========================================================

    def _get_location_mscs(self, filt: str) -> list[MusicSwitchContainer]:
        valid_msc_arg_hash = calc_hash("BgmPlaceType")
        return list(
            self.bnk.query(
                f"type=MusicSwitchContainer arguments:*/group_id={valid_msc_arg_hash} {filt}"
            )
        )

    def _conditions_summary(
        self, entry: AmbientBgm, conditions: dict[str, str], join: str = " / "
    ) -> str:
        """One-line summary of which conditions are set for a track entry."""
        parts = [conditions.get(arg, _WILDCARD) for arg in self.ambience_args]
        return join.join(parts)

    def _update_summary(self) -> None:
        location_str = " > ".join(v for v in self.location_state_path if v != "*")
        if not location_str:
            location_str = "<invalid>"

        tree = build_tree(self._bgm_tracks, self._state_paths, self.ambience_args)
        tree_str = tree.format_tree() or µ("<nothing to see here>")

        summary = f"""\
Location selector:
  {location_str}

Ambience tree:
{tree_str}"""

        dpg.set_value(self._t("summary_text"), summary)

    def _get_values_for_arg(self, arg: int | str) -> list[str]:
        if isinstance(arg, int):
            arg = lookup_name(arg, f"#{arg}")

        return ["*"] + GameObjects.GameStates.get(arg, [])

    def _rebuild_location_tab(self) -> None:
        """Regenerate the per-argument input rows after an MSC change."""
        dpg.delete_item(self._t("location_args_group"), children_only=True)

        if not self.msc:
            return

        self.location_state_path = [_WILDCARD] * len(self.msc.arguments)

        for idx, arg in enumerate(self.msc.arguments):
            name = lookup_name(arg.group_id, f"#{arg.group_id}")
            values = self._get_values_for_arg(arg.group_id)

            with dpg.group(
                horizontal=True,
                parent=self._t("location_args_group"),
            ):
                dpg.add_input_text(
                    default_value=_WILDCARD,
                    width=160,
                    tag=self._t(f"location_val:{idx}"),
                    callback=self._on_location_val_changed,
                    user_data=idx,
                )
                dpg.add_combo(
                    values,
                    no_preview=True,
                    callback=self._on_location_val_changed,
                    user_data=idx,
                )
                dpg.add_text(name)

    def _rebuild_ambience_rows(self) -> None:
        """Rebuild the per-track header texts from current active args."""
        for idx, (entry, conditions) in enumerate(
            zip(self._bgm_tracks, self._state_paths)
        ):
            tag = self._t(f"track_conditions:{idx}")
            if dpg.does_item_exist(tag):
                dpg.set_item_label(tag, self._conditions_summary(entry, conditions))

    def _get_default_state_path(self) -> list[str]:
        return {a: _WILDCARD for a in self.ambience_args}

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
        self._rebuild_location_tab()
        dpg.show_item(self._t("location_args_group"))
        self.show_message()

    def _on_location_val_changed(self, sender: str, value: str, idx: int) -> None:
        self.location_state_path[idx] = value
        input_tag = self._t(f"location_val:{idx}")
        if dpg.does_item_exist(input_tag) and sender != input_tag:
            dpg.set_value(input_tag, value)

    def _ambience_arg_to_row(self, arg: str, idx: int) -> None:
        """Render one ambience-arg row: input + combo(no_preview) + locked hint."""
        values = list(GameObjects.GameStates.keys())
        with dpg.group(horizontal=True):
            dpg.add_input_text(
                default_value=arg,
                width=200,
                callback=self._on_ambience_arg_name_changed,
                tag=self._t(f"ambience_state:{idx}"),
                user_data=idx,
            )
            dpg.add_combo(
                values,
                no_preview=True,
                callback=self._on_ambience_arg_name_changed,
                tag=self._t(f"ambience_state_combo:{idx}"),
                user_data=idx,
            )

    def _new_ambience_arg(self, done: Callable[[str], None]) -> None:
        arg = "<empty>"
        self.ambience_args.append(arg)
        done(arg)

    def _on_ambience_arg_name_changed(self, sender: str, value: str, idx: int) -> None:
        self.ambience_args[idx] = value
        self._ambience_states_table.items[idx] = value

        for conditions in self._state_paths:
            conditions.setdefault(value, _WILDCARD)

        dpg.set_value(self._t(f"ambience_state:{idx}"), value)
        dpg.set_value(self._t(f"ambience_state_combo:{idx}"), value)
        self._rebuild_ambience_rows()
        self._update_summary()

    def _ambience_branch_to_row(self, entry: AmbientBgm, idx: int) -> None:
        if idx < len(self._state_paths):
            state_path = self._state_paths[idx]
        else:
            state_path = self._get_default_state_path()

        label = self._conditions_summary(entry, state_path)

        with dpg.tree_node(
            label=label,
            default_open=True,
            span_full_width=True,
            tag=self._t(f"track_conditions:{idx}"),
        ) as tree_node:
            with dpg.tree_node(label=µ("Regular"), span_full_width=True):
                add_wav_player(
                    entry.regular_track,
                    on_file_changed=self._make_track_changed_cb(idx, False),
                    on_loop_changed=self._make_loop_changed_cb(idx, False),
                )
                dpg.add_spacer(height=3)
                add_properties_table(
                    {PropID.HPF: 2.0},
                    self._make_properties_changed_cb(idx, False),
                    label=µ("Properties (in combat)"),
                )

            with dpg.tree_node(label=µ("Battle"), span_full_width=True):
                add_wav_player(
                    entry.battle_track,
                    on_file_changed=self._make_track_changed_cb(idx, True),
                    on_loop_changed=self._make_loop_changed_cb(idx, True),
                )
                add_properties_table(
                    {PropID.HPF: -400.0},
                    self._make_properties_changed_cb(idx, True),
                    label=µ("Properties (out of combat)"),
                )

        with dpg.item_handler_registry():
            dpg.add_item_clicked_handler(
                dpg.mvMouseButton_Right,
                callback=self._on_edit_conditions,
                user_data=idx,
            )

        dpg.bind_item_handler_registry(tree_node, dpg.last_container())

    def _new_ambience_branch(self, done: Callable[[AmbientBgm], None]) -> None:
        ret = open_file_dialog(
            title="Select Audio File",
            filetypes={µ("Audio Files (.wav, .wem)", "filetypes"): ["*.wav", "*.wem"]},
        )
        if ret:
            done(AmbientBgm(Path(ret)))

    def _on_add_ambience_branch(
        self,
        sender: str,
        info: tuple[int, AmbientBgm, list[AmbientBgm]],
        user_data: Any,
    ) -> None:
        entry = info[1]
        self._state_paths.append(self._get_default_state_path())
        self._bgm_tracks.append(entry)
        self._update_summary()

    def _on_remove_ambience_branch(
        self,
        sender: str,
        info: tuple[int, AmbientBgm, list[AmbientBgm]],
        user_data: Any,
    ) -> None:
        idx = info[0]
        self._state_paths.pop(idx)
        self._bgm_tracks.pop(idx)
        self._update_summary()

    def _on_add_ambience_arg(
        self,
        sender: str,
        info: tuple[int, str, list[str]],
        user_data: Any,
    ) -> None:
        arg = info[1]
        if arg and arg not in self.ambience_args:
            self.ambience_args = list(self.ambience_args) + [arg]
            # seed new key into existing entries so no data is lost
            for conditions in self._state_paths:
                conditions.setdefault(arg, _WILDCARD)

        self._rebuild_ambience_rows()
        self._update_summary()

    def _on_remove_ambience_arg(
        self,
        sender: str,
        info: tuple[int, str, list[str]],
        user_data: Any,
    ) -> None:
        idx = info[0]

        self.ambience_args = [a for i, a in enumerate(self.ambience_args) if i != idx]
        self._rebuild_ambience_rows()
        self._update_summary()

    def _on_edit_conditions(self, sender: str, app_data: Any, idx: int) -> None:
        """Open the state-path editor for one track entry."""
        entry = self._bgm_tracks[idx]
        conditions = self._state_paths[idx]
        state_args = self.ambience_args

        # build a synthetic state_path list aligned to the ambience args
        current_path = [conditions.get(a, _WILDCARD) for a in state_args]

        def _on_path_selected(_sender: str, state_path: list[str], _ud: Any) -> None:
            for arg, val in zip(state_args, state_path):
                conditions[arg] = val

            tag = self._t(f"track_conditions:{idx}")
            if dpg.does_item_exist(tag):
                dpg.set_item_label(tag, self._conditions_summary(entry, conditions))

            self._update_summary()

        edit_state_path_dialog(
            self.bnk,
            state_args,
            _on_path_selected,
            state_path=current_path,
            hide_node_id=True,
        )

    def _on_okay(self) -> None:
        if not self.msc:
            self.show_message(µ("Select MusicSwitchContainer first", "msg"))
            return

        if not self._bgm_tracks:
            self.show_messageµ("No tracks added", "msg")
            return

        bgm_place_type_idx = self.msc.get_argument_pos("BgmPlaceType")
        if self.location_state_path[bgm_place_type_idx] in ("", "0", _WILDCARD):
            self.show_message(µ("BgmPlaceType not set"))
            return

        for key in self.location_state_path:
            if not key:
                self.show_message(µ("Invalid state value {key}").format(key=key))
                return

            if key not in (_WILDCARD, "0"):
                break
        else:
            self.show_message(µ("Location state path not specified"))
            return

        seen: set[tuple[str]] = set()
        for idx, conditions in enumerate(self._state_paths):
            path = tuple(conditions.values())
            if path in seen:
                self.show_message(µ("State path {idx} is redundant").format(idx=idx))
                return

        self.show_message()

        with loading_indicator(µ("Working")):
            # convert .wav → .wem
            waves = []
            indices = []
            for i, bgm in enumerate(self._bgm_tracks):
                if bgm.regular_track and bgm.regular_track.suffix == ".wav":
                    waves.append(bgm.regular_track)
                    indices.append((i, "regular"))

                if bgm.battle_track and bgm.battle_track.suffix == ".wav":
                    waves.append(bgm.battle_track)
                    indices.append((i, "battle"))

            if waves:
                wwise = get_config().locate_wwise()
                converted = wav2wem(wwise, waves)

                for (idx, state), wem in zip(indices, converted):
                    if state == "regular":
                        self._bgm_tracks[idx].regular_track = wem
                    else:
                        self._bgm_tracks[idx].battle_track = wem

            # TODO transition rules?
            ambience_tree = build_tree(
                self._bgm_tracks, self._state_paths, self.ambience_args
            )

            nodes = create_ambience_bgm(
                self.bnk,
                self.msc,
                self.location_state_path,
                ambience_tree,
                properties={PropID.Priority: 80.0},
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
                self._build_tab_location()
                self._build_tab_ambience()
                self._build_tab_summary()

    def _build_tab_location(self) -> None:
        with dpg.tab(label=µ("location branch")):
            dpg.add_text(µ("MusicSwitchContainer"))
            add_select_node(
                self._get_location_mscs,
                "MusicSwitchContainer",
                self._on_msc_selected,
                get_node_details=get_details_musicswitchcontainer,
                node_type=MusicSwitchContainer,
            )

            dpg.add_child_window(
                autosize_x=True,
                auto_resize_y=True,
                tag=self._t("location_args_group"),
                show=False,
            )

            add_paragraphs(
                µ(
                    """\
                        - Ambience tracks need to be added to cs_Smain (sssss!)
                        - Use the main music controller (1001573296 in ER/NR)
                        - Set BgmPlaceType to your map's BgmPlaceInfo (vanilla only!)
                        - (All?) map regions can modify CommonPlaceType
                        - Use a SoundRegion (not Sound!) and set Unknown 0x0A
                    """,
                    "tips",
                ),
                color=style.light_blue,
            )

    def _build_tab_ambience(self) -> None:
        with dpg.tab(label=µ("Ambience tree")):
            with dpg.tree_node(label="States", default_open=True):
                self._ambience_states_table = add_widget_table(
                    list(self.ambience_args),
                    self._ambience_arg_to_row,
                    new_item=self._new_ambience_arg,
                    on_add=self._on_add_ambience_arg,
                    on_remove=self._on_remove_ambience_arg,
                    add_item_label=µ("+ Add State"),
                    show_clear=False,
                )

            dpg.add_spacer(height=4)
            add_widget_table(
                [],
                self._ambience_branch_to_row,
                new_item=self._new_ambience_branch,
                on_add=self._on_add_ambience_branch,
                on_remove=self._on_remove_ambience_branch,
                add_item_label=µ("+ Add Branch"),
                show_clear=True,
            )

            add_paragraphs(
                µ(
                    """\
                        - Your location can use additional states
                        - Typical states are TimeZone and FieldBattleState
                        - Areas usually have a base track and a battle overlay
                    """,
                    "tips",
                ),
                color=style.light_blue,
            )

    def _build_tab_summary(self) -> None:
        with dpg.tab(label=µ("Summary")):
            dpg.add_text(µ("Ambience decision tree:", "tips"))

            dpg.add_spacer(height=3)
            with dpg.child_window(height=-70):
                dpg.add_text(
                    µ("<nothing to see here>"),
                    tag=self._t("summary_text"),
                    color=style.pink,
                )

            dpg.add_spacer(height=2)
            dpg.add_text(
                "",
                tag=self._t("notification"),
                show=False,
                color=style.red,
            )

            dpg.add_spacer(height=4)
            dpg.add_button(
                label=µ("Let there be light!", "button"),
                callback=self._on_okay,
                tag=self._t("btn_okay"),
            )

    def _make_track_changed_cb(self, idx: int, battle: bool) -> Callable:
        def cb(sender: str, track: Path, user_data: Any) -> None:
            if track:
                if battle:
                    self._bgm_tracks[idx].battle_track = track
                else:
                    self._bgm_tracks[idx].regular_track = track

                self._update_summary()

        return cb

    def _make_loop_changed_cb(self, idx: int, battle: bool) -> Callable:
        def cb(sender: str, data: tuple[float, float, bool], user_data: Any) -> None:
            if idx < len(self._bgm_tracks):
                self._bgm_tracks[idx].loop_start = data[0]
                self._bgm_tracks[idx].loop_end = data[1]

        return cb

    def _make_properties_changed_cb(self, idx: int, battle: bool) -> Callable:
        def cb(sender: str, data: dict[PropID, float], user_data: Any) -> None:
            if idx < len(self._bgm_tracks):
                if battle:
                    self._bgm_tracks[idx].state_ctrl_battle = data
                else:
                    self._bgm_tracks[idx].state_ctrl_regular = data

        return cb

    # === Public ============================================================

    def show_message(self, msg: str = None, color: style.RGBA = style.red) -> None:
        """Show or hide the notification on the Summary tab."""
        tag = self._t("notification")
        if not msg:
            dpg.hide_item(tag)
            return

        dpg.configure_item(tag, default_value=msg, color=color, show=True)

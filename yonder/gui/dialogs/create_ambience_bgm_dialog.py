from __future__ import annotations
from typing import Any, Callable, Literal
from pathlib import Path
from dataclasses import dataclass, field
from dearpygui import dearpygui as dpg

from yonder import Soundbank, HIRCNode
from yonder.hash import lookup_name, calc_hash
from yonder.types import MusicSwitchContainer
from yonder.enums import PropID
from yonder.convenience import (
    create_ambience_bgm,
    DecisionNode,
    BgmTrack,
    StateCtrl,
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
    loading_indicator,
)
from yonder.gui.widgets.select_node import get_details_musicswitchcontainer
from .edit_state_path_dialog import edit_state_path_dialog
from .file_dialog import open_file_dialog


@dataclass
class StateProperty:
    property: PropID = None
    value: float = 0.0
    mode: Literal["default", "regular", "battle"] = "default"


@dataclass
class BgmVariant:
    track: Path = None
    props: list[StateProperty] = field(default_factory=list)
    loop_info: tuple[float, float] = (0.0, 0.0)
    trims: tuple[float, float] = (0.0, 0.0)


@dataclass
class AmbientBgm:
    regular: BgmVariant = None
    battle: BgmVariant = None
    state_path: dict[str, str] = field(default_factory=dict)
    fadein: float = 0.0
    intro: bool = False

    def _collect_properties(
        self, bgm: BgmVariant
    ) -> tuple[dict[PropID, float], StateCtrl, StateCtrl]:
        default = {}
        normal = StateCtrl("FieldBattleState", "FieldNormal", {})
        battle = StateCtrl("FieldBattleState", "FieldNormal", {})

        for p in bgm.props:
            if p.mode == "default":
                default[p.property] = p.value
            elif p.mode == "regular":
                normal.modifiers[p.property] = p.value
            elif p.mode == "battle":
                battle.modifiers[p.property] = p.value
            else:
                raise ValueError(f"Unknown state property mode {p.mode}")

        return (default, normal, battle)

    def to_bgmtrack(self) -> tuple[BgmTrack, BgmTrack]:
        reg_default, reg_ctrl_normal, reg_ctrl_battle = self._collect_properties(
            self.regular
        )
        bat_default, bat_ctrl_normal, bat_ctrl_battle = self._collect_properties(
            self.battle
        )

        return (
            BgmTrack(
                self.regular.track,
                self.regular.loop_info,
                self.regular.trims,
                self.fadein,
                self.intro,
                reg_default,
                [reg_ctrl_normal, reg_ctrl_battle],
            ),
            BgmTrack(
                self.battle.track,
                self.battle.loop_info,
                self.battle.trims,
                self.fadein,
                self.intro,
                bat_default,
                [bat_ctrl_normal, bat_ctrl_battle],
            ),
        )


def build_tree(
    entries: list[AmbientBgm],
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
        depth: int,
    ) -> None:
        if depth == len(active_args):
            node.children.append(DecisionNode(leaf_value=entry.to_bgmtrack()))
            return

        arg = active_args[depth]
        val = entry.state_path.get(arg, _WILDCARD)
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
        self.on_created = on_created

        self.msc: MusicSwitchContainer = None
        self.area_args = list(initial_ambience_args or [])
        self.local_args: list[str] = []
        self._bgm_tracks: list[AmbientBgm] = []

        self._build(title)

    # === Helpers ===========================================================

    def _get_area_mscs(self, filt: str) -> list[MusicSwitchContainer]:
        valid_msc_arg_hash = calc_hash("BgmPlaceType")
        return list(
            self.bnk.query(
                f"type=MusicSwitchContainer arguments:*/group_id={valid_msc_arg_hash} {filt}"
            )
        )

    def _conditions_summary(
        self,
        entry: AmbientBgm,
        join: str = " / ",
    ) -> str:
        """One-line summary of which conditions are set for a track entry."""
        parts = [entry.state_path.get(arg, _WILDCARD) for arg in self.area_args]
        return join.join(parts)

    def _update_summary(self) -> None:
        def leaf_to_str(leaf: tuple[BgmTrack, BgmTrack]) -> str:
            ret = [bgm.track.name for bgm in leaf if bgm.track]
            return "\n".join(ret)

        location_str = " / ".join(v for v in self.local_args if v != "*")
        if not location_str:
            location_str = "<invalid>"

        tree = build_tree(self._bgm_tracks, self.area_args)
        tree_str = tree.format_tree(leaf_to_str=leaf_to_str) or µ("<nothing to see here>")

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

        self.local_args = [_WILDCARD] * len(self.msc.arguments)

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
        for idx, entry in enumerate(self._bgm_tracks):
            tag = self._t(f"track_conditions:{idx}")
            if dpg.does_item_exist(tag):
                dpg.set_item_label(tag, self._conditions_summary(entry))

    def _get_default_state_path(self) -> dict[str, str]:
        return {a: _WILDCARD for a in self.area_args}

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
        self.local_args[idx] = value
        input_tag = self._t(f"location_val:{idx}")
        if dpg.does_item_exist(input_tag) and sender != input_tag:
            dpg.set_value(input_tag, value)

    def _local_arg_to_row(self, arg: str, idx: int) -> None:
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

    def _new_local_arg(self, done: Callable[[str], None]) -> None:
        arg = "<empty>"
        self.area_args.append(arg)
        done(arg)

    def _on_ambience_arg_name_changed(self, sender: str, value: str, idx: int) -> None:
        self.area_args[idx] = value
        self._ambience_states_table.items[idx] = value

        for entry in self._bgm_tracks:
            entry.state_path.setdefault(value, _WILDCARD)

        dpg.set_value(self._t(f"ambience_state:{idx}"), value)
        dpg.set_value(self._t(f"ambience_state_combo:{idx}"), value)
        self._rebuild_ambience_rows()
        self._update_summary()

    def _local_branch_to_row(self, entry: AmbientBgm, idx: int) -> None:
        label = self._conditions_summary(entry)

        with dpg.tree_node(
            label=label,
            default_open=True,
            lines=dpg.mvTreeLines_ToNodes,
            span_full_width=True,
            tag=self._t(f"track_conditions:{idx}"),
        ) as tree_node:
            with dpg.child_window(
                autosize_x=True,
                auto_resize_y=True,
            ):
                with dpg.group(horizontal=True):
                    dpg.add_checkbox(
                        label=µ("Intro"),
                        default_value=entry.intro,
                        callback=self._make_callback(entry, "intro"),
                    )
                    with dpg.tooltip(dpg.last_item()):
                        dpg.add_text(µ("Use part before loop_start as intro"))

                    dpg.add_input_float(
                        label=µ("Fade-in"),
                        default_value=0.0,
                        min_value=0.0,
                        min_clamped=True,
                        width=200,
                        callback=self._make_callback(entry, "fadein"),
                    )

                # TODO
                with dpg.group(horizontal=True):
                    dpg.add_text(µ("Transitions:"))
                    dpg.add_button(
                        label=µ("Default"),
                    )
                    dpg.add_button(
                        label=µ("Branches"),
                    )
                    dpg.add_button(
                        label=µ("Intro"),
                    )

            dpg.add_spacer(height=3)

            with dpg.tree_node(
                label=µ("Regular"),
                lines=dpg.mvTreeLines_ToNodes,
                span_full_width=True,
            ) as tree_node_regular:
                add_wav_player(
                    entry.regular.track,
                    on_file_changed=self._make_callback(entry.regular, "track"),
                    loop_markers_enabled=True,
                    on_loop_changed=self._make_callback(entry.regular, "loop_info"),
                    trim_enabled=True,
                    on_trims_changed=self._make_callback(entry.regular, "trims"),
                )
                dpg.add_spacer(height=3)
                add_widget_table(
                    entry.regular.props,
                    self._bgm_properties_to_row,
                    new_item=self._new_bgm_property,
                    on_add=self._on_add_bgm_property,
                    on_remove=self._on_remove_bgm_property,
                    columns=["", "", µ("default"), µ("regular"), µ("battle")],
                    column_weights=[100, 100, 25, 25, 25],
                    header_row=True,
                    label=µ("Properties"),
                    user_data=(idx, False),
                )
            dpg.bind_item_theme(tree_node_regular, style.themes.get_color_theme(style.green))

            with dpg.tree_node(
                label=µ("Battle"),
                lines=dpg.mvTreeLines_ToNodes,
                span_full_width=True,
            ) as tree_node_battle:
                add_wav_player(
                    entry.battle.track,
                    on_file_changed=self._make_callback(entry, "track"),
                    loop_markers_enabled=True,
                    on_loop_changed=self._make_callback(entry, "loop_info"),
                    trim_enabled=True,
                    on_trims_changed=self._make_callback(entry, "trims"),
                )
                dpg.add_spacer(height=3)
                add_widget_table(
                    entry.battle.props,
                    self._bgm_properties_to_row,
                    new_item=self._new_bgm_property,
                    on_add=self._on_add_bgm_property,
                    on_remove=self._on_remove_bgm_property,
                    columns=["", "", µ("default"), µ("regular"), µ("battle")],
                    column_weights=[100, 100, 25, 25, 25],
                    header_row=True,
                    label=µ("Properties"),
                    user_data=(idx, True),
                )
            dpg.bind_item_theme(tree_node_battle, style.themes.get_color_theme(style.light_red))

        with dpg.item_handler_registry():
            dpg.add_item_clicked_handler(
                dpg.mvMouseButton_Right,
                callback=self._edit_state_path,
                user_data=idx,
            )

        dpg.bind_item_handler_registry(tree_node, dpg.last_container())

    def _new_local_branch(self, done: Callable[[AmbientBgm], None]) -> None:
        ret = open_file_dialog(
            title="Select Audio File",
            filetypes={µ("Audio Files (.wav, .wem)", "filetypes"): ["*.wav", "*.wem"]},
        )
        if ret:
            done(
                AmbientBgm(
                    BgmVariant(
                        Path(ret), props=[StateProperty(PropID.HPF, 2.0, "battle")]
                    ),
                    BgmVariant(
                        None, props=[StateProperty(PropID.HPF, -400.0, "regular")]
                    ),
                    state_path=self._get_default_state_path(),
                )
            )

    def _on_add_local_branch(
        self,
        sender: str,
        info: tuple[int, AmbientBgm, list[AmbientBgm]],
        user_data: Any,
    ) -> None:
        entry = info[1]
        self._bgm_tracks.append(entry)
        self._update_summary()

    def _on_remove_local_branch(
        self,
        sender: str,
        info: tuple[int, AmbientBgm, list[AmbientBgm]],
        user_data: Any,
    ) -> None:
        idx = info[0]
        self._bgm_tracks.pop(idx)
        self._update_summary()

    def _bgm_properties_to_row(self, prop: StateProperty, idx: int) -> None:
        def on_property_changed(sender: str, new_val: str, user_data: Any) -> None:
            prop.property = PropID[new_val]

        def on_value_changed(sender: str, new_val: str, user_data: Any) -> None:
            prop.value = new_val

        def on_mode_toggle(sender: str, enabled: bool, sender_mode: str) -> None:
            if not enabled:
                # One must always be active
                dpg.set_value(sender, True)
                return

            for mode, checkbox in [
                ("default", check_default),
                ("regular", check_regular),
                ("battle", check_battle),
            ]:
                dpg.set_value(checkbox, mode == sender_mode)

        # TODO remove states that are already in use for properties with the same mode
        dpg.add_combo(
            sorted(p.name for p in PropID),
            default_value=prop.property.name,
            width=-1,
            callback=on_property_changed,
        )
        dpg.add_input_float(
            default_value=prop.value,
            width=-1,
            callback=on_value_changed,
        )

        check_default = dpg.add_checkbox(
            default_value=prop.mode == "default",
            callback=on_mode_toggle,
            user_data="default",
        )
        check_regular = dpg.add_checkbox(
            default_value=prop.mode == "regular",
            callback=on_mode_toggle,
            user_data="regular",
        )
        check_battle = dpg.add_checkbox(
            default_value=prop.mode == "battle",
            callback=on_mode_toggle,
            user_data="battle",
        )

    def _new_bgm_property(self, done: Callable[[StateProperty], None]) -> None:
        done(StateProperty(PropID.Volume))

    def _on_add_bgm_property(
        self,
        sender: str,
        data: tuple[int, StateProperty, list[StateProperty]],
        info: tuple[int, bool],
    ) -> None:
        idx, battle = info

        if battle:
            self._bgm_tracks[idx].battle.props.append(data[1])
        else:
            self._bgm_tracks[idx].regular.props.append(data[1])

    def _on_remove_bgm_property(
        self,
        sender: str,
        data: tuple[int, StateProperty, list[StateProperty]],
        info: tuple[int, bool],
    ) -> None:
        idx, battle = info

        if battle:
            self._bgm_tracks[idx].battle.props.pop(data[0])
        else:
            self._bgm_tracks[idx].regular.props.pop(data[0])

    def _on_add_local_arg(
        self,
        sender: str,
        info: tuple[int, str, list[str]],
        user_data: Any,
    ) -> None:
        arg = info[1]
        if arg and arg not in self.area_args:
            self.area_args = list(self.area_args) + [arg]
            # seed new key into existing entries so no data is lost
            for entry in self._bgm_tracks:
                entry.state_path.setdefault(arg, _WILDCARD)

        self._rebuild_ambience_rows()
        self._update_summary()

    def _on_remove_local_arg(
        self,
        sender: str,
        info: tuple[int, str, list[str]],
        user_data: Any,
    ) -> None:
        idx = info[0]

        self.area_args = [a for i, a in enumerate(self.area_args) if i != idx]
        self._rebuild_ambience_rows()
        self._update_summary()

    def _edit_state_path(self, sender: str, app_data: Any, idx: int) -> None:
        """Open the state-path editor for one track entry."""
        entry = self._bgm_tracks[idx]
        state_args = self.area_args

        # build a synthetic state_path list aligned to the ambience args
        current_path = [entry.state_path.get(a, _WILDCARD) for a in state_args]

        def _on_path_selected(_sender: str, state_path: list[str], _ud: Any) -> None:
            for arg, val in zip(state_args, state_path):
                entry.state_path[arg] = val

            tag = self._t(f"track_conditions:{idx}")
            if dpg.does_item_exist(tag):
                dpg.set_item_label(tag, self._conditions_summary(entry))

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
        if self.local_args[bgm_place_type_idx] in ("", "0", _WILDCARD):
            self.show_message(µ("BgmPlaceType not set"))
            return

        for key in self.local_args:
            if not key:
                self.show_message(µ("Invalid state value {key}").format(key=key))
                return

            if key not in (_WILDCARD, "0"):
                break
        else:
            self.show_message(µ("Location state path not specified"))
            return

        seen: set[tuple[str]] = set()
        for idx, entry in enumerate(self._bgm_tracks):
            path = tuple(entry.state_path.values())
            if path in seen:
                self.show_message(µ("State path {idx} is redundant").format(idx=idx))
                return

        self.show_message()

        with loading_indicator(µ("Working")):
            # convert .wav -> .wem
            waves = []
            indices = []
            for i, bgm in enumerate(self._bgm_tracks):
                if bgm.regular.track and bgm.regular.track.suffix == ".wav":
                    waves.append(bgm.regular.track)
                    indices.append((i, "regular"))

                if bgm.battle.track and bgm.battle.track.suffix == ".wav":
                    waves.append(bgm.battle.track)
                    indices.append((i, "battle"))

            if waves:
                wwise = get_config().locate_wwise()
                converted = wav2wem(wwise, waves)

                for (idx, state), wem in zip(indices, converted):
                    if state == "regular":
                        self._bgm_tracks[idx].regular.track = wem
                    else:
                        self._bgm_tracks[idx].battle.track = wem

            # TODO transition rules?
            ambience_tree = build_tree(self._bgm_tracks, self.area_args)

            nodes = create_ambience_bgm(
                self.bnk,
                self.msc,
                self.local_args,
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
            height=640,
            no_saved_settings=True,
            tag=self.tag,
            on_close=lambda: dpg.delete_item(self.tag),
        ):
            with dpg.tab_bar():
                self._build_tab_area_selector()
                self._build_tab_local_tree()
                self._build_tab_summary()

    def _build_tab_area_selector(self) -> None:
        with dpg.tab(label=µ("Area selector")):
            with dpg.child_window(
                border=False,
                autosize_x=True,
                height=-125,
            ):
                dpg.add_text(µ("MusicSwitchContainer"))
                add_select_node(
                    self._get_area_mscs,
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

    def _build_tab_local_tree(self) -> None:
        with dpg.tab(label=µ("Local tree")):
            with dpg.child_window(
                border=False,
                autosize_x=True,
                height=-105,
            ):
                with dpg.tree_node(label="States"):
                    self._ambience_states_table = add_widget_table(
                        list(self.area_args),
                        self._local_arg_to_row,
                        new_item=self._new_local_arg,
                        on_add=self._on_add_local_arg,
                        on_remove=self._on_remove_local_arg,
                        add_item_label=µ("+ Add State"),
                        show_clear=False,
                    )

                dpg.add_spacer(height=4)
                add_widget_table(
                    [],
                    self._local_branch_to_row,
                    new_item=self._new_local_branch,
                    on_add=self._on_add_local_branch,
                    on_remove=self._on_remove_local_branch,
                    add_item_label=µ("+ Add Branch"),
                    show_clear=True,
                )

            add_paragraphs(
                µ(
                    """\
                        - Your location can use additional states
                        - Typical states are TimeZone and FieldBattleState
                        - Areas usually have a base track and a battle overlay
                        - Loop markers for regular and battle are linked!
                    """,
                    "tips",
                ),
                color=style.light_blue,
            )

    def _build_tab_summary(self) -> None:
        with dpg.tab(label=µ("Summary")):
            dpg.add_text(µ("Ambience decision tree:", "tips"))

            dpg.add_spacer(height=3)
            with dpg.child_window(height=-45):
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

    def _make_callback(
        self, obj: Any, attr: str, transformer: Callable[[Any], Any] = None
    ) -> Callable:
        def cb(sender: str, value: Any, user_data: Any) -> None:
            if transformer:
                value = transformer(value)

            setattr(obj, attr, value)
            self._update_summary()

        return cb

    # === Public ============================================================

    def show_message(self, msg: str = None, color: style.RGBA = style.red) -> None:
        """Show or hide the notification on the Summary tab."""
        tag = self._t("notification")
        if not msg:
            dpg.hide_item(tag)
            return

        dpg.configure_item(tag, default_value=msg, color=color, show=True)

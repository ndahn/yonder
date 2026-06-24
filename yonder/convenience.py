from __future__ import annotations
from typing import Any, Generic, TypeVar
from dataclasses import dataclass, field
from pathlib import Path

from yonder import Soundbank, HIRCNode, Hash, calc_hash
from yonder.types import (
    Event,
    Action,
    ActorMixer,
    RandomSequenceContainer,
    Sound,
    MusicSwitchContainer,
    MusicRandomSequenceContainer,
    MusicSegment,
    MusicTrack,
)
from yonder.types.base_types import (
    MusicFade,
    RTPCGraphPoint,
    MusicTransitionRule,
)
from yonder.hash import lookup_name
from yonder.enums import (
    SyncType,
    PropID,
    SourceType,
    GroupType,
    ClipAutomationType,
    CurveInterpolation,
    MarkerId,
    PlaybackMode,
    RandomMode,
    VirtualQueueBehavior,
    SoundType,
)
from yonder.game import Game
from yonder.util import logger, parse_state_path


_T = TypeVar("_T")


@dataclass
class StateCtrl:
    group: str
    state: str
    modifiers: dict[PropID, float]


@dataclass
class BgmTrack:
    track: Path = None
    loop_info: tuple[float, float] = (0.0, 0.0)
    trims: tuple[float, float] = (0.0, 0.0)
    fadein: float = 0.0
    has_intro: bool = False
    properties: dict[PropID, float] = field(default_factory=dict)
    state_ctrl: list[StateCtrl] = field(default_factory=list)

    def __str__(self) -> str:
        if self.track:
            return f"{self.track.name}"

        return "None"


@dataclass
class DecisionNode(Generic[_T]):
    arg: str = ""
    value: str = "*"
    children: list[DecisionNode] = field(default_factory=list)
    leaf_value: _T = None

    @property
    def is_leaf(self) -> bool:
        return self.leaf_value is not None

    def all_args(self) -> list[str]:
        args = []
        node = self.children[0] if self.children else None
        while node and not node.is_leaf:
            args.append(node.arg)
            node = node.children[0] if node.children else None

        return args

    def flatten(self) -> dict[tuple[str, ...], _T]:
        def delve(node: DecisionNode, path: list[str]):
            if node.is_leaf:
                yield (tuple(path), node.leaf_value)
            else:
                for child in node.children:
                    child_val = [] if child.is_leaf else [child.value]
                    yield from delve(child, path + child_val)

        return dict(delve(self, []))

    def format_tree(self, indent: int = 0, leaf_to_str: callable = str) -> str:
        """Produce a compact text representation of a DecisionNode tree."""
        pad = "  " * indent
        if self.is_leaf:
            name = [f"{pad} + {x}" for x in leaf_to_str(self.leaf_value).splitlines()]
            return "\n".join(name)

        val = self.value if self.value is not None else "*"
        head = f"{pad}[{self.arg} = {val}]\n" if self.arg else ""
        return head + "".join(
            c.format_tree(indent + 1, leaf_to_str) for c in self.children
        )


def create_simple_sound(
    bnk: Soundbank,
    event_name: str,
    wems: list[Path] | Path,
    actor_mixer: int | ActorMixer,
    *,
    playback_mode: PlaybackMode = PlaybackMode.Random,
    random_mode: RandomMode = RandomMode.Standard,
    loop_count: int = 1,
    avoid_repeat_count: int = 0,
    properties: dict[PropID, float] = None,
) -> tuple[tuple[Event, Event], RandomSequenceContainer, list[Sound]]:
    """Create a new sound structure with one or more sounds in a RandomSequenceContainer controlled by a start and stop event.

    Parameters
    ----------
    bnk : Soundbank
        The soundbank to add the structure to.
    event_name : str
        Base name of the new events.
    wems : list[Path] | Path
        Audio files to add.
    actor_mixer : int | Node
        The ActorMixer to attach the new RandomSequenceContainer to.
    avoid_repeats : bool, optional
        If True the container will avoid playing the same sound twice in a row.
    properties : dict[str, float], optional
        Properties to apply to the RandomSequenceContainer.

    Returns
    -------
    Node
        _description_
    """
    if f"Play_{event_name}" in bnk:
        raise ValueError(f"Wwise event 'Play_{event_name}' already exists")

    if isinstance(wems, Path):
        wems = [wems]

    for w in wems:
        if not w.name.endswith(".wem"):
            raise ValueError("All tracks must be .wem files")

    rsc = RandomSequenceContainer.new(
        bnk.new_id(),
        None,
        playback_mode=playback_mode,
        random_mode=random_mode,
        loop_count=loop_count,
        avoid_repeat_count=avoid_repeat_count,
        parent=actor_mixer,
        props=properties,
    )

    sounds = []
    for w in wems:
        w = bnk.add_wem(w, SourceType.Embedded)
        snd = Sound.new(bnk.new_id(), w, parent=rsc.id)
        rsc.add_playlist_item(snd)
        sounds.append(snd)

    play = Event.new(f"Play_{event_name}")
    play_action = Action.new_play_action(bnk.new_id(), rsc.id, bnk.bank_id)
    play.actions.append(play_action.id)

    stop = Event.new(f"Stop_{event_name}")
    stop_action = Action.new_stop_action(bnk.new_id(), rsc.id)
    stop.actions.append(stop_action.id)

    # Add the RSC to the actor mixer
    if isinstance(actor_mixer, int):
        if actor_mixer == 0:
            logger.warning(
                f"No ActorMixer specified for RSC {rsc.id} of new sound {event_name}"
            )
        else:
            actor_mixer = bnk.get(actor_mixer)
            if not actor_mixer:
                logger.warning(
                    f"ActorMixer {actor_mixer} not found in soundbank {bnk}. If it is part of another soundbank, make sure to add the RSC's ID ({rsc.id}) to its children!"
                )

    if isinstance(actor_mixer, HIRCNode):
        actor_mixer.attach(rsc)

    # Add nodes to soundbank
    bnk.add_nodes(rsc, *sounds, play, play_action, stop, stop_action)
    return ((play, stop), rsc, sounds)


def _setup_bgm(
    bnk: Soundbank,
    parent: int | HIRCNode,
    tracks: BgmTrack | list[BgmTrack],
    *,
    intro: bool = False,
    track_transition: MusicTransitionRule = None,
    intro_transition: MusicTransitionRule = None,
) -> list[HIRCNode]:
    new_nodes = []
    if isinstance(tracks, BgmTrack):
        tracks = [tracks]

    # Might sometimes contain the loop_enabled flag, too
    loop_start, loop_end, *_ = tracks[0].loop_info

    for bgm in tracks:
        bnk.add_wem(bgm.track, SourceType.Streaming)

    root_mrsc = MusicRandomSequenceContainer.new(bnk.new_id(), parent=parent)
    new_nodes.append(root_mrsc)

    if intro and loop_start <= 0:
        raise ValueError("Intro enabled, but LoopStart is 0")

    if intro:
        if loop_start <= 1.0:
            logger.warning(f"Extremly short intro ({loop_start * 1000:0d}ms)")

        intro_seg = MusicSegment.new(
            bnk.new_id(), parent=root_mrsc, props={PropID.Priority: 80.0}
        )
        intro_seg.set_marker(MarkerId.LoopStart.value, 0.0)
        intro_seg.set_marker(MarkerId.LoopEnd.value, loop_start * 1000)
        new_nodes.append(intro_seg)

        for bgm in tracks:
            mt = MusicTrack.new(
                bnk.new_id(), bgm.track, parent=intro_seg, props={PropID.Priority: 80.0}
            )
            mt.set_trims(bgm.trims[0], loop_start * 1000)

            for prop, val in bgm.properties:
                mt.set_property(prop, val)

            if bgm.fadein > 0:
                mt.add_clip(
                    ClipAutomationType.FadeIn,
                    [
                        RTPCGraphPoint(0.0, 0.0, CurveInterpolation.Sine),
                        RTPCGraphPoint(
                            bgm.fadein * 1000, 1.0, CurveInterpolation.Constant
                        ),
                    ],
                )

            for ctrl in bgm.state_ctrl:
                mt.set_state_ctrl(bnk, ctrl.group, ctrl.state, ctrl.modifiers)

            intro_seg.duration = mt.playlist[0].source_duration
            intro_seg.attach(mt)
            new_nodes.append(mt)

        # Needs a root playlist item first
        playlist_root = root_mrsc.add_playlist_item(
            bnk.new_id(),
            0,
            ers_type=0,
            avoid_repeat_count=1,
        )
        # Setup playlist item as loop intro
        root_mrsc.add_playlist_item(
            bnk.new_id(),
            intro_seg.id,
            loop_base=True,
            parent=playlist_root,
        )

    # Setup the segment and music track
    bgm_seg = MusicSegment.new(
        bnk.new_id(), parent=root_mrsc, props={PropID.Priority: 80.0}
    )
    new_nodes.append(bgm_seg)

    # Add markers for looping
    if not loop_end:
        loop_end = bgm_seg.duration
    else:
        loop_end *= 1000

    if loop_end < 0:
        loop_end = bgm_seg.duration + loop_end

    # NOTE: Either the begin_trim or the LoopStart marker should remain at 0!
    # Leaving the loop marker at 0 and adjusting the begin trim instead should
    # be more reliable as it will work even if an intro is used, but can still
    # be adjusted per track

    # Intentionally set to 0! We'll trim to loop start instead
    bgm_seg.set_marker(MarkerId.LoopStart.value, 0)
    # According to Shion this is probably just for testing
    bgm_seg.set_marker("LoopCheck", loop_end - 3000)
    bgm_seg.set_marker(MarkerId.LoopEnd.value, loop_end)

    for bgm in tracks:
        mt = MusicTrack.new(
            bnk.new_id(), bgm.track, parent=bgm_seg, props={PropID.Priority: 80.0}
        )
        # NOTE loop_start is correct, see above
        mt.set_trims(loop_start, bgm.trims[1])

        for prop, val in bgm.properties:
            mt.set_property(prop, val)

        # Pronounced fade in for the track
        if not intro and bgm.fadein > 0.0:
            mt.add_clip(
                ClipAutomationType.FadeIn,
                [
                    RTPCGraphPoint(0.0, 0.0, CurveInterpolation.Sine),
                    RTPCGraphPoint(bgm.fadein * 1000, 1.0, CurveInterpolation.Constant),
                ],
            )

        for ctrl in bgm.state_ctrl:
            mt.set_state_ctrl(bnk, ctrl.group, ctrl.state, ctrl.modifiers)

        # Add to segment
        track_duration_ms = mt.playlist[0].source_duration
        bgm_seg.duration = track_duration_ms
        bgm_seg.attach(mt)
        new_nodes.append(mt)

    # Adjust base transition rule
    if not track_transition:
        track_transition = root_mrsc.music_trans_node_params.transition_rules[0]
        track_transition.configure(
            src_sync_type=SyncType.ExitMarker,  # important!
            src_transition_time=1000,
            src_fade_offset=1000,
            src_fade_curve=CurveInterpolation.Sine,
            dst_transition_time=500,
            dst_fade_offset=-500,
            dst_fade_curve=CurveInterpolation.Log1,
            dst_play_pre_entry=True,
        )

    root_mrsc.music_trans_node_params.transition_rules[0] = track_transition

    if intro:
        if not intro_transition:
            intro_transition = MusicTransitionRule().configure(
                src_ids=[intro_seg.id],
                dst_ids=[bgm_seg.id],
                src_sync_type=SyncType.ExitMarker,
                src_transition_time=100,
                src_fade_offset=100,
                src_fade_curve=CurveInterpolation.Sine,
                dest_transition_time=100,
                dest_fade_curve=CurveInterpolation.Exp3,
                dest_play_pre_entry=True,
                src_play_post_exit=0,
            )
        
        root_mrsc.music_trans_node_params.transition_rules.append(intro_transition)

    # Add the segment to the music container's playlist
    if not root_mrsc.playlist_items:
        playlist_root = root_mrsc.add_playlist_item(bnk.new_id(), 0, ers_type=0)
    else:
        playlist_root = root_mrsc.playlist_items[0].playlist_item_id

    root_mrsc.add_playlist_item(bnk.new_id(), bgm_seg.id, parent=playlist_root)

    return new_nodes


def _set_index_transition_ids(
    transitions: list[MusicTransitionRule], nodes: list[HIRCNode]
) -> None:
    def get_id(idx: int) -> int:
        if idx < 0:
            return -1

        if idx < len(nodes):
            return nodes[idx].id

        return None

    for trans in transitions:
        for idx, src_idx in enumerate(trans.source_ids):
            true_id = get_id(src_idx)
            if true_id is None:
                logger.warning(
                    f"Extra transition {idx} has invalid source index {src_idx}"
                )
            else:
                trans.source_ids[idx] = true_id

        for idx, dst_idx in enumerate(trans.destination_ids):
            true_id = get_id(dst_idx)
            if true_id is None:
                logger.warning(
                    f"Extra transition {idx} has invalid destination index {dst_idx}"
                )
            else:
                trans.source_ids[idx] = true_id


def create_boss_bgm(
    bnk: Soundbank,
    master: MusicSwitchContainer,
    master_branch: Hash | list[Hash],
    tracks: list[Path] | Path,
    *,
    loop_markers: list[tuple[float, float]] = None,
    play_intro: list[bool] = None,
    add_nobattle_state: bool = True,
    master_transition: MusicTransitionRule = None,
    phase_transitions: list[MusicTransitionRule] = None,
    track_transitions: MusicTransitionRule = None,
    properties: dict[PropID, float] = None,
) -> tuple[list[HIRCNode]]:
    # An overview of what's happening:
    # https://docs.google.com/document/d/1Dx8U9q6iEofPtKtZ0JI1kOedJYs9ifhlO7H5Knil5sg/edit?tab=t.0
    new_nodes: list[HIRCNode] = []

    if isinstance(tracks, Path):
        tracks = [tracks]

    for f in tracks:
        if not f.name.endswith(".wem"):
            raise ValueError("All tracks must be .wem files")

    # Setup the boss phase music manager
    if properties is None:
        properties = {}

    # Prepare the new master state path
    if isinstance(master_branch, (str, int)):
        bgm_enemy_type = master_branch
        master_branch: list[str] = []
        for arg in master.arguments:
            if lookup_name(arg) == "BgmEnemyType":
                master_branch.append(bgm_enemy_type)
            else:
                master_branch.append("*")

    # Default and heatup tracks
    boss_phases = ["*"]
    if len(tracks) > 1:
        boss_phases += [f"HU{i + 1}" for i in range(len(tracks) - 1)]

    boss_state_keys = parse_state_path(boss_phases)

    # Boss music manager
    boss_msc = MusicSwitchContainer.new(
        bnk.new_id(),
        [("BossBattleState", GroupType.State)],
        None,
        parent=master.id,
        props=properties | {PropID.Priority: 80.0},
    )
    new_nodes.append(boss_msc)

    # Setup transition rules
    if master_transition:
        master_transition.destination_ids = [boss_msc.id]
        master_transition.source_transition_rule.sync_type = SyncType.Immediate
        master.music_trans_node_params.transition_rules.append(master_transition)

    if not track_transitions:
        track_transitions = [MusicTransitionRule().configure(
            src_transition_time=100,
            src_fade_offset=100,
            src_fade_curve=CurveInterpolation.Sine,
            dest_transition_time=100,
            dest_fade_curve=CurveInterpolation.Exp3,
            dest_play_pre_entry=True,
        )] * len(tracks)

    # Setup the phase music tracks
    phase_masters: list[HIRCNode] = []
    for i, (phase, track) in enumerate(zip(boss_state_keys, tracks)):
        # TODO get BgmTracks passed instead
        bgm = BgmTrack(
            track,
            loop_markers[i],
            fadein=0.3,
        )
        phase_nodes = _setup_bgm(
            bnk,
            boss_msc,
            bgm,
            intro=play_intro and play_intro[i],
            track_transition=track_transitions[i],
        )

        boss_msc.add_branch([phase], phase_nodes[0])
        phase_masters.append(phase_nodes[0])
        new_nodes.extend(phase_nodes)

    # Phase transition rules
    if phase_transitions:
        _set_index_transition_ids(phase_transitions, phase_masters)
        boss_msc.music_trans_node_params.transition_rules = phase_transitions
    else:
        rule = boss_msc.music_trans_node_params.transition_rules[0]
        rule.configure(
            src_transition_time=1500,
            src_fade_offset=1500,
            src_fade_curve=CurveInterpolation.Sine,
            dst_transition_time=500,
            dst_fade_offset=-500,
            dst_fade_curve=CurveInterpolation.Log1,
            dst_play_pre_entry=True,
        )

    # To disable the boss music, presumably not used by bosses you can't run away from
    if add_nobattle_state:
        boss_msc.add_branch(["NoBattle"], 0)

    # Add to master and soundbank
    master.add_branch(master_branch, boss_msc)
    bnk.add_nodes(*new_nodes)
    return new_nodes


def create_ambience_bgm(
    bnk: Soundbank,
    master: MusicSwitchContainer,
    master_branch: Hash | list[Hash],
    location_tree: DecisionNode[tuple[BgmTrack, BgmTrack]],
    *,
    master_transition: MusicTransitionRule = None,
    variant_transitions: list[MusicTransitionRule] = None,
    track_transitions: list[MusicTransitionRule] = None,
    properties: dict[PropID, float] = None,
) -> list[HIRCNode]:
    new_nodes = []

    if properties is None:
        properties = {}

    # Prepare the new master state path
    if isinstance(master_branch, (str, int)):
        common_place_type = master_branch
        master_branch: list[str] = []
        for arg in master.arguments:
            if lookup_name(arg) == "CommonPlaceType":
                master_branch.append(common_place_type)
            else:
                master_branch.append("*")

    location_branches = location_tree.flatten()

    # Manager for this ambience
    ambience_msc = MusicSwitchContainer.new(
        bnk.new_id(),
        [(arg, GroupType.State) for arg in location_tree.all_args()],
        props=properties | {PropID.Priority: 80.0},
        parent=master,
    )
    new_nodes.append(ambience_msc)

    # Setup transition rules
    if master_transition:
        master_transition.destination_ids = [ambience_msc.id]
        master_transition.source_transition_rule.sync_type = SyncType.Immediate
        master.music_trans_node_params.transition_rules.append(master_transition)

    if not track_transitions:
        track_transitions = [MusicTransitionRule().configure(
            src_transition_time=3000,
            src_fade_offset=3000,
            src_fade_curve=CurveInterpolation.SCurve,
            dst_transition_time=1000,
            dst_fade_curve=CurveInterpolation.InvSCurve,
        )] * len(location_branches)

    branch_masters: list[HIRCNode] = []
    for idx, branch, (regular_track, battle_track) in enumerate(location_branches.items()):
        # Ambience music typically has one base track and a battle track which is overlayed
        # rather than being a separate music track, but we don't enforce that here. The
        # alternative being to have a decision branch on the FieldBattleState, in which case
        # we won't need the states to control audio layers.
        tracks = []
        has_intro = False

        if regular_track:
            tracks.append(regular_track)
            has_intro |= regular_track.has_intro

        if battle_track:
            has_intro = battle_track.has_intro

        branch_nodes = _setup_bgm(
            bnk,
            ambience_msc,
            tracks,
            intro=has_intro,
            track_transition=track_transitions[idx],
        )

        ambience_msc.add_branch(branch, branch_nodes[0])
        branch_masters.append(branch_nodes[0])
        new_nodes.extend(branch_nodes)

    # Variation transition rules
    if variant_transitions:
        _set_index_transition_ids(variant_transitions, branch_masters)
        ambience_msc.music_trans_node_params.transition_rules.extend(
            variant_transitions
        )
    else:
        rule = ambience_msc.music_trans_node_params.transition_rules[0]
        rule.configure(
            src_transition_time=1000,
            src_fade_offset=1000,
            src_fade_curve=CurveInterpolation.Linear,
            src_sync_type=SyncType.Immediate,
            dst_transition_time=1000,
            dst_fade_curve=CurveInterpolation.Linear,
        )

    # Add to master and soundbank
    master.add_branch(master_branch, ambience_msc)
    bnk.add_nodes(*new_nodes)
    return new_nodes


# TODO outdated, will need a revisit
def create_ambience_soundscape(
    bnk: Soundbank,
    master: MusicSwitchContainer,
    master_branch: list[Hash],
    location_tree: DecisionNode[Path],
    *,
    trims: list[tuple[float, float]] = None,
    properties: dict[PropID, float] = None,
) -> list[HIRCNode]:
    new_nodes = []

    if properties is None:
        properties = {}

    ambience_msc = MusicSwitchContainer.new(
        bnk.new_id(),
        [(arg, GroupType.State) for arg in location_tree.all_args()],
        props=properties | {PropID.Priority: 80.0},
        parent=master,
    )
    new_nodes.append(ambience_msc)

    # Setup default transition
    base_rule = ambience_msc.music_trans_node_params.transition_rules[0]
    base_rule.configure(
        src_transition_time=3000,
        src_fade_offset=3000,
        src_fade_curve=CurveInterpolation.Sine,
        src_sync_type=SyncType.Immediate,
        dst_transition_time=3000,
        dst_fade_curve=CurveInterpolation.Sine,
    )

    # Create the ambience tracks
    location_branches = location_tree.flatten()
    for branch, track in location_branches.items():
        track = bnk.add_wem(track, SourceType.Streaming)

        branch_mrsc = MusicRandomSequenceContainer.new(
            bnk.new_id(), parent=ambience_msc
        )
        # TODO trims
        branch_seg = MusicSegment.new(bnk.new_id(), parent=branch_mrsc)
        # All tracks should have the loop property
        branch_track = MusicTrack.new(bnk.new_id(), track, props={PropID.Loop: 0.0})

        # Transition rule (might matter for looping?)
        branch_rule = branch_mrsc.music_trans_node_params.transition_rules[0]
        branch_rule.configure(
            src_transition_time=1000,
            src_fade_offset=1000,
            src_fade_curve=CurveInterpolation.Log1,
            src_sync_type=SyncType.ExitMarker,
            dst_transition_time=1000,
            dst_fade_curve=CurveInterpolation.Log1,
        )

        # Connect the items
        branch_seg.attach(branch_track)
        branch_mrsc.add_playlist_item(bnk.new_id(), branch_seg, ers_type=0)
        ambience_msc.add_branch(parse_state_path(branch), branch_mrsc)

        new_nodes.extend([branch_mrsc, branch_seg, branch_track])

    master.add_branch(parse_state_path(master_branch), ambience_msc)
    bnk.add_nodes(*new_nodes)
    return new_nodes


#######################################
### EXPERIMENTAL
#######################################


# TODO untested
# Setup an audio layer that overrides the vanilla states.
def setup_custom_music_branch(
    bnk: Soundbank, node: MusicSwitchContainer, new_args: str | list[str]
) -> None:
    if node.has_argument("CustomMusic"):
        logger.info(f"Node {node} is already prepared")
        return

    if isinstance(new_args, str):
        new_args = [new_args]

    node.insert_argument(0, "CustomMusic", GroupType.State)
    for arg in new_args:
        node.insert_argument(-1, arg, GroupType.State)

    state_group_id = calc_hash("CustomMusic")
    on_state = calc_hash("On")
    off_state = calc_hash("None")

    enable_evt = Event.new("Play_m999888777")
    enable_act = Action.new_setstate_action(bnk.new_id(), state_group_id, on_state)
    enable_evt.actions.append(enable_act)

    disable_evt = Event.new("Stop_m999888777")
    disable_act = Action.new_setstate_action(bnk.new_id(), state_group_id, off_state)
    disable_evt.actions.append(disable_act)

    bnk.add_nodes(enable_evt, enable_act, disable_evt, disable_act)


# TODO untested
def create_custom_music_event(
    bnk: Soundbank,
    event_id: int,
    custom_states: dict[str, str],
    sound_type: SoundType = SoundType.Sfx,
) -> None:
    """Creates a play and stop event which, instead of playing audio, simply set a state. Since they have regular play/stop event names, they can be activated e.g. via EMEVD's PlaySE, SFX, etc. Should be used together with [[create_custom_music_branch]].

    Parameters
    ----------
    bnk : Soundbank
        The soundbank.
    event_id : int
        Numeric part of the event name.
    custom_states : dict[str, str]
        Additional states to set by the play event.
    sound_type : SoundType
        Prefix to use for the event name.
    """
    state_group_id = calc_hash("CustomMusic")
    on_state = calc_hash("On")
    off_state = calc_hash("None")

    enable_evt = Event.new(f"Play_{sound_type.value}{event_id}")
    enable_act = Action.new_setstate_action(bnk.new_id(), state_group_id, on_state)
    enable_evt.actions.append(enable_act)

    for key, val in custom_states.items():
        state_act = Action.new_setstate_action(
            bnk.new_id(), calc_hash(key), calc_hash(val)
        )
        enable_evt.actions.append(state_act)

    disable_evt = Event.new(f"Stop_{sound_type.value}{event_id}")
    disable_act = Action.new_setstate_action(bnk.new_id(), state_group_id, off_state)
    disable_evt.actions.append(disable_act)

    bnk.add_nodes(enable_evt, *enable_evt.actions, disable_evt, disable_act)


# TODO untested
# Fixes some shenanigans FS caused in their soundbanks, making it difficult or impossible to add
# custom music (especially in NR).
def unmangle_soundbanks(main: Soundbank, smain: Soundbank, game: Game) -> Soundbank:
    # Both NR and ER have a duplicate ambience structure in cs_smain which is actually
    # incomplete. The true one in cs_main takes priority, but it's confusing to have
    smain.delete_subtree("Play_a000000000")
    smain.delete_subtree("Stop_a000000000")

    if game == Game.EldenRing:
        pass
    elif game == Game.Nightreign:
        # NR contains an orphaned duplicate of the MusicSwitchContainer for music in cs_main
        # which will shadow the true one from cs_smain
        main.delete_subtree(1001573296)
    else:
        logger.warning(f"Unexpected game {game}")


# TODO untested
# Setup a custom music and ambience soundbank which would be easier to mod
def setup_music_soundbank(
    main: Soundbank, smain: Soundbank, new_bnk_path: Path
) -> Soundbank:
    from yonder.transfer import copy_wwise_events

    # TODO check if events still exist in cs_main/cs_smain

    music_bnk = Soundbank.create_empty_soundbank(new_bnk_path, "cs_music", True)

    # Transfer a000000000 to music_bnk
    copy_wwise_events(
        main,
        music_bnk,
        {"Play_a000000000": "Play_a000000000", "Stop_a000000000": "Stop_a000000000"},
    )
    main.delete_subtree("Play_a000000000")
    main.delete_subtree("Stop_a000000000")

    # Transfer m000000000 to music_bnk
    copy_wwise_events(
        smain,
        music_bnk,
        {"Play_m000000000": "Play_m000000000", "Stop_m000000000": "Stop_m000000000"},
    )
    main.delete_subtree("Play_m000000000")
    main.delete_subtree("Stop_m000000000")

    # Add reference to music_bnk so that it's automatically loaded by the game
    main.stid.add_bank("cs_music")
    return music_bnk

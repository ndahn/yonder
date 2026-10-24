from __future__ import annotations
from typing import Generic, TypeVar
from dataclasses import dataclass, field
from pathlib import Path

from yonder import Soundbank, HIRCNode, Hash, calc_hash
from yonder.types import (
    Event,
    Action,
    ActorMixer,
    RandomSequenceContainer,
    LayerContainer,
    SwitchContainer,
    Sound,
    MusicSwitchContainer,
    MusicRandomSequenceContainer,
    MusicSegment,
    MusicTrack,
)
from yonder.types.base_types import (
    RTPCGraphPoint,
    MusicTransitionRule,
)
from yonder.hash import lookup_name
from yonder.enums import (
    Game,
    SyncType,
    PropID,
    SourceType,
    GroupType,
    ClipAutomationType,
    CurveInterpolation,
    MarkerId,
    PlaybackMode,
    RandomMode,
    SoundType,
    RandomSequenceMode,
)
from yonder.util import logger, parse_state_path


_T = TypeVar("_T")


@dataclass
class StateProperty:
    prop: PropID = None
    value: float = None
    in_db: bool = False


@dataclass
class StateCtrl:
    group: str = None
    state: str = None
    modifiers: list[StateProperty] = field(default_factory=list)
    default: float = None


@dataclass
class BgmTrack:
    """A music track to turn into a segment.

    ``loop_info`` and ``trims`` are positions on the track's audio in ms. A
    loop end <= 0 is measured from the end of the audio.
    """

    track: Path = None
    loop_info: tuple[float, float] = (0.0, 0.0)
    trims: tuple[float, float] = (0.0, 0.0)
    fadein: float = 0.0
    properties: dict[PropID, float] = field(default_factory=dict)
    state_ctrl: list[StateCtrl] = field(default_factory=list)

    def __str__(self) -> str:
        if self.track:
            return f"{self.track.name}"

        return "None"


@dataclass
class BossBgm:
    track: BgmTrack = None
    # Play the part before loop_start once as an intro
    intro: bool = False


@dataclass
class AreaBgm:
    regular: BgmTrack = None
    battle: BgmTrack = None
    # Play the part before the regular track's loop_start once as an intro
    intro: bool = False

    def __str__(self):
        return f"""\
Regular: {self.regular}
Battle: {self.battle}
Intro: {self.intro}
"""


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


def _add_sound(bnk: Soundbank, wem: Path, parent: HIRCNode) -> Sound:
    """Embed one audio file and hang a Sound for it under `parent`."""
    wem = bnk.add_wem(wem, SourceType.Embedded)
    snd = Sound.new(bnk.new_id(), wem, parent=parent.id)

    if isinstance(parent, RandomSequenceContainer):
        parent.add_playlist_item(snd)
    else:
        parent.children.add(snd.id)

    return snd


def _group_by_layer(
    wems: "list[Path] | Path", layers: list[int] = None
) -> dict[int, list[Path]]:
    """Bucket the audio files by layer, keeping the order they came in.

    Files sharing a layer belong together: in an RSC they are alternatives of
    one slot, in a LayerContainer they are one of the parallel voices.
    """
    if isinstance(wems, Path):
        wems = [wems]

    if layers and len(layers) != len(wems):
        raise ValueError("Length of layers must match length of wems")

    layer_map: dict[int, list[Path]] = {}
    for wem, layer in zip(wems, layers or range(len(wems))):
        layer_map.setdefault(layer, []).append(wem)

    return layer_map


def _add_alternatives(
    bnk: Soundbank, wems: list[Path], parent: HIRCNode
) -> list[HIRCNode]:
    """Attach one slot's audio under `parent`, picking a shape to suit it.

    A single file becomes a plain Sound. Several become an RSC that picks one
    of them, which is how Fromsoft nests alternatives inside a slot.
    """
    if len(wems) == 1:
        return [_add_sound(bnk, wems[0], parent)]

    rsc = RandomSequenceContainer.new(bnk.new_id(), avoid_repeat_count=1, parent=parent.id)
    if isinstance(parent, RandomSequenceContainer):
        parent.add_playlist_item(rsc)
    else:
        parent.children.add(rsc.id)

    return [rsc] + [_add_sound(bnk, w, rsc) for w in wems]


def _make_events(
    bnk: Soundbank, event_name: str, target: HIRCNode
) -> tuple[Event, Action, Event, Action]:
    """The Play_/Stop_ event pair that drives `target`."""
    play = Event.new(f"Play_{event_name}")
    play_action = Action.new_play(bnk.new_id(), target, bank_id=bnk.bank_id)
    play.actions.append(play_action.id)

    stop = Event.new(f"Stop_{event_name}")
    stop_action = Action.new_stop(bnk.new_id(), target)
    stop.actions.append(stop_action.id)

    return play, play_action, stop, stop_action


def _attach_to_actor_mixer(
    bnk: Soundbank,
    actor_mixer: "int | ActorMixer",
    node: HIRCNode,
    event_name: str,
) -> None:
    """Hang the structure off its ActorMixer, warning if that is not possible."""
    if isinstance(actor_mixer, int):
        if actor_mixer == 0:
            logger.warning(
                f"No ActorMixer specified for {node.type_name} {node.id} of new sound {event_name}"
            )
            return

        resolved = bnk.get(actor_mixer)
        if not resolved:
            logger.warning(
                f"ActorMixer {actor_mixer} not found in soundbank {bnk}. If it is part of another soundbank, consider adding the container's ID ({node.id}) to its children!"
            )
            return

        actor_mixer = resolved

    if isinstance(actor_mixer, HIRCNode):
        actor_mixer.attach(node)


def create_simple_sound_rsc(
    bnk: Soundbank,
    event_name: str,
    wems: list[Path] | Path,
    actor_mixer: int | ActorMixer,
    *,
    layers: list[int] = None,
    playback_mode: PlaybackMode = PlaybackMode.Random,
    random_mode: RandomMode = RandomMode.Standard,
    loop_count: int = 1,
    avoid_repeat_count: int = 0,
    properties: dict[PropID, float] = None,
) -> tuple[tuple[Event, Event], RandomSequenceContainer, list[HIRCNode]]:
    """Create a sound structure that plays one of its sounds, picked per play.

    ActorMixer -> RandomSequenceContainer -> Sound, with the container choosing
    between the sounds. Files sharing a layer are nested under a LayerContainer
    so that they play together as one alternative.

    Parameters
    ----------
    bnk : Soundbank
        The soundbank to add the structure to.
    event_name : str
        Base name of the new events.
    wems : list[Path] | Path
        Audio files to add.
    actor_mixer : int | ActorMixer
        The ActorMixer to attach the new RandomSequenceContainer to.
    layers : list[int], optional
        One layer id per wem. Wems sharing an id are grouped under a
        LayerContainer and thus play in parallel. Defaults to one each.
    playback_mode : PlaybackMode
        Whether the container picks randomly or steps through in sequence.
    random_mode : RandomMode
        Standard or shuffle, when picking randomly.
    loop_count : int
        How often the container repeats. 0 loops forever.
    avoid_repeat_count : int
        How many recent picks the container refuses to repeat.
    properties : dict[PropID, float], optional
        Properties to apply to the RandomSequenceContainer.

    Returns
    -------
    tuple
        ``((play_event, stop_event), container, nodes)``, where `nodes` holds
        everything created below the container.
    """
    if f"Play_{event_name}" in bnk:
        raise ValueError(f"Wwise event 'Play_{event_name}' already exists")

    layer_map = _group_by_layer(wems, layers)

    master_rsc = RandomSequenceContainer.new(
        bnk.new_id(),
        None,
        playback_mode=playback_mode,
        random_mode=random_mode,
        loop_count=loop_count,
        avoid_repeat_count=avoid_repeat_count,
        parent=actor_mixer,
        props=properties,
    )

    nodes = []
    for layer_wems in layer_map.values():
        if len(layer_wems) == 1:
            # One sound is an alternative all by itself
            nodes.append(_add_sound(bnk, layer_wems[0], master_rsc))
        else:
            # Several play together: LayerContainer -> RSC -> Sound
            lc = LayerContainer.new(bnk.new_id(), parent=master_rsc.id)
            master_rsc.add_playlist_item(lc)
            nodes.append(lc)

            for w in layer_wems:
                nodes.extend(_add_alternatives(bnk, [w], lc))

    play, play_action, stop, stop_action = _make_events(bnk, event_name, master_rsc)
    _attach_to_actor_mixer(bnk, actor_mixer, master_rsc, event_name)

    bnk.add_nodes(master_rsc, *nodes, play, play_action, stop, stop_action)
    return ((play, stop), master_rsc, nodes)


def create_simple_sound_lc(
    bnk: Soundbank,
    event_name: str,
    wems: list[Path] | Path,
    actor_mixer: int | ActorMixer,
    *,
    layers: list[int] = None,
    properties: dict[PropID, float] = None,
) -> tuple[tuple[Event, Event], LayerContainer, list[HIRCNode]]:
    """Create a sound structure that plays all of its sounds at once.

    ActorMixer -> RandomSequenceContainer -> LayerContainer -> Sound. The
    LayerContainer is the interesting part, but it still hangs off an RSC: that
    is the shape Fromsoft uses under an ActorMixer, and it is what the events
    target, so all three create_simple_sound variants are wired alike.

    No blend tracks are set up, the children simply sound together. Add them
    with `LayerContainer.add_layer` if they should crossfade on an RTPC.

    Parameters
    ----------
    bnk : Soundbank
        The soundbank to add the structure to.
    event_name : str
        Base name of the new events.
    wems : list[Path] | Path
        Audio files to add. Each becomes one simultaneous voice.
    actor_mixer : int | ActorMixer
        The ActorMixer to attach the new RandomSequenceContainer to.
    layers : list[int], optional
        One layer id per wem. Wems sharing an id become alternatives of a
        single voice (RSC -> Sound) instead of voices of their own, so that a
        layer can vary between plays. Defaults to one each.
    properties : dict[PropID, float], optional
        Properties to apply to the LayerContainer.

    Returns
    -------
    tuple
        ``((play_event, stop_event), container, nodes)``, where `container` is
        the LayerContainer and `nodes` holds the RSC above it along with
        everything created below it.
    """
    if f"Play_{event_name}" in bnk:
        raise ValueError(f"Wwise event 'Play_{event_name}' already exists")

    layer_map = _group_by_layer(wems, layers)

    master_rsc = RandomSequenceContainer.new(bnk.new_id(), None, parent=actor_mixer)
    layer_container = LayerContainer.new(
        bnk.new_id(), props=properties, parent=master_rsc.id
    )
    master_rsc.add_playlist_item(layer_container)

    nodes = [layer_container]
    for layer_wems in layer_map.values():
        nodes.extend(_add_alternatives(bnk, layer_wems, layer_container))

    play, play_action, stop, stop_action = _make_events(bnk, event_name, master_rsc)
    _attach_to_actor_mixer(bnk, actor_mixer, master_rsc, event_name)

    bnk.add_nodes(master_rsc, *nodes, play, play_action, stop, stop_action)
    return ((play, stop), layer_container, nodes)


def create_simple_sound_sc(
    bnk: Soundbank,
    event_name: str,
    wems: list[Path] | Path,
    switch_group: str | int,
    switch_map: dict[str | int, int | list[int]],
    actor_mixer: int | ActorMixer,
    *,
    default_switch: str | int = None,
    properties: dict[PropID, float] = None,
) -> tuple[tuple[Event, Event], SwitchContainer, list[HIRCNode]]:
    """Create a sound structure that plays whichever sound the switch selects.

    ActorMixer -> RandomSequenceContainer -> SwitchContainer -> Sound. As with
    the LayerContainer variant the main container hangs off an RSC, which is
    what the events target.

    Parameters
    ----------
    bnk : Soundbank
        The soundbank to add the structure to.
    event_name : str
        Base name of the new events.
    wems : list[Path] | Path
        Audio files to add.
    switch_group : str | int
        The switch group the container reads, by name or id.
    switch_map : dict
        Which sounds each switch value plays, as indices into `wems`. A value
        mapped to several of them gets an RSC that picks between those. Wems
        that no switch asks for are left out of the structure entirely.
    actor_mixer : int | ActorMixer
        The ActorMixer to attach the new RandomSequenceContainer to.
    default_switch : str | int, optional
        The switch value to fall back on. Defaults to the first mapped one.
    properties : dict[PropID, float], optional
        Properties to apply to the SwitchContainer.

    Returns
    -------
    tuple
        ``((play_event, stop_event), container, nodes)``, where `container` is
        the SwitchContainer and `nodes` holds the RSC above it along with
        everything created below it.
    """
    if f"Play_{event_name}" in bnk:
        raise ValueError(f"Wwise event 'Play_{event_name}' already exists")

    if isinstance(wems, Path):
        wems = [wems]

    if not switch_map:
        raise ValueError("switch_map must assign at least one switch value")

    master_rsc = RandomSequenceContainer.new(bnk.new_id(), None, parent=actor_mixer)

    # The states are filled in below: a switch can only point at nodes that
    # exist, and those are created under the container itself
    switch_container = SwitchContainer.new(
        bnk.new_id(),
        switch_group,
        {},
        default_state=default_switch or next(iter(switch_map)),
        props=properties,
        parent=master_rsc.id,
    )
    master_rsc.add_playlist_item(switch_container)

    nodes = [switch_container]
    for state, indices in switch_map.items():
        if isinstance(indices, int):
            indices = [indices]

        chosen = [wems[i] for i in indices if 0 <= i < len(wems)]
        if not chosen:
            continue

        created = _add_alternatives(bnk, chosen, switch_container)
        nodes.extend(created)

        # The switch selects the node it was given, not the sounds below it
        switch_container.attach(created[0], state)

    play, play_action, stop, stop_action = _make_events(bnk, event_name, master_rsc)
    _attach_to_actor_mixer(bnk, actor_mixer, master_rsc, event_name)

    bnk.add_nodes(master_rsc, *nodes, play, play_action, stop, stop_action)
    return ((play, stop), switch_container, nodes)


def _setup_bgm(
    bnk: Soundbank,
    parent: int | HIRCNode,
    tracks: BgmTrack | list[BgmTrack],
    *,
    intro: bool = False,
    intro_transition: MusicTransitionRule = None,
    track_transition: MusicTransitionRule = None,
) -> list[HIRCNode]:
    """Create a music container with a looping segment for the tracks.

    The loop points are taken from the first track and are positions on its
    audio. If ``intro`` is set, the audio before the loop start is split off
    into an intro segment that plays once, and the main segment starts at the
    loop start.
    """
    new_nodes = []
    if isinstance(tracks, BgmTrack):
        tracks = [tracks]

    tracks = [bgm for bgm in tracks if bgm.track]
    ref = tracks[0] if tracks else BgmTrack()

    for bgm in tracks:
        bnk.add_wem(bgm.track, SourceType.Streaming)

    # Segment markers cannot take the track trims into account. Each track's
    # begin trim is balanced with a negative play_at instead, so that its
    # audible part starts with the segment. The markers are therefore shifted
    # by the reference track's begin trim.
    loop_start, loop_end, *_ = ref.loop_info
    intro = intro and loop_start > ref.trims[0]
    intro_length = loop_start - ref.trims[0] if intro else 0.0

    root_mrsc = MusicRandomSequenceContainer.new(bnk.new_id(), parent=parent)
    new_nodes.append(root_mrsc)

    if intro:
        if intro_length <= 1.0:
            logger.warning(f"Extremly short intro ({intro_length:.0f}ms)")

        intro_seg = MusicSegment.new(
            bnk.new_id(), parent=root_mrsc, props={PropID.Priority: 80.0}
        )
        # Like vanilla intros: the exit marker sits at the end of the audio
        intro_seg.set_marker(MarkerId.LoopStart.value, 0.0)
        intro_seg.set_marker(MarkerId.LoopEnd.value, intro_length)
        new_nodes.append(intro_seg)

        for bgm in tracks:
            mt = MusicTrack.new(
                bnk.new_id(), bgm.track, parent=intro_seg, props={PropID.Priority: 80.0}
            )
            # The intro ends where the main segment's loop starts
            intro_end = -(mt.playlist[0].source_duration - loop_start)
            mt.set_trims(bgm.trims[0], intro_end)
            mt.playlist[0].play_at = -bgm.trims[0]

            for prop, val in bgm.properties.items():
                mt.set_property(prop, val)

            if bgm.fadein > 0:
                mt.add_clip_automation(
                    ClipAutomationType.FadeIn,
                    [
                        RTPCGraphPoint(0.0, 0.0, CurveInterpolation.Sine),
                        RTPCGraphPoint(bgm.fadein, 1.0, CurveInterpolation.Constant),
                    ],
                )

            for ctrl in bgm.state_ctrl:
                if ctrl and ctrl.modifiers:
                    state_props = {
                        p.prop: (p.value if p.value != ctrl.default else None, p.in_db)
                        for p in ctrl.modifiers
                    }
                    mt.set_state_ctrl(
                        bnk, ctrl.group, ctrl.state, state_props, ctrl.default
                    )

            intro_seg.duration = intro_length
            intro_seg.attach(mt)
            new_nodes.append(mt)

        # Needs a root playlist item first
        playlist_root = root_mrsc.add_playlist_item(
            bnk.new_id(),
            0,
            ers_type=RandomSequenceMode.ContinuousSequence,
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

    ref_duration = 0.0
    for bgm in tracks:
        mt = MusicTrack.new(
            bnk.new_id(), bgm.track, parent=bgm_seg, props={PropID.Priority: 80.0}
        )
        if not ref_duration:
            ref_duration = mt.playlist[0].source_duration

        begin_trim = loop_start if intro else bgm.trims[0]
        mt.set_trims(begin_trim, bgm.trims[1])
        mt.playlist[0].play_at = -begin_trim

        for prop, val in bgm.properties.items():
            mt.set_property(prop, val)

        # Pronounced fade in for the track
        if not intro and bgm.fadein > 0.0:
            mt.add_clip_automation(
                ClipAutomationType.FadeIn,
                [
                    RTPCGraphPoint(0.0, 0.0, CurveInterpolation.Sine),
                    RTPCGraphPoint(bgm.fadein, 1.0, CurveInterpolation.Constant),
                ],
            )

        for ctrl in bgm.state_ctrl:
            if ctrl and ctrl.modifiers:
                state_props = {
                    p.prop: (p.value if p.value != ctrl.default else None, p.in_db)
                    for p in ctrl.modifiers
                }
                mt.set_state_ctrl(
                    bnk, ctrl.group, ctrl.state, state_props, ctrl.default
                )

        # Like in vanilla banks the segment is as long as the audible track
        begin_trim, end_trim = mt.get_trims()
        audible_ms = mt.playlist[0].source_duration - begin_trim + end_trim
        bgm_seg.duration = max(bgm_seg.duration, audible_ms)
        bgm_seg.attach(mt)
        new_nodes.append(mt)

    # Add markers for looping, moved from the audio onto the segment timeline
    if loop_end <= 0:
        loop_end = ref_duration + loop_end

    # With an intro the segment is trimmed to start at the loop
    shift = loop_start if intro else ref.trims[0]
    loop_start = max(0.0, loop_start - shift)
    loop_end = min(loop_end - shift, bgm_seg.duration)

    bgm_seg.set_marker(MarkerId.LoopStart.value, loop_start)
    # According to Shion this is probably just for testing
    bgm_seg.set_marker("LoopCheck", loop_end - 3000)
    bgm_seg.set_marker(MarkerId.LoopEnd.value, loop_end)

    # Adjust base transition rule
    if track_transition:
        # Important, can cause the game to crash otherwise!
        track_transition.configure(src_sync_type=SyncType.ExitMarker)
    else:
        track_transition = root_mrsc.music_trans_node_params.transition_rules[0]
        track_transition.configure(
            src_sync_type=SyncType.ExitMarker,
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
        if intro_transition:
            intro_transition.configure(src_sync_type=SyncType.ExitMarker)
        else:
            intro_transition = MusicTransitionRule().configure(
                src_ids=[intro_seg.id],
                dst_ids=[bgm_seg.id],
                src_sync_type=SyncType.ExitMarker,
                src_transition_time=100,
                src_fade_offset=100,
                src_fade_curve=CurveInterpolation.Sine,
                dst_transition_time=100,
                dst_fade_curve=CurveInterpolation.Exp3,
                dst_play_pre_entry=True,
                src_play_post_exit=0,
            )

        root_mrsc.music_trans_node_params.transition_rules.append(intro_transition)

    # Add the segment to the music container's playlist
    if not root_mrsc.playlist_items:
        playlist_root = root_mrsc.add_playlist_item(
            bnk.new_id(), 0, ers_type=RandomSequenceMode.ContinuousSequence
        )
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
                trans.destination_ids[idx] = true_id


def _get_unique_name(
    bnk: Soundbank, base: str, suffixes: list[int | str] = None
) -> str:
    if suffixes:
        for val in suffixes:
            if isinstance(val, int):
                val = lookup_name(val, val)
            if val and val not in "*0_ ":
                base += "_" + val.strip("_")

    base = base.rstrip("_")
    if base in bnk:
        base += "_"
        add = 1

        while base + str(add) in bnk:
            add += 1

        base += str(add)

    return base


def create_boss_bgm(
    bnk: Soundbank,
    master: MusicSwitchContainer,
    master_branch: Hash | list[Hash],
    tracks: BossBgm | list[BossBgm],
    *,
    add_nobattle_state: bool = True,
    master_transition: MusicTransitionRule = None,
    phase_transitions: list[MusicTransitionRule] = None,
    track_transitions: MusicTransitionRule = None,
) -> tuple[list[HIRCNode]]:
    # An overview of what's happening:
    # https://docs.google.com/document/d/1Dx8U9q6iEofPtKtZ0JI1kOedJYs9ifhlO7H5Knil5sg/edit?tab=t.0
    new_nodes: list[HIRCNode] = []

    if isinstance(tracks, Path):
        tracks = [tracks]

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
    name = _get_unique_name(bnk, "BossBgm", master_branch)
    boss_msc = MusicSwitchContainer.new(
        name,
        [("BossBattleState", GroupType.State)],
        None,
        parent=master.id,
        props={PropID.Priority: 80.0},
    )
    new_nodes.append(boss_msc)

    # Setup transition rules
    if master_transition:
        master_transition.destination_ids = [boss_msc.id]
        master_transition.source_transition_rule.sync_type = SyncType.Immediate
        master.music_trans_node_params.transition_rules.append(master_transition)

    if not track_transitions:
        track_transitions = [
            MusicTransitionRule().configure(
                src_sync_type=SyncType.ExitMarker,
                src_transition_time=500,
                src_fade_offset=500,
                src_fade_curve=CurveInterpolation.Sine,
                dst_transition_time=500,
                dst_fade_curve=CurveInterpolation.Exp3,
                dst_play_pre_entry=True,
            )
        ] * len(tracks)

    # Setup the phase music tracks
    phase_masters: list[HIRCNode] = []
    for i, (phase, bgm) in enumerate(zip(boss_state_keys, tracks)):
        phase_nodes = _setup_bgm(
            bnk,
            boss_msc,
            bgm.track,
            intro=bgm.intro,
            track_transition=track_transitions[i],
        )

        if phase == 0:
            # No need to add a new path, just adjust the default path
            boss_msc.select_child([phase]).node_id = phase_nodes[0].id
            boss_msc.children.add(phase_nodes[0].id)
        else:
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


def create_area_bgm(
    bnk: Soundbank,
    master: MusicSwitchContainer,
    master_branch: Hash | list[Hash],
    location_tree: DecisionNode[AreaBgm],
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

    # Manager for this area
    name = _get_unique_name(bnk, "AreaBgm", master_branch)
    area_msc = MusicSwitchContainer.new(
        calc_hash(name),
        [(arg, GroupType.State) for arg in location_tree.all_args()],
        props=properties | {PropID.Priority: 80.0},
        parent=master,
    )
    new_nodes.append(area_msc)

    # Setup transition rules
    if master_transition:
        master_transition.destination_ids = [area_msc.id]
        master_transition.source_transition_rule.sync_type = SyncType.Immediate
        master.music_trans_node_params.transition_rules.append(master_transition)

    if not track_transitions:
        track_transitions = [
            MusicTransitionRule().configure(
                src_sync_type=SyncType.ExitMarker,
                src_transition_time=3000,
                src_fade_offset=3000,
                src_fade_curve=CurveInterpolation.SCurve,
                dst_transition_time=1000,
                dst_fade_curve=CurveInterpolation.InvSCurve,
            )
        ] * len(location_branches)

    branch_masters: list[HIRCNode] = []
    for idx, (branch, bgm) in enumerate(location_branches.items()):
        # area music typically has one base track and a battle track which is overlayed
        # rather than being a separate music track, but we don't enforce that here. The
        # alternative being to have a decision branch on the FieldBattleState, in which case
        # we won't need the states to control audio layers.
        tracks = []

        if bgm.regular:
            tracks.append(bgm.regular)

        if bgm.battle:
            tracks.append(bgm.battle)

        branch_nodes = _setup_bgm(
            bnk,
            area_msc,
            tracks,
            intro=bgm.intro,
            track_transition=track_transitions[idx],
        )

        area_msc.add_branch(branch, branch_nodes[0])
        branch_masters.append(branch_nodes[0])
        new_nodes.extend(branch_nodes)

    # Variation transition rules
    if variant_transitions:
        _set_index_transition_ids(variant_transitions, branch_masters)
        area_msc.music_trans_node_params.transition_rules = variant_transitions
    else:
        rule = area_msc.music_trans_node_params.transition_rules[0]
        rule.configure(
            src_transition_time=1000,
            src_fade_offset=1000,
            src_fade_curve=CurveInterpolation.Linear,
            src_sync_type=SyncType.Immediate,
            dst_transition_time=1000,
            dst_fade_curve=CurveInterpolation.Linear,
        )

    # Add to master and soundbank
    master.add_branch(master_branch, area_msc)
    bnk.add_nodes(*new_nodes)
    return new_nodes


# TODO outdated, will need a revisit
def create_ambience(
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
        branch_mrsc.add_playlist_item(
            bnk.new_id(), branch_seg, ers_type=RandomSequenceMode.ContinuousSequence
        )
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
    enable_act = Action.new_set_state(bnk.new_id(), state_group_id, on_state)
    enable_evt.actions.append(enable_act)

    disable_evt = Event.new("Stop_m999888777")
    disable_act = Action.new_set_state(bnk.new_id(), state_group_id, off_state)
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
    enable_act = Action.new_set_state(bnk.new_id(), state_group_id, on_state)
    enable_evt.actions.append(enable_act)

    for key, val in custom_states.items():
        state_act = Action.new_set_state(
            bnk.new_id(), calc_hash(key), calc_hash(val)
        )
        enable_evt.actions.append(state_act)

    disable_evt = Event.new(f"Stop_{sound_type.value}{event_id}")
    disable_act = Action.new_set_state(bnk.new_id(), state_group_id, off_state)
    disable_evt.actions.append(disable_act)

    bnk.add_nodes(enable_evt, *enable_evt.actions, disable_evt, disable_act)


def unmangle_soundbanks(main: Soundbank, smain: Soundbank, game: Game) -> Soundbank:
    """Fixes some shenanigans FS caused in their soundbanks, making it difficult or impossible to add custom music (especially in NR)."""
    # Both NR and ER have a duplicate ambience structure in cs_smain which is actually
    # incomplete. The true one in cs_main takes priority, but it's confusing to have
    logger.info("Removing duplicate ambient structure from cs_smain")
    for key in ("Play_a000000000", "Stop_a000000000"):
        if key in smain:
            smain.delete_subtree(key)

    if game == Game.EldenRing:
        pass
    elif game == Game.Nightreign:
        # NR contains an orphaned duplicate of the MusicSwitchContainer for music in cs_main
        # which will shadow the true one from cs_smain
        logger.info("Removing duplicate music structure from cs_main")
        if 1001573296 in main:
            main.delete_subtree(1001573296)
    else:
        logger.warning(f"Unsupported game {game}")


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

    main.save()
    smain.save()
    music_bnk.save()

    return music_bnk

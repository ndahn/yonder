from pathlib import Path

from yonder import Soundbank, HIRCNode, Hash
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
)
from yonder.util import logger, parse_state_path


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


def create_boss_bgm(
    bnk: Soundbank,
    master: MusicSwitchContainer,
    state_path: Hash | list[Hash],
    tracks: list[Path] | Path,
    *,
    loop_markers: list[tuple[float, float]] = None,
    play_preloop_intro: list[bool] = None,
    add_nobattle_state: bool = True,
    default_transition: tuple[MusicFade, MusicFade] = None,
    phase_transitions: list[tuple[MusicFade, MusicFade]] = None,
    self_transitions: list[tuple[MusicFade, MusicFade]] = None,
    repeat_transitions: list[tuple[MusicFade, MusicFade]] = None,
) -> tuple[list[HIRCNode]]:
    # An overview of what's happening:
    # https://docs.google.com/document/d/1Dx8U9q6iEofPtKtZ0JI1kOedJYs9ifhlO7H5Knil5sg/edit?tab=t.0
    def apply_fades(
        rule: MusicTransitionRule,
        src_fade: MusicFade,
        dst_fade: MusicFade,
        sync_type: SyncType,
    ) -> None:
        src_rule = rule.source_transition_rule
        src_rule.transition_time = src_fade.transition_time
        src_rule.fade_offet = src_fade.offset
        src_rule.fade_curve = src_fade.curve
        src_rule.sync_type = sync_type

        dst_rule = rule.destination_transition_rule
        dst_rule.transition_time = dst_fade.transition_time
        dst_rule.fade_offet = dst_fade.offset
        dst_rule.fade_curve = dst_fade.curve

    if isinstance(tracks, Path):
        tracks = list(tracks)

    for f in tracks:
        if not f.name.endswith(".wem"):
            raise ValueError("All tracks must be .wem files")

    # Prepare the new master state path
    if isinstance(state_path, (str, int)):
        bgm_enemy_type = state_path
        state_path: list[str] = []
        for arg in master.arguments:
            if lookup_name(arg) == "BgmEnemyType":
                state_path.append(bgm_enemy_type)
            else:
                state_path.append("*")

    # Setup the boss phase music manager
    boss_msc = MusicSwitchContainer.new(
        bnk.new_id(),
        [("BossBattleState", GroupType.State)],
        None,
        parent=master.id,
        props={PropID.Priority: 80.0},
    )

    # Default and heatup tracks
    boss_phases = ["*"]
    if len(tracks) > 1:
        boss_phases += [f"HU{i + 1}" for i in range(len(tracks) - 1)]

    boss_state_keys = parse_state_path(boss_phases)
    new_nodes: list[HIRCNode] = [boss_msc]
    phase_masters: list[MusicRandomSequenceContainer] = []

    for i, (phase, bgm) in enumerate(zip(boss_state_keys, tracks)):
        bgm = bnk.add_wem(bgm, SourceType.Streaming)

        phase_mrsc = MusicRandomSequenceContainer.new(bnk.new_id(), parent=boss_msc)
        phase_masters.append(phase_mrsc)

        has_intro = False
        if play_preloop_intro and play_preloop_intro[i]:
            if loop_markers and loop_markers[i] is not None:
                has_intro = True

                main_loop_start = loop_markers[i][0]
                if main_loop_start <= 1000:
                    logger.warning(f"Extremly short intro for phase {i}")

                intro_seg = MusicSegment.new(bnk.new_id(), parent=phase_mrsc)
                intro_track = MusicTrack.new(bnk.new_id(), bgm, parent=intro_seg)

                # Pronounced fade-in
                intro_track.add_clip(
                    ClipAutomationType.FadeIn,
                    [
                        RTPCGraphPoint(0.0, 0.0, CurveInterpolation.Sine),
                        RTPCGraphPoint(0.3, 1.0, CurveInterpolation.Constant),
                    ],
                )

                intro_seg.attach(intro_track)
                intro_seg.duration = intro_track.playlist[0].source_duration

                # Trim track to loop_markers marker
                intro_seg.set_marker(MarkerId.LoopStart.value, 0.0)
                intro_seg.set_marker(MarkerId.LoopEnd.value, main_loop_start)
                intro_track.set_trims(0.0, main_loop_start - 1000)

                # Needs a root playlist item first
                mrs_playlist_root = phase_mrsc.add_playlist_item(
                    bnk.new_id(), 0, ers_type=0
                )
                # Setup playlist item as loop intro
                phase_mrsc.add_playlist_item(
                    bnk.new_id(),
                    intro_seg.id,
                    loop_base=True,
                    parent=mrs_playlist_root,
                )
            else:
                logger.warning(
                    f"Phase {i} has play_intro enabled, but no loop_markers were provided"
                )

        # Setup the segment and music track
        phase_seg = MusicSegment.new(bnk.new_id(), parent=phase_mrsc)
        phase_track = MusicTrack.new(bnk.new_id(), bgm, parent=phase_seg)

        # Pronounced fade in for the track
        phase_track.add_clip(
            ClipAutomationType.FadeIn,
            [
                RTPCGraphPoint(0.0, 0.0, CurveInterpolation.Sine),
                RTPCGraphPoint(0.3, 1.0, CurveInterpolation.Constant),
            ],
        )

        # Add to segment
        track_duration_ms = phase_track.playlist[0].source_duration
        phase_seg.attach(phase_track)
        phase_seg.duration = track_duration_ms

        # Intro to main track transition rule
        if has_intro:
            base_rule = phase_mrsc.music_trans_node_params.transition_rules[0]
            base_rule.source_transition_rule.play_post_exit = 0

            phase_mrsc.add_transition_rule(
                intro_seg.id,
                phase_seg.id,
                SyncType.ExitMarker,
                source_transition_time=1500,
                source_fade_offset=1500,
                source_fade_curve=CurveInterpolation.Log1,
                dest_transition_time=500,
                dest_fade_offset=-500,
                dest_fade_curve=CurveInterpolation.Linear,
                dest_play_pre_entry=True,
            )
        else:
            base_rule = phase_mrsc.music_trans_node_params.transition_rules[0]
            base_rule.destination_transition_rule.play_pre_entry = 1

        # Add markers for looping
        if loop_markers and len(loop_markers) > i and loop_markers[i]:
            loop_start, loop_end = loop_markers[i]
        else:
            loop_start = 0.0
            loop_end = track_duration_ms

        phase_seg.set_marker(MarkerId.LoopStart.value, loop_start)
        # According to Shion this is probably just for testing
        phase_seg.set_marker("LoopCheck", loop_end - 3000)
        phase_seg.set_marker(MarkerId.LoopEnd.value, loop_end)
        # Don't trim the loop track!

        # Add the segment to the music container's playlist
        if not phase_mrsc.playlist_items:
            mrs_playlist_root = phase_mrsc.add_playlist_item(
                bnk.new_id(), 0, ers_type=0
            )
        else:
            mrs_playlist_root = phase_mrsc.playlist_items[0].playlist_item_id

        phase_mrsc.add_playlist_item(
            bnk.new_id(), phase_seg.id, parent=mrs_playlist_root
        )

        # Setup transition rules when repeating song
        if repeat_transitions and i < len(repeat_transitions):
            if i == 0:
                base_rule = phase_mrsc.music_trans_node_params.transition_rules[0]

                apply_fades(base_rule, *repeat_transitions[i], SyncType.ExitMarker)
            else:
                rule = phase_mrsc.add_transition_rule(
                    phase_seg.id,
                    phase_seg.id,
                )
                apply_fades(rule, *repeat_transitions[i], SyncType.ExitMarker)

        # Add this phase to the boss music manager
        boss_msc.add_branch([phase], phase_mrsc.id)

        # Collect the nodes we added
        new_nodes.append(phase_mrsc)
        if has_intro:
            new_nodes.extend((intro_seg, intro_track))
        new_nodes.extend((phase_seg, phase_track))

    # To disable the boss music, presumably not used by bosses you can't run away from
    if add_nobattle_state:
        boss_msc.add_branch(["NoBattle"], 0)

    # Setup phase transition rules
    if default_transition:
        base_rule = boss_msc.music_trans_node_params.transition_rules[0]
        apply_fades(base_rule, *default_transition, SyncType.Immediate)

    if phase_transitions:
        # the "any" phase will use the default transition
        for i in range(1, len(boss_phases) - 1):
            if phase_transitions[i]:
                rule = boss_msc.add_transition_rule(
                    phase_masters[i].id,
                    phase_masters[i + 1].id,
                )
                apply_fades(rule, *phase_transitions[i], SyncType.Immediate)

    if self_transitions:
        # the "any" phase will use the default transition
        for i in range(1, len(boss_phases)):
            if self_transitions[i]:
                rule = boss_msc.add_transition_rule(
                    phase_masters[i].id,
                    phase_masters[i].id,
                )
                apply_fades(rule, *self_transitions[i], SyncType.Immediate)

    # Add new bgm decision branch to master
    master_state_keys: list[int] = parse_state_path(state_path)
    master.add_branch(master_state_keys, boss_msc.id)

    # Add nodes to soundbank
    bnk.add_nodes(*new_nodes)
    return new_nodes


# NOTE for the dialog
# - select master MSC
# - master args:
#   - FallenLeaves yes/no
#   - BgmPlaceType
#   - StateWeatherType
#   - Set_State_EnvPlaceType
# - ambience args (optional except 1st)
#   - OutdoorIndoor (*, Outdoor, IndoorAll, IndoorHalf)
#   - BgmPlaceType (Bgm_550_RoadFortress)
#   - StateWeatherType (_60_SandStorm)
#   - TimeZone (*) 
#   - CommonPlaceType (_14)
# - All tracks should have the loop property and use trims (no loop markers)
def create_ambience(
    bnk: Soundbank,
    master: MusicSwitchContainer,
    state_path: Hash | list[Hash],
    room_states: Hash | list[Hash],
    room_tracks: dict[tuple[str], Path],
    *,
    trims: list[tuple[float, float]] = None,
) -> list[HIRCNode]:
    if isinstance(state_path, (str, int)):
        state_path = [state_path]

    # TODO top state should always be OutdoorIndoor
    if isinstance(room_states, (str, int)):
        room_states = [room_states]

    ambience_msc = MusicSwitchContainer.new(
        bnk.new_id(),
        [(rs, GroupType.State) for rs in room_states],
        props={PropID.Priority, 80.0},
    )

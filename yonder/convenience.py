from pathlib import Path
from dataclasses import dataclass

from yonder import Soundbank, Node
from yonder.datatypes import GraphPoint
from yonder.node_types import (
    Event,
    Action,
    RandomSequenceContainer,
    Sound,
    MusicSwitchContainer,
    MusicRandomSequenceContainer,
    MusicSegment,
    MusicTrack,
)
from yonder.hash import lookup_name
from yonder.enums import CurveType
from yonder.util import logger


@dataclass(slots=True)
class Fade:
    duration: int = 0
    offset: int = 0
    curve: CurveType = "Linear"


def create_simple_sound(
    bnk: Soundbank,
    event_name: str,
    wems: list[Path] | Path,
    actor_mixer: int | Node,
    avoid_repeats: bool = False,
    properties: dict[str, float] = None,
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

    rsc = RandomSequenceContainer.new(
        bnk.new_id(),
        avoid_repeats=avoid_repeats,
        loop_count=1,
        parent=actor_mixer,
    )
    if properties:
        for key, val in properties.items():
            rsc.set_property(key, val)
    rsc.avoid_repeats = avoid_repeats

    sounds = []
    for w in wems:
        snd = Sound.new_from_wem(bnk.new_id(), w, parent=rsc)
        rsc.add_child(snd)
        sounds.append(snd)

    play = Event.new(f"Play_{event_name}")
    play_action = Action.new_play_action(bnk.new_id(), rsc.id)
    play.add_action(play_action)

    stop = Event.new(f"Stop_{event_name}")
    stop_action = Action.new_stop_action(bnk.new_id(), rsc.id)
    stop.add_action(stop_action)

    # Add the RSC to the actor mixer
    if isinstance(actor_mixer, int):
        if actor_mixer == 0:
            logger.warning(
                f"No ActorMixer specified for RSC {rsc.id} of new sound {event_name}"
            )
        else:
            amx_node = bnk.get(actor_mixer)
            if not amx_node:
                logger.warning(
                    f"ActorMixer {actor_mixer} not found in soundbank {bnk}. If it is part of another soundbank, make sure to add the RSC's ID ({rsc.id}) to its children!"
                )
            else:
                amx_node.cast().add_child(rsc)
    elif isinstance(actor_mixer, Node):
        actor_mixer.cast().add_child(rsc)

    bnk.add_nodes(rsc, *sounds, play, play_action, stop, stop_action)
    for w in wems:
        bnk.add_wem(w, "Embedded")

    return ((play, stop), rsc, sounds)


def create_boss_bgm(
    bnk: Soundbank,
    master: MusicSwitchContainer,
    state_path: str | list[str | int],
    tracks: list[Path] | Path,
    track_markers: list[tuple[float, float]] = None,
    add_nobattle_state: bool = True,
    *,
    default_transition: tuple[Fade, Fade] = None,
    phase_transitions: list[tuple[Fade, Fade]] = None,
    self_transitions: list[tuple[Fade, Fade]] = None,
    repeat_transitions: list[tuple[Fade, Fade]] = None,
) -> list[Node]:
    # An overview of what's happening:
    # https://docs.google.com/document/d/1Dx8U9q6iEofPtKtZ0JI1kOedJYs9ifhlO7H5Knil5sg/edit?tab=t.0
    def apply_fades(rule: dict, src_fade: Fade, dst_fade: Fade) -> None:
        # TODO create a proper transition rule type
        src_rule = rule["source_transition_rule"]
        src_rule["transition_time"] = src_fade.duration
        src_rule["fade_offset"] = src_fade.offset
        src_rule["fade_curve"] = src_fade.curve

        dst_rule = rule["destination_transition_rule"]
        dst_rule["transition_time"] = dst_fade.duration
        dst_rule["fade_offset"] = dst_fade.offset
        dst_rule["fade_curve"] = dst_fade.curve

    if isinstance(tracks, Path):
        tracks: list[Path] = tracks

    for f in tracks:
        if not f.name.endswith(".wem"):
            raise ValueError("All tracks must be .wem files")

    # Prepare the new master state path
    if isinstance(state_path, str):
        bgm_enemy_type = state_path
        state_path: list[str] = []
        for arg in master.arguments:
            if lookup_name(arg) == "BgmEnemyType":
                state_path.append(bgm_enemy_type)
            else:
                state_path.append("*")

    # Setup the boss phase music manager
    boss_msc = MusicSwitchContainer.new(
        bnk.new_id(), ["BossBattleState"], parent=master
    )

    # Default and heatup tracks
    boss_phases = ["*"]
    if len(tracks) > 1:
        boss_phases += [f"HU{i + 1}" for i in range(len(tracks) - 1)]

    boss_state_keys = MusicSwitchContainer.parse_state_path(boss_phases)
    children: list[Node] = []
    phase_masters: list[MusicRandomSequenceContainer] = []

    for i, (phase, bgm) in enumerate(zip(boss_state_keys, tracks)):
        phase_mrs = MusicRandomSequenceContainer.new(bnk.new_id(), parent=boss_msc)
        phase_masters.append(phase_mrs)

        # Setup the segment and music track
        phase_seg = MusicSegment.new(bnk.new_id(), parent=phase_mrs)
        phase_track = MusicTrack.new_from_wem(bnk.new_id(), bgm, parent=phase_seg)
        
        # Pronounced fade in for the track
        phase_track.add_clip(
            "FadeIn", [GraphPoint(0.0, 0.0, "Sine"), GraphPoint(0.2, 1.0, "Constant")]
        )
        
        # Add to segment
        track_duration_ms = phase_track.playlist[0]["source_duration"]
        phase_seg.add_child(phase_track)
        phase_seg.duration = track_duration_ms

        # Add markers for looping
        if track_markers and len(track_markers) > i and track_markers[i]:
            loop_start, loop_end = track_markers[i]
        else:
            loop_start = 0.0
            loop_end = track_duration_ms / 1000

        phase_seg.set_marker(MusicSegment.loop_start_id, loop_start * 1000)
        # According to Shion this is probably just for testing
        phase_seg.set_marker("LoopCheck", track_duration_ms - 3000)
        phase_seg.set_marker(MusicSegment.loop_end_id, loop_end * 1000)

        # Add the segment to the music container's playlist. First item always uses weight?
        item_key = phase_mrs.add_playlist_item(bnk.new_id(), 0, avoid_repeat=1)
        phase_mrs.add_playlist_item(
            bnk.new_id(), phase_seg.id, parent=item_key, ers_type=4294967295
        )

        # Setup transition rules when repeating song
        if repeat_transitions and repeat_transitions[i]:
            if i == 0:
                apply_fades(phase_mrs.transition_rules[0], *repeat_transitions[i])
            else:
                rule = phase_mrs.add_transition_rule(phase_seg.id, phase_seg.id)
                apply_fades(rule, *repeat_transitions[i])

        # Add this phase to the boss' music manager
        boss_msc.add_branch([phase], phase_mrs.id)
        children.extend(
            [
                phase_mrs,
                phase_seg,
                phase_track,
            ]
        )

    # To disable the boss music, presumably not used by bosses you can't run away from
    if add_nobattle_state:
        boss_msc.add_branch(["NoBattle"], 0)

    # Setup phase transition rules
    if default_transition:
        rule = boss_msc.transition_rules[0]
        apply_fades(rule, *default_transition)

    if phase_transitions:
        # the "any" phase will use the default transition
        for i in range(boss_phases[1:-1]):
            if phase_transitions[i]:
                rule = boss_msc.add_transition_rule(
                    phase_masters[i].id,
                    phase_masters[i + 1].id,
                )
                apply_fades(rule, *phase_transitions[i])

    if self_transitions:
        # the "any" phase will use the default transition
        for i in range(boss_phases[1:]):
            if self_transitions[i]:
                rule = boss_msc.add_transition_rule(
                    phase_masters[i].id,
                    phase_masters[i].id,
                )
                apply_fades(rule, *self_transitions[i])

    # Add new bgm decision branch to master
    master_state_keys: list[int] = MusicSwitchContainer.parse_state_path(state_path)
    master.add_branch(master_state_keys, boss_msc.id)

    # Add nodes and wems to soundbank
    bnk.add_nodes(boss_msc, *children)
    for bgm in tracks:
        bnk.add_wem(bgm, "Streaming")

    return (boss_msc, children)

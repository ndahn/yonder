from __future__ import annotations
from typing import Callable
from dataclasses import dataclass, field
from pathlib import Path
import math
import networkx as nx
import pyo
from pyo import sndinfo

from yonder import Soundbank, HIRCNode, Hash, calc_hash
from yonder.types import Sound, MusicTrack, MusicSegment, State
from yonder.types.base_types import (
    RTPC,
    StateGroup,
    ClipAutomation,
    RTPCGraphPoint,
    ConversionTable,
)
from yonder.types.mixins import PropertyMixin, StateMixin
from yonder.enums import (
    PropID,
    RtpcAccum,
    MarkerId,
    ClipAutomationType,
    WwiseCutoffFrequencies,
    CurveInterpolation,
    CurveScaling,
)
from yonder.interpolation import interpolate
from yonder.util import logger
from yonder.game import GameObjects


def db_to_amp(db: float) -> float:
    # volume properties are stored in dB
    return 10.0 ** (db / 20.0)


def lpf_to_hz(val: float) -> float:
    return interpolate(
        CurveInterpolation.Linear,
        val - int(val),
        WwiseCutoffFrequencies[int(val)],
        WwiseCutoffFrequencies[int(val) + 1],
    )


def hpf_to_hz(val: float) -> float:
    val = 100 - val
    return interpolate(
        CurveInterpolation.Linear,
        1.0 - (val - int(val)),
        WwiseCutoffFrequencies[int(val) - 1],
        WwiseCutoffFrequencies[int(val)],
    )


def cents_to_speed(cents: float) -> float:
    # pitch properties are stored in cents, applied as playback speed
    return 2.0 ** (cents / 1200.0)


def to_pyo_domain(prop: PropID, val: float) -> float:
    if prop == PropID.Volume:
        return db_to_amp(val)
    elif prop == PropID.LPF:
        return lpf_to_hz(val)
    elif prop == PropID.HPF:
        return hpf_to_hz(val)
    elif prop == PropID.Pitch:
        return cents_to_speed(val)
    else:
        raise ValueError(f"Unhandled property {prop}")


def make_envelope(
    points: list[RTPCGraphPoint],
    conv: Callable[[float], float] = None,
    resolution: int = 8,
) -> pyo.Linseg:
    if not conv:
        conv = lambda v: v

    segs = []
    if points[0].from_ > 0.0:
        # Constant before first point
        segs.append((0.0, conv(points[0].to)))

    for p, nxt in zip(points[:-1], points[1:]):
        span = nxt.from_ - p.from_
        if span <= 0.0:
            continue

        n = int(span * resolution)
        for i in range(n):
            t = i / n
            val = interpolate(p.interpolation, t, p.to, nxt.to)
            segs.append((p.from_ + t * span, conv(val)))

    # Extrapolate past final point
    segs.append((points[-1].from_, conv(points[-1].to)))
    return pyo.Linseg(segs)


def eval_curve(
    points: list[RTPCGraphPoint], x: float, scaling: CurveScaling = CurveScaling.None_
) -> float:
    if x <= points[0].from_:
        return points[0].to

    if x >= points[-1].from_:
        return points[-1].to

    for p, nxt in zip(points[:-1], points[1:]):
        if x > p.from_:
            t = (x - p.from_) / (nxt.from_ - p.from_)
            y = interpolate(p.interpolation, t, p.to, nxt.to)
            break

    # TODO verify DB/Log against known banks: likely means the y axis is
    # dB/log so interpolation should happen in the scaled domain
    if scaling == CurveScaling.DBToLin:
        return db_to_amp(y)
    elif scaling == CurveScaling.Log:
        # TODO unverified: y is a linear ratio on a log-shaped curve;
        # convert to dB so it stays additive with the rest of the accumulator.
        return 20.0 * math.log10(max(y, 1e-9))
    elif scaling == CurveScaling.DB:
        # y already sits in the same dB domain we accumulate in
        pass

    return y


def accumulate(base: float, val: float, accum: RtpcAccum) -> float:
    if accum == RtpcAccum.Additive:
        return base + val
    elif accum == RtpcAccum.Multiply:
        return base * val
    elif accum == RtpcAccum.Boolean:
        return val if val > 0 else base
    elif accum == RtpcAccum.Maximum:
        return max(base, val)
    elif accum == RtpcAccum.Filter:
        # lpf/hpf are stored as 0-100 percent where higher = more filtering,
        # so "most restrictive wins" is the same operation as maximum
        return max(base, val)
    elif accum == RtpcAccum.Exclusive:
        return val

    return base


@dataclass
class StateCtrl:
    group: Hash
    state: Hash
    adjustment: float
    accum: RtpcAccum


@dataclass
class PlaybackProperty:
    value: float = 0.0
    rtpcs: list[RTPC] = field(default_factory=list)
    states: list[StateCtrl] = field(default_factory=list)
    # TODO attenuations
    clips: list[ConversionTable] = field(default_factory=list)


@dataclass
class PlaybackContext:
    properties: dict[PropID, PlaybackProperty] = field(default_factory=dict)
    loop: bool = False
    loop_start: float = 0.0
    loop_end: float = 0.0

    def __post_init__(self):
        self.properties = {
            PropID.Pitch: PlaybackProperty(),
            PropID.HPF: PlaybackProperty(),
            PropID.LPF: PlaybackProperty(),
            PropID.Volume: PlaybackProperty(),
        }


@dataclass
class Voice:
    audiofile: Path = None
    ctx: PlaybackContext = field(default_factory=PlaybackContext)
    ctrls: dict[PropID, pyo.SigTo] = field(default_factory=dict)
    chain: list[pyo.PyoObject] = field(default_factory=list)

    def __post_init__(self):
        self.ctrls = {
            PropID.Pitch: pyo.SigTo(cents_to_speed(0.0), 0.05),
            PropID.HPF: pyo.SigTo(17.0, 0.05),
            PropID.LPF: pyo.SigTo(20000.0, 0.05),
            PropID.Volume: pyo.SigTo(db_to_amp(0.0), 0.05),
        }

    def build(self) -> pyo.PyoObject:
        c = self.ctrls
        envelopes = []

        gain = c[PropID.Volume]
        for curve in self.ctx.properties[PropID.Volume].clips:
            env = make_envelope(curve.points, db_to_amp)
            gain *= env
            envelopes.append(env)

        hp_freq = c[PropID.HPF]
        for curve in self.ctx.properties[PropID.HPF].clips:
            env = make_envelope(curve.points, hpf_to_hz)
            hp_freq *= env
            envelopes.append(env)

        lp_freq = c[PropID.LPF]
        for curve in self.ctx.properties[PropID.LPF].clips:
            env = make_envelope(curve.points, lpf_to_hz)
            lp_freq *= env
            envelopes.append(env)

        if self.ctx.loop:
            if self.ctx.loop_end <= self.ctx.loop_start:
                self.ctx.loop_end = sndinfo(str(self.audiofile))[1]

            # marker loop: SfPlayer only loops whole files, Looper loops a table region
            table = pyo.SndTable(str(self.audiofile))
            src = pyo.Looper(
                table,
                pitch=c[PropID.Pitch],
                start=self.ctx.loop_start,
                dur=self.ctx.loop_end - self.ctx.loop_start,
                xfade=0,
                startfromloop=False,  # play intro once, then loop the region
            )
        else:
            src = pyo.SfPlayer(
                str(self.audiofile), speed=c[PropID.Pitch], loop=self.ctx.loop
            )

        # fixed order for all voices: source -> HPF -> LPF -> gain
        hp = pyo.ButHP(src, freq=hp_freq)
        lp = pyo.ButLP(hp, freq=lp_freq)
        tail = lp * gain

        self.chain = [*envelopes, src, hp, lp, gain, tail]
        return tail

    def update(
        self,
        rtpc_params: dict[Hash, float] = None,
        active_states: dict[Hash, list[Hash]] = None,
    ) -> None:
        if not rtpc_params:
            rtpc_params = {}

        if not active_states:
            active_states = {}

        rtpc_params = {calc_hash(k): v for k, v in rtpc_params.items()}

        for prop, p in self.ctx.properties.items():
            val = p.value

            # RTPCs
            for rtpc in p.rtpcs:
                x = rtpc_params.get(rtpc.param_id, 0.0)
                y = eval_curve(rtpc.graph_points, x, rtpc.curve_scaling)
                val = accumulate(val, y, rtpc.rtpc_accum)

            # States
            for group, states in active_states.items():
                group = calc_hash(group)
                states = set(calc_hash(s) for s in states)

                for s in p.states:
                    if s.group == group and s.state in states:
                        # TODO how to respect in_db from StatePropertyInfo?
                        val = accumulate(val, s.adjustment, s.accum)

            # TODO Attenuations

            self.ctrls[prop].value = to_pyo_domain(prop, val)

    def start(self) -> None:
        for obj in self.chain:
            obj.play()

    def stop(self) -> None:
        for obj in self.chain:
            obj.stop()


class NewPlayer:
    def __init__(self):
        self._default_fade_time = 0.05
        self._voices: list[Voice] = []

        self._server = pyo.Server().boot()
        # mixes the voice branches; time smooths per-voice amp changes
        self._mixer = pyo.Mixer(outs=1, chnls=1, time=self._default_fade_time)
        # final volume adjustment
        self._gate = pyo.SigTo(value=1.0, time=self._default_fade_time)
        # master chain: mixer -> gate -> dac
        self._master = self._mixer[0] * self._gate
        self._master.out()

    def __del__(self):
        self._server.stop()
        self._server.shutdown()
        self._server = None

    def start(self) -> None:
        self._server.start()

    def stop(self) -> None:
        self._server.stop()

    def play(self) -> None:
        for voice in self._voices:
            voice.start()

    def set_volume(self, vol: float) -> None:
        self._gate.setValue(vol, time=self._default_fade_time)

    def set_muted(self, muted: bool) -> None:
        self._gate.setValue(0.0 if muted else 1.0, time=self._default_fade_time)

    def fade(self, target_vol: float, duration: float) -> None:
        self._gate.setValue(target_vol, time=duration)

    def __getitem__(self, idx: int) -> Voice:
        return self._voices[idx]

    def __len__(self) -> int:
        return len(self._voices)

    def from_hierarchy(
        self, bnk: Soundbank, root: int | HIRCNode, full_tree: bool = False
    ) -> NewPlayer:
        self.stop()

        if isinstance(root, HIRCNode):
            root = root.id

        if full_tree:
            root, tree = next(bnk.find_event_subgraphs_for(root))
        else:
            tree = bnk.get_subtree(root, True)

        leafs = [n for (n, d) in tree.out_degree if d == 0]
        voices: dict[int, Voice] = {}

        for branch in nx.all_simple_paths(tree, root, leafs):
            leaf_id = branch[-1]

            if leaf_id in voices:
                logger.warning(
                    f"Player will ignore secondary paths to {leaf_id} ({branch})"
                )
                continue

            voice = Voice()
            voices[leaf_id] = voice
            leaf_node = bnk.get(leaf_id)

            if isinstance(leaf_node, Sound):
                voice.audiofile = bnk.get_wem_path(
                    leaf_node.source_id, leaf_node.bank_source_data.source_type
                )
            elif isinstance(leaf_node, MusicTrack):
                # TODO what to do with tracks that have multiple sources?
                voice.audiofile = bnk.get_wem_path(
                    leaf_node.source_ids[0], leaf_node.sources[0].source_type
                )
                voice.ctx.loop = True

                # TODO trims
                for clip in leaf_node.clip_items:
                    # TODO how to store these in ctx?
                    pass

            voice = voices[leaf_id]

            for nid in reversed(branch[:-1]):
                node = bnk[nid]

                # Collect properties
                if isinstance(node, PropertyMixin):
                    for bundle in node.properties:
                        if bundle.prop_enum in voice.ctx.properties:
                            voice.ctx.properties[bundle.prop_enum] += bundle.value
                        elif bundle.prop_enum == PropID.Loop:
                            voice.ctx.loop = True
                        else:
                            # Other properties are ignored for now
                            pass

                # Collect states
                if isinstance(node, StateMixin):
                    # Find out which param idx controls the property
                    for prop in (PropID.Volume, PropID.LPF, PropID.HPF, PropID.Pitch):
                        prop_idx = None
                        accum = None
                        for idx, prop_info in enumerate(
                            node.states.state_property_info
                        ):
                            if prop_info.property == prop:
                                prop_idx = idx
                                accum = prop_info.accum_type
                                break
                        else:
                            continue

                        # Property found, look for states that affect it
                        for chunk in node.states.state_group_chunks:
                            for state_value in chunk.states:
                                state: State = bnk.get(state_value.state_instance_id)
                                if state:
                                    if state.has_param_for(prop_idx):
                                        adjust = state.get_param(prop_idx)
                                    elif state.has_default():
                                        adjust = state.get_default()
                                    else:
                                        continue

                                    voice.ctx.properties[prop].states.append(
                                        StateCtrl(
                                            chunk.state_group_id,
                                            state_value,
                                            adjust,
                                            accum,
                                        )
                                    )

                # Collect rtpcs
                if hasattr(node, "rtpcs"):
                    rtpc: RTPC
                    for rtpc in node.rtpcs:
                        param = GameObjects.RTPCParameter(rtpc.param_id).name

                        # TODO make a better way to compare these
                        if param == "Pitch":
                            voice.ctx.properties[PropID.Pitch].rtpcs.append(rtpc)
                        elif param == "HPF":
                            voice.ctx.properties[PropID.HPF].rtpcs.append(rtpc)
                        elif param == "LPF":
                            voice.ctx.properties[PropID.LPF].rtpcs.append(rtpc)
                        elif param == "Volume":
                            voice.ctx.properties[PropID.Volume].rtpcs.append(rtpc)
                        else:
                            # Unknown param
                            pass

                # TODO Collect attenuations

                if isinstance(node, MusicSegment):
                    voice.ctx.loop_start = node.get_marker_pos(MarkerId.LoopStart) / 1000.0
                    voice.ctx.loop_end = node.get_marker_pos(MarkerId.LoopEnd) / 1000.0

        # build one pyo chain per leaf and register it as a mixer voice
        for idx, voice in enumerate(voices.values()):
            if voice.audiofile is None:
                continue

            tail = voice.build()
            voice.stop()
            self._mixer.addInput(idx, tail)
            self._mixer.setAmp(idx, 0, 1.0)

        self._voices = list(voices.values())
        return self

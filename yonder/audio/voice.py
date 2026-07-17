from __future__ import annotations
from typing import Callable
from dataclasses import dataclass, field
from pathlib import Path

# If there is no official wheel yet:
# pip install -i https://test.pypi.org/simple/ pyo
import pyo
from pyo import sndinfo

from yonder import Hash, calc_hash
from yonder.types.base_types import (
    RTPC,
    ClipAutomation,
)
from yonder.enums import (
    PropID,
    RtpcAccum,
    ClipAutomationType,
    CurveScaling,
)

from .audiomath import (
    db_to_amp,
    hpf_to_hz,
    lpf_to_hz,
    cents_to_speed,
    make_envelope,
    eval_curve,
    accumulate,
    to_pyo_domain,
)


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
    clips: list[ClipAutomation] = field(default_factory=list)


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
    on_voice_finished: Callable[[], None] = None
    _trig_finished: pyo.TrigFunc = None

    def __post_init__(self):
        self.ctrls = {
            PropID.Pitch: pyo.SigTo(cents_to_speed(0.0), 0.05),
            PropID.HPF: pyo.SigTo(17.0, 0.05),
            PropID.LPF: pyo.SigTo(20000.0, 0.05),
            PropID.Volume: pyo.SigTo(db_to_amp(0.0), 0.05),
        }

    def _finished(self) -> None:
        if self.on_voice_finished:
            self.on_voice_finished()

    def _build(self) -> pyo.PyoObject:
        c = self.ctrls
        envelopes = []

        gain = c[PropID.Volume]
        for clip in self.ctx.properties[PropID.Volume].clips:
            if clip.auto_type == ClipAutomationType.Volume:
                env = make_envelope(clip.graph_points, CurveScaling.DB, db_to_amp)
            else:
                # Fades are already normalized to 0..1, no conversion needed
                env = make_envelope(clip.graph_points, CurveScaling.DB, None)

            gain *= env
            envelopes.append(env)

        hp_freq = c[PropID.HPF]
        for clip in self.ctx.properties[PropID.HPF].clips:
            env = make_envelope(clip.graph_points, CurveScaling.Log, hpf_to_hz)
            hp_freq *= env
            envelopes.append(env)

        lp_freq = c[PropID.LPF]
        for clip in self.ctx.properties[PropID.LPF].clips:
            env = make_envelope(clip.graph_points, CurveScaling.Log, lpf_to_hz)
            lp_freq *= env
            envelopes.append(env)

        # ClipAutomation does not support pitch

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
        self._trig_finished = pyo.TrigFunc(src["trig"], self._finished)
        return tail

    def update(
        self,
        rtpc_params: dict[Hash, float] = None,
        active_states: dict[Hash, list[Hash]] = None,
        distance: float = 0.0,
        angle: float = 0.0,
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

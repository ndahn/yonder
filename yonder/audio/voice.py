from __future__ import annotations
from typing import Callable
from dataclasses import dataclass, field
import pyo

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
from .stream_source import StreamSource


@dataclass
class StateCtrl:
    group: Hash
    state: Hash
    adjustment: float
    accum: RtpcAccum


@dataclass(init=False)
class ModifierStack:
    value: float = 0.0
    rtpcs: list[RTPC] = field(default_factory=list)
    states: list[StateCtrl] = field(default_factory=list)
    # TODO attenuations
    clips: list[ClipAutomation] = field(default_factory=list)
    ctrl: pyo.SigTo = None

    def __init__(self, ctrl_default: float, time: float = 0.05):
        self.ctrl = pyo.SigTo(ctrl_default, time=time)


@dataclass
class Voice:
    src: StreamSource
    mod: dict[PropID, ModifierStack] = field(default_factory=dict)
    chain: list[pyo.PyoObject] = field(default_factory=list)
    on_voice_finished: Callable[[], None] = None
    _trig_finished: pyo.TrigFunc = None

    def __post_init__(self):
        self.mod = {
            PropID.Pitch: ModifierStack(cents_to_speed(0.0)),
            PropID.HPF: ModifierStack(17.0),
            PropID.LPF: ModifierStack(20000.0),
            PropID.Volume: ModifierStack(db_to_amp(0.0)),
        }

    def _finished(self) -> None:
        if self.on_voice_finished:
            self.on_voice_finished()

    def _build(self) -> pyo.PyoObject:
        c = self.mod
        envelopes = []

        gain = c[PropID.Volume].ctrl
        for clip in c[PropID.Volume].clips:
            if clip.auto_type == ClipAutomationType.Volume:
                env = make_envelope(clip.graph_points, CurveScaling.DB, db_to_amp)
            else:
                # Fades are already normalized to 0..1, no conversion needed
                env = make_envelope(clip.graph_points, CurveScaling.DB, None)

            gain *= env
            envelopes.append(env)

        hp_freq = c[PropID.HPF].ctrl
        for clip in c[PropID.HPF].clips:
            env = make_envelope(clip.graph_points, CurveScaling.Log, hpf_to_hz)
            hp_freq *= env
            envelopes.append(env)

        lp_freq = c[PropID.LPF].ctrl
        for clip in c[PropID.LPF].clips:
            env = make_envelope(clip.graph_points, CurveScaling.Log, lpf_to_hz)
            lp_freq *= env
            envelopes.append(env)

        # NOTE: ClipAutomation does not support pitch

        # fixed order for all voices: source -> HPF -> LPF -> gain
        hp = pyo.ButHP(self.src, freq=hp_freq)
        lp = pyo.ButLP(hp, freq=lp_freq)
        tail = lp * gain

        # Add self.src to the chain too so it's easier to start and stop everything
        self.chain = [*envelopes, self.src, hp, lp, gain, tail]
        self._trig_finished = pyo.TrigFunc(self.src["trig"], self._finished)
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

        for prop, p in self.mod.items():
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

            self.mod[prop].ctrl.value = to_pyo_domain(prop, val)

    def start(self) -> None:
        for obj in self.chain:
            obj.play()

    def stop(self) -> None:
        for obj in self.chain:
            obj.stop()

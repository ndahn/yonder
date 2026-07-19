from __future__ import annotations
from dataclasses import dataclass, field
import pyo

from yonder import Soundbank, HIRCNode, Hash, calc_hash
from yonder.types.base_types import (
    RTPC,
    ClipAutomation,
    ConversionTable,
)
from yonder.types import State, Attenuation
from yonder.types.mixins import PropertyMixin, StateMixin
from yonder.enums import (
    PropID,
    RtpcAccum,
    ClipAutomationType,
    CurveParameters,
    CurveScaling,
)
from yonder.game import GameObjects

from .audiomath import (
    db_to_amp,
    hpf_to_hz,
    lpf_to_hz,
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
    attenuations: list[ConversionTable] = field(default_factory=list)
    clips: list[ClipAutomation] = field(default_factory=list)
    ctrl: pyo.SigTo = None

    def __init__(self, ctrl_default: float, time: float = 0.05):
        self.ctrl = pyo.SigTo(ctrl_default, time=time)


class VoiceBuilder:
    def __init__(self, src: StreamSource):
        self.src = src
        self.mod: dict[PropID, ModifierStack] = {
            PropID.Pitch: ModifierStack(0.0),  # semitones
            PropID.HPF: ModifierStack(hpf_to_hz(0)),  # Hz
            PropID.LPF: ModifierStack(lpf_to_hz(0)),  # Hz
            PropID.Volume: ModifierStack(db_to_amp(0.0)),  # factor
        }

    def collect_modifiers(self, bnk: Soundbank, node: HIRCNode) -> VoiceBuilder:
        atten: Attenuation = None

        # Properties
        if isinstance(node, PropertyMixin):
            for bundle in node.properties:
                if bundle.prop_enum in self.mod:
                    self.mod[bundle.prop_enum].value += bundle.value
                elif bundle.prop_enum == PropID.Loop:
                    self.src.loop = True
                elif bundle.prop_enum == PropID.LoopStart:
                    self.src.loop_start = bundle.value / 1000.0
                elif bundle.prop_enum == PropID.LoopEnd:
                    # TODO verify that this is always positive
                    self.src.loop_end = bundle.value / 1000.0
                elif bundle.prop_enum == PropID.AttenuationID:
                    atten = bnk.get(int(bundle.value))
                # Other properties to consider:
                # - Probability
                else:
                    # Other properties are ignored for now
                    pass

        # States
        if isinstance(node, StateMixin):
            # Find out which param idx controls the property
            for prop in (PropID.Volume, PropID.LPF, PropID.HPF, PropID.Pitch):
                prop_idx = None
                accum = None
                for idx, prop_info in enumerate(node.states.state_property_info):
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

                            self.mod[prop].states.append(
                                StateCtrl(
                                    chunk.state_group_id,
                                    state_value,
                                    adjust,
                                    accum,
                                )
                            )

        # RTPCs
        if hasattr(node, "rtpcs"):
            rtpc: RTPC
            for rtpc in node.rtpcs:
                param = GameObjects.RTPCParameter(rtpc.param_id).name

                # TODO provide a better way to compare these
                if param == "Pitch":
                    self.mod[PropID.Pitch].rtpcs.append(rtpc)
                elif param == "HPF":
                    self.mod[PropID.HPF].rtpcs.append(rtpc)
                elif param == "LPF":
                    self.mod[PropID.LPF].rtpcs.append(rtpc)
                elif param == "Volume":
                    self.mod[PropID.Volume].rtpcs.append(rtpc)
                else:
                    # Unknown param
                    pass

        # Attenuations
        if atten:
            for param, prop in [
                (CurveParameters.VolumeDry, PropID.Volume),
                (CurveParameters.HPF, PropID.HPF),
                (CurveParameters.LPF, PropID.LPF),
            ]:
                curve_idx = atten.curves_to_use[param.value]
                if curve_idx >= 0 and curve_idx < len(atten.curves):
                    curve = atten.curves[curve_idx]
                    self.mod[prop].attenuations.append(curve)

        return self

    def build(self) -> Voice:
        c = self.mod
        envelopes = []

        gain = c[PropID.Volume].ctrl
        for clip in c[PropID.Volume].clips:
            if clip.auto_type == ClipAutomationType.Volume:
                env = make_envelope(clip.graph_points, CurveScaling.DB, db_to_amp)
            else:
                # Fades are already normalized to 0..1, no conversion needed
                env = make_envelope(clip.graph_points, CurveScaling.None_, None)

            # SigTo ──┐
            #         ├─(×)──┐
            # env1 ───┘      ├─(×)──> out signal
            # env2 ──────────┘
            gain *= env
            envelopes.append(env)

        hp_freq = c[PropID.HPF].ctrl
        for clip in c[PropID.HPF].clips:
            # clip y-axis is percent (0-100), which interpolates linearly;
            # the log-frequency behavior lives inside the percent->hz table
            env = make_envelope(clip.graph_points, CurveScaling.None_, hpf_to_hz)
            hp_freq *= env
            envelopes.append(env)

        lp_freq = c[PropID.LPF].ctrl
        for clip in c[PropID.LPF].clips:
            env = make_envelope(clip.graph_points, CurveScaling.None_, lpf_to_hz)
            lp_freq *= env
            envelopes.append(env)

        # NOTE: ClipAutomation and attenuation do not support pitch
        # transpo is in semitones; winsize trades latency vs. smearing
        # better, but more costly: PVAnal -> PVTranspoe -> PVSynth
        pitch = pyo.Harmonizer(self.src, transpo=c[PropID.Pitch].ctrl, winsize=0.1)

        # fixed order for all voices: source -> pitch -> HPF -> LPF -> gain
        hp = pyo.ButHP(pitch, freq=hp_freq)
        lp = pyo.ButLP(hp, freq=lp_freq)
        tail = lp * gain

        chain = [*envelopes, pitch, hp, lp, gain, tail]
        return Voice(self.src, c, chain)


class Voice(pyo.PyoObject):
    def __init__(
        self,
        src: StreamSource,
        modifiers: dict[PropID, ModifierStack],
        effect_chain: list[pyo.PyoObject],
        mul: float = 1,
        add: float = 0,
    ):
        pyo.PyoObject.__init__(self, mul, add)
        self.src = src
        self.modifiers = modifiers
        self.chain = effect_chain
        self._trig = pyo.Trig()
        self._fwd = pyo.TrigFunc(src["trig"], self._on_finished)
        self._base_objs = self.tail.getBaseObjects()

    @property
    def tail(self) -> pyo.PyoObject:
        return self.chain[-1]

    def update(
        self,
        rtpc_params: dict[Hash, float] = None,
        active_states: dict[Hash, list[Hash]] = None,
        distance: float = 0.0,
    ) -> None:
        if not rtpc_params:
            rtpc_params = {}

        if not active_states:
            active_states = {}

        rtpc_params = {calc_hash(k): v for k, v in rtpc_params.items()}

        for prop, p in self.modifiers.items():
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

            # Attenuations
            for curve in p.attenuations:
                val += eval_curve(curve.points, distance, curve.curve_scaling)

            self.modifiers[prop].ctrl.value = to_pyo_domain(prop, val)

    def play(self, dur: float = 0, delay: float = 0) -> pyo.PyoObject:
        self.src.play()

        for obj in self.chain:
            obj.play()

        return pyo.PyoObject.play(self, dur, delay)

    def stop(self, wait: float = 0) -> None:
        self.src.stop()

        for obj in self.chain:
            obj.stop()

        return pyo.PyoObject.stop(self, wait)

    def out(
        self, chnl: int = 0, inc: int = 1, dur: float = 0, delay: float = 0
    ) -> pyo.PyoObject:
        self.play()
        return pyo.PyoObject.out(self, chnl, inc, dur, delay)

    def _on_finished(self) -> None:
        self._trig.play()

    def __getitem__(self, key: str):
        if key == "trig":
            return self._trig
        
        return pyo.PyoObject.__getitem__(self, key)

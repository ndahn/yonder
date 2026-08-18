import pyo

from yonder.types.base_types import ClipAutomation
from yonder.enums import ClipAutomationType, CurveScaling
from yonder.audio.audiomath import hpf_to_hz, lpf_to_hz, db_to_amp, make_envelope


class PropertyControl(pyo.PyoObject):
    def __init__(
        self,
        source: pyo.PyoObject,
        gain_db: float = 0,
        hpf_cents: float = 0,
        lpf_hz: float = 0,
        pitch_semitones: float = 0,
        clip_automations: list[ClipAutomation] = None,
        mul: float = 1,
        add: float = 0,
    ):
        pyo.PyoObject.__init__(self, mul, add)

        if not clip_automations:
            clip_automations = []

        self._build(
            source,
            gain_db,
            hpf_cents,
            lpf_hz,
            pitch_semitones,
            clip_automations,
        )
        self._base_objs = self.tail().getBaseObjects()

    def _build(
        self,
        source: pyo.PyoObject,
        gain_db: float,
        hpf_cents: float,
        lpf_hz: float,
        pitch_semitones: float,
        clip_automations: list[ClipAutomation],
    ) -> None:
        self._gain_ctrl = pyo.SigTo(db_to_amp(gain_db), time=0.05)
        self._hpf_ctrl = pyo.SigTo(hpf_to_hz(hpf_cents), time=0.05)
        self._lpf_ctrl = pyo.SigTo(lpf_to_hz(lpf_hz), time=0.05)
        self._pitch_ctrl = pyo.SigTo(pitch_semitones, time=0.05)
        envelopes = []

        for clip in clip_automations:
            if clip.auto_type == ClipAutomationType.Volume:
                env = make_envelope(clip.graph_points, CurveScaling.DB, db_to_amp)

                # SigTo ──┐
                #         ├─(×)──┐
                # env1 ───┘      ├─(×)──> out signal
                # env2 ──────────┘
                self._gain_ctrl *= env
                envelopes.append(env)

            elif clip.auto_type in (
                ClipAutomationType.FadeIn,
                ClipAutomationType.FadeOut,
            ):
                # Fades are already normalized to 0..1, no conversion needed
                env = make_envelope(clip.graph_points, CurveScaling.None_, None)
                self._gain_ctrl *= env
                envelopes.append(env)

            elif clip.auto_type == ClipAutomationType.LPF:
                # clip y-axis is percent (0-100), which interpolates linearly;
                # the log-frequency behavior lives inside the percent->hz table
                env = make_envelope(clip.graph_points, CurveScaling.None_, hpf_to_hz)
                self._hpf_ctrl *= env
                envelopes.append(env)

            elif clip.auto_type == ClipAutomationType.HPF:
                env = make_envelope(clip.graph_points, CurveScaling.None_, lpf_to_hz)
                self._lpf_ctrl *= env
                envelopes.append(env)

            # NOTE: ClipAutomation and attenuation do not support pitch!

        # transpo is in semitones; winsize balances latency vs. smearing
        # better, but more costly: PVAnal -> PVTranspoe -> PVSynth
        pitch = pyo.Harmonizer(source, transpo=self._pitch_ctrl, winsize=0.1)

        # fixed order for all voices: source -> pitch -> HPF -> LPF -> gain
        hp = pyo.ButHP(pitch, freq=self._hpf_ctrl)
        lp = pyo.ButLP(hp, freq=self._lpf_ctrl)

        self._chain: list[pyo.PyoObject] = [
            source,
            envelopes,
            pitch,
            hp,
            lp,
            self._gain_ctrl,
        ]

    def source(self) -> pyo.PyoObject:
        return self._chain[0]

    def tail(self) -> pyo.PyoObject:
        return self._chain[-1]

    def play(self, dur: float = 0, delay: float = 0) -> pyo.PyoObject:
        for obj in self._chain:
            obj.play()

        return pyo.PyoObject.play(self, dur, delay)

    def stop(self, wait: float = 0) -> pyo.PyoObject:
        for obj in self._chain:
            obj.stop()

        return pyo.PyoObject.stop(self, wait)

    def out(
        self, chnl: int = 0, inc: int = 1, dur: float = 0, delay: float = 0
    ) -> pyo.PyoObject:
        self.play()
        return pyo.PyoObject.out(self, chnl, inc, dur, delay)

    @property
    def volume(self) -> float:
        return self._gain_ctrl.value

    @volume.setter
    def volume(self, gain: float) -> None:
        self._gain_ctrl.value = gain

    @property
    def hpf(self) -> float:
        return self._hpf_ctrl.value

    @hpf.setter
    def hpf(self, cents: float) -> None:
        self._hpf_ctrl.value = cents

    @property
    def lpf(self) -> float:
        return self._lpf_ctrl.value

    @lpf.setter
    def lpf(self, cents: float) -> None:
        self._lpf_ctrl.value = cents

    @property
    def pitch(self) -> float:
        return self._pitch_ctrl.value

    @pitch.setter
    def pitch(self, semitones: float) -> None:
        self._pitch_ctrl.value = semitones

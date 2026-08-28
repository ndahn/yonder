from typing import Callable
from pathlib import Path
import pyo
from pyo import sndinfo

from yonder.util import logger
from yonder.types import Attenuation
from yonder.types.base_types import ClipAutomation, ConversionTable, ConeParams
from yonder.enums import ClipAutomationType, CurveScaling, AttenuationProperty
from yonder.audio.audiomath import (
    hpf_to_hz,
    lpf_to_hz,
    db_to_amp,
    amp_to_db,
    make_envelope,
    eval_curve,
)


class StreamSource(pyo.PyoObject):
    def __init__(
        self,
        path: Path | str,
        loop: bool = False,
        volume_db: float = 0,
        hpf_cents: float = 0,
        lpf_cents: float = 0,
        pitch_semitones: float = 0,
        distance: float = 0.0,
        angle: float = 0.0,
        attenuation: Attenuation = None,
        clip_automations: list[ClipAutomation] = None,
        loop_start: float = 0.0,
        loop_end: float = 0.0,
        begin_trim: float = 0.0,
        end_trim: float = 0.0,
        xfade: float = 0.05,
        mul: float = 1,
        add: float = 0,
    ):
        pyo.PyoObject.__init__(self, mul, add)

        begin_trim = abs(begin_trim)
        end_trim = abs(end_trim)

        self._path = Path(path)
        self._raw_duration = sndinfo(str(path))[1]
        self._begin_trim = begin_trim
        self._end_trim = end_trim

        if loop_end == 0.0:
            loop_end = self.duration

        self._loop_start = loop_start
        self._loop_end = loop_end
        self._xfade = xfade
        self._paused_pos = 0.0
        self.loop = loop
        self.speed = pyo.SigTo(1.0, 0.05)

        # Two players that crossfade between each other when looping to allow
        # looping at arbitrary samples (SfPlayer only support looping at end)
        self._envs = [pyo.SigTo(0, xfade), pyo.SigTo(0, xfade)]
        self._players = [
            pyo.SfPlayer(
                str(self._path), speed=self.speed, loop=False, mul=self._envs[i]
            )
            for i in range(2)
        ]
        self._active = 0

        # Clock gives the position of playback in 0..1, threshold switches to 1
        # shortly before the stream ends and triggers the player swap
        self._clock = pyo.Phasor()
        self._pre_wrap = pyo.Thresh(self._clock)
        self._swapper = pyo.TrigFunc(self._pre_wrap, self._swap)
        self._trig = pyo.Trig()

        self.set_trims(begin_trim, end_trim)
        self.set_loop_points(loop_start, loop_end)

        # Our crossfaded sum becomes this object's audio stream
        # Always stereo, something like 7.1 would add a huge cpu cost otherwise
        self._mix = (self._players[0] + self._players[1]).mix(2)
        self._gain_ctrl = pyo.SigTo(db_to_amp(volume_db), time=0.05)
        self._hpf_ctrl = pyo.SigTo(hpf_to_hz(hpf_cents), time=0.05)
        self._lpf_ctrl = pyo.SigTo(lpf_to_hz(lpf_cents), time=0.05)
        self._pitch_ctrl = pyo.SigTo(pitch_semitones, time=0.05)

        self._distance = distance
        self._angle = angle
        self._dist_ctrl_volume = pyo.SigTo(db_to_amp(0), time=0.05)
        self._dist_ctrl_lpf = pyo.SigTo(lpf_to_hz(0), time=0.05)
        self._dist_ctrl_hpf = pyo.SigTo(hpf_to_hz(0), time=0.05)
        self._angle_ctrl_volume = pyo.SigTo(db_to_amp(0), time=0.05)
        self._angle_ctrl_lpf = pyo.SigTo(lpf_to_hz(0), time=0.05)
        self._angle_ctrl_hpf = pyo.SigTo(hpf_to_hz(0), time=0.05)
        self._att_volume_curve: ConversionTable = None
        self._att_lpf_curve: ConversionTable = None
        self._att_hpf_curve: ConversionTable = None
        self._cone_params: ConeParams = None

        # Apply attenuation data
        if attenuation:
            self._att_volume_curve = attenuation.get_curve(AttenuationProperty.Volume)
            self._att_lpf_curve = attenuation.get_curve(AttenuationProperty.LPF)
            self._att_hpf_curve = attenuation.get_curve(AttenuationProperty.HPF)

            if attenuation.is_cone_enabled:
                self._cone_params = attenuation.cone_params

        self._chain = self._setup_property_controls(self._mix, clip_automations)
        self._base_objs = sum(o.getBaseObjects() for o in self._chain)

        self._update_attenuation()

    def _setup_property_controls(
        self,
        source: pyo.PyoObject,
        clip_automations: list[ClipAutomation],
    ) -> list[pyo.PyoObject]:
        envelopes = []

        if not clip_automations:
            clip_automations = []

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

        signal_in = self._dist_ctrl_volume * self._angle_ctrl_volume * source

        # fixed order for all voices: source -> pitch -> HPF -> LPF -> gain
        # transpo is in semitones; winsize balances latency vs. smearing
        # better, but more costly: PVAnal -> PVTranspoe -> PVSynth
        pitch = pyo.Harmonizer(signal_in, transpo=self._pitch_ctrl, winsize=0.1)

        # distance attenuation
        hp_base = pyo.ButHP(pitch, freq=self._hpf_ctrl)
        hp_dist = pyo.ButHP(hp_base, freq=self._dist_ctrl_hpf)
        hp_angle = pyo.ButHP(hp_dist, freq=self._angle_ctrl_hpf)

        # cone params
        lp_base = pyo.ButLP(hp_angle, freq=self._lpf_ctrl)
        lp_dist = pyo.ButLP(lp_base, freq=self._dist_ctrl_lpf)
        lp_angle = pyo.ButLP(lp_dist, freq=self._angle_ctrl_lpf)

        return [
            source,
            envelopes,
            pitch,
            hp_base,
            hp_dist,
            hp_angle,
            lp_base,
            lp_dist,
            lp_angle,
            self._gain_ctrl,
        ]

    @property
    def distance(self) -> float:
        return self._distance

    @distance.setter
    def distance(self, dist: float) -> None:
        self._distance = dist
        self._update_attenuation()

    @property
    def angle(self) -> float:
        return self._angle

    @angle.setter
    def angle(self, phi: float) -> None:
        self._angle = phi
        self._update_attenuation()

    def _update_attenuation(self) -> None:
        def apply(
            curve: ConversionTable, ctrl: pyo.SigTo, conv: Callable[[float], float]
        ) -> None:
            if curve:
                y = eval_curve(curve.points, self._distance, curve.curve_scaling)
                ctrl.value = conv(y)

        apply(self._att_volume_curve, self._dist_ctrl_volume, db_to_amp)
        apply(self._att_hpf_curve, self._dist_ctrl_hpf, hpf_to_hz)
        apply(self._att_lpf_curve, self._dist_ctrl_lpf, lpf_to_hz)

        if self._cone_params:
            cone = self._cone_params
            # TODO match to cone positioning angle
            # For 0 to 360: min(self._angle % 360, 360 - self._angle % 360)
            angle = abs((self._angle + 180) % 360 - 180)
            inner_half = cone.inside_degrees / 2
            outer_half = cone.outside_degrees / 2

            if angle <= inner_half:
                # Within the inner cone, no additional attenuation
                pass
            elif outer_half > inner_half:
                if angle <= outer_half:
                    # Transition zone
                    f = (angle - inner_half) / (outer_half - inner_half)
                else:
                    # Outside outer cone, maximum attenuation
                    f = 1.0

                self._angle_ctrl_volume.value = db_to_amp(f * cone.outside_volume)
                self._angle_ctrl_hpf.value = hpf_to_hz(f * cone.high_pass)
                self._angle_ctrl_lpf.value = lpf_to_hz(f * cone.low_pass)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def progress(self) -> float:
        return self._clock.get()

    @property
    def volume(self) -> float:
        return amp_to_db(self._gain_ctrl.value)

    @volume.setter
    def volume(self, vol_db: float) -> None:
        self._gain_ctrl.value = amp_to_db(vol_db)

    @property
    def gain(self) -> float:
        return self._gain_ctrl.value

    @gain.setter
    def gain(self, gain: float) -> None:
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

    @property
    def begin_trim(self) -> float:
        return self._begin_trim

    @property
    def end_trim(self) -> float:
        return self._end_trim

    def set_trims(
        self,
        from_start: float,
        from_end: float,
        keep_loop_marks_stationary: bool = False,
    ) -> None:
        from_start = abs(from_start)
        from_end = abs(from_end)

        # This won't work for prefetch streaming items since we're using the file duration
        # TODO resolve to the proper sound file, and ignore end_trim
        if from_start >= self.raw_duration - from_end:
            logger.warning(
                "Trims would result in play duration <= 0, ignoring end_trim for playback"
            )
            from_end = 0.0

        if keep_loop_marks_stationary:
            # negative if trim reduced, positive if increased
            begin_diff = self._begin_trim - from_start
            self._loop_start = max(0.0, self._loop_start - begin_diff)

            # positive if trim reduced, negative if increased
            end_diff = self._end_trim - from_end
            self._loop_end = min(self._raw_duration, self._loop_end - end_diff)

        # In wwise, trims are set from the beginning/end of the track
        self._begin_trim = from_start
        self._end_trim = from_end
        self._update()

    @property
    def loop_start(self) -> float:
        # In wwise loop_start is relative to begin_trim
        return self._loop_start

    @property
    def loop_end(self) -> float:
        return self._loop_end

    def set_loop_points(self, start: float, end: float) -> None:
        if start < 0.0 or end < 0.0:
            raise ValueError("loop points must be >= 0")

        if end <= start:
            raise ValueError("start must be < end")

        self._loop_start = start
        self._loop_end = end
        self._update()

    @property
    def duration(self) -> float:
        return self._raw_duration - self._begin_trim - self._end_trim

    @property
    def raw_duration(self) -> float:
        return self._raw_duration

    @property
    def play_duration(self) -> float:
        if not self.loop:
            return self.duration

        return self.play_end - self.play_begin

    @property
    def play_begin(self) -> float:
        return self.loop_start

    @property
    def play_end(self) -> float:
        return min(self.loop_end, self.duration)

    @property
    def xfade(self) -> float:
        return self._xfade

    @xfade.setter
    def xfade(self, val: float) -> float:
        self._xfade = val
        self._update()

    def _update(self) -> None:
        dur = self.play_duration
        self._clock.freq = self.speed / dur
        self._pre_wrap.threshold = 1.0 - self._xfade / dur

    def _swap(self) -> None:
        if not self.loop:
            self.stop()
            self._trig.play()
            return

        # Start the second player which will take over
        nxt = 1 - self._active
        playback_start = self._begin_trim + self._loop_start
        self._players[nxt].setOffset(playback_start)
        self._players[nxt].play()

        # Let the envelopes handle the crossfade
        self._envs[nxt].value = 1
        self._envs[self._active].value = 0
        self._active = nxt

    @property
    def pos(self) -> float:
        return self._clock.get() * self.duration

    def seek(self, pos: float) -> None:
        dur = self.duration
        clamped = max(0.0, min(pos, dur - 1e-6))
        self._paused_pos = clamped

        if not self.isPlaying():
            # Only store position for next playback
            return

        t = self._begin_trim + clamped
        player = self._players[self._active]
        player.setOffset(t)
        # Apply offset
        player.play()

        # Phase is only what to add, not the internal value
        self._clock.reset()
        self._clock.phase = clamped / dur

    def play(self, dur: int = 0, delay: int = 0) -> None:
        self._players[0].setOffset(self._begin_trim)
        self._players[0].play()
        self._players[1].stop()
        self._envs[0].value = 1
        self._envs[1].value = 0
        self._active = 0

        dur = self.duration
        self._clock.reset()
        self._clock.phase = self._paused_pos / dur if dur else 0.0
        self._clock.play()

        for o in self._chain:
            o.play(dur, delay)

        return pyo.PyoObject.play(self, dur, delay)

    def stop(self, wait: int = 0) -> None:
        self._paused_pos = self.pos

        for i in range(2):
            self._players[i].stop()
            self._envs[i].value = 0

        self._clock.stop()
        for o in self._chain:
            o.stop(wait)

        return pyo.PyoObject.stop(self, wait)

    def out(
        self, chnl: int = 0, inc: int = 1, dur: int = 0, delay: int = 0
    ) -> pyo.PyoObject:
        self.play()
        return pyo.PyoObject.out(self, chnl, inc, dur, delay)

    def __getitem__(self, key: str):
        if key == "trig":
            return self._trig

        return pyo.PyoObject.__getitem__(self, key)

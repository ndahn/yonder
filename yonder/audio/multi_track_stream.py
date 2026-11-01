from typing import Callable
from pathlib import Path
import math
import pyo
from pyo import sndinfo

from yonder.types.base_types import (
    ClipAutomation,
    TrackSrcInfo,
)
from yonder.enums import ClipAutomationType, CurveScaling
from yonder.util import logger
from .audiomath import (
    hpf_to_hz,
    hz_to_hpf,
    lpf_to_hz,
    hz_to_lpf,
    db_to_amp,
    amp_to_db,
    cents_to_speed,
    speed_to_cents,
    make_envelope,
)


class MultiTrackStream(pyo.PyoObject):
    @classmethod
    def from_source_ids(
        cls,
        sources: int | list[int],
        resolve_source: Callable[[int], Path],
        *,
        loop_count: int = -1,
        volume_db: float = 0,
        hpf_cents: float = 0,
        lpf_cents: float = 0,
        pitch_cents: float = 0,
        clip_automations: list[ClipAutomation] = None,
        begin_trim: float = 0.0,
        end_trim: float = 0.0,
        loop_start: float = 0.0,
        loop_end: float = 0.0,
        xfade: float = 0.05,
        mul: float = 1,
        add: float = 0,
    ) -> "MultiTrackStream":
        """build a playlist from plain files, for sounds with no track/playlist data"""
        if isinstance(sources, (int)):
            sources = [sources]

        playlist = []
        cursor = 0.0
        last = len(sources) - 1

        for i, sid in enumerate(sources):
            path = resolve_source(sid)
            if not path:
                logger.warning(f"Failed to resolve wem for source {sid}")
                continue

            raw_dur = sndinfo(str(path))[1]
            b_trim = begin_trim if i == 0 else 0.0
            e_trim = end_trim if i == last else 0.0

            playlist.append(
                TrackSrcInfo(
                    source_id=sid,
                    play_at=cursor,
                    begin_trim_offset=b_trim,
                    end_trim_offset=e_trim,
                    source_duration=raw_dur,
                )
            )
            cursor += raw_dur - b_trim - e_trim

        if not playlist:
            playlist.append(TrackSrcInfo())

        return cls(
            playlist,
            resolve_source,
            loop_count=loop_count,
            volume_db=volume_db,
            hpf_cents=hpf_cents,
            lpf_cents=lpf_cents,
            pitch_cents=pitch_cents,
            clip_automations=clip_automations,
            loop_start=loop_start,
            loop_end=loop_end,
            xfade=xfade,
            mul=mul,
            add=add,
        )

    """
    Plays a track built from one or more clips laid out on a timeline. Two players alternate and crossfade at clip boundaries and loop points.

    Everything that changes the playing material is a handover to the idle
    player (see `_cue`): starting or seeking, the next clip taking over, and
    jumping from the loop end back to the loop start. Only the next handover
    is ever armed, see `_arm`. Its trigger fires `_LEAD` seconds early to give
    pyo's callback time to cue the idle player; the handover itself is timed
    sample-accurately by envelopes and delays. The intro before the loop start
    plays once, the loop region repeats.
    """

    # How far ahead of a handover its trigger fires, in timeline seconds. Has
    # to cover a couple of audio buffers
    _LEAD = 0.05

    # Shortest ramp an envelope makes, so hard switches don't click
    _DECLICK = 0.002

    def __init__(
        self,
        playlist: list[TrackSrcInfo],
        resolve_source: Callable[[int], Path],
        *,
        loop_count: int = -1,
        volume_db: float = 0,
        hpf_cents: float = 0,
        lpf_cents: float = 0,
        pitch_cents: float = 0,
        clip_automations: list[ClipAutomation] = None,
        loop_start: float = 0.0,
        loop_end: float = 0.0,
        xfade: float = 0.05,
        mul: float = 1,
        add: float = 0,
    ):
        pyo.PyoObject.__init__(self, mul, add)

        if not playlist:
            raise ValueError("playlist must contain at least one clip")

        self._playlist = sorted(playlist, key=lambda c: c.play_at)
        self._resolve_source = resolve_source
        self._track_duration = max(self._clip_end(c) for c in self._playlist)

        self._loop_start = 0.0
        self._loop_end = self._track_duration
        self._xfade = 0.0
        self._paused_pos = 0.0
        self._loops_played = 0
        self.loop_count = loop_count

        # The handover the clock's trigger is armed for, see _arm
        self._pending: tuple = None

        # wwise implements pitch as a playback speed change (resampling).
        # Our clock is driven from this signal and follows automatically
        speed = cents_to_speed(pitch_cents)
        self._speed_ctrl = pyo.SigTo(speed, 0.05, init=speed)

        # two players alternate clips and crossfade at the boundary
        # needed for looping at arbitrary points. Linseg envelopes rather than
        # SigTo, since a handover needs a ramp that starts at a precise moment.
        # pyo only delays play() by whole audio buffers, the short delay line
        # behind each player makes up the remainder, see _cue
        first_path = str(resolve_source(self._playlist[0].source_id))
        self._envs = [pyo.Linseg([(0, 0), (1, 0)]) for _ in range(2)]
        self._players = [
            pyo.SfPlayer(first_path, speed=self._speed_ctrl, loop=False)
            for _ in range(2)
        ]
        self._voices = [
            pyo.SDelay(self._players[i], delay=0, maxdelay=0.2, mul=self._envs[i])
            for i in range(2)
        ]
        self._active_player = 0
        self._clip_index = 0

        # Position on the track's timeline in seconds: the time since the last
        # jump plus where that jump went to. Its span only has to outlast the
        # longest stretch without a jump, i.e. the whole track
        span = self._track_duration + 1.0
        self._origin = pyo.Sig(0.0)
        self._clock = pyo.Phasor(
            freq=self._speed_ctrl / span, mul=span, add=self._origin
        )
        self._event_thresh = pyo.Thresh(self._clock, threshold=span)
        self._event_func = pyo.TrigFunc(self._event_thresh, self._on_event)
        self._trig = pyo.Trig().stop()  # discard auto-play trigger
        self._clock.stop()

        self.set_loop_points(loop_start, loop_end)
        self.xfade = xfade

        # always stereo, something like 7.1 would add a huge cpu cost otherwise
        self._mix = (self._voices[0] + self._voices[1]).mix(2)

        # Main controls, usually for properties
        self._master_gain_ctrl = pyo.SigTo(1.0, time=0.05)
        self._gain_ctrl = pyo.SigTo(db_to_amp(volume_db), time=0.05)
        self._hpf_ctrl = pyo.SigTo(hpf_to_hz(hpf_cents), time=0.05)
        self._lpf_ctrl = pyo.SigTo(lpf_to_hz(lpf_cents), time=0.05)

        self._chain = self._setup_property_controls(self._mix, clip_automations)
        # Only the fully processed signal is our output. Consumers like Mixer and
        # InputFader read the first stream of this object, i.e. the raw signal
        self._base_objs = self._chain[-1].getBaseObjects()

    def _setup_property_controls(
        self,
        source: pyo.PyoObject,
        clip_automations: list[ClipAutomation],
    ) -> list[pyo.PyoObject]:
        envelopes = []
        gain_signal = self._gain_ctrl
        hpf_signal = self._hpf_ctrl
        lpf_signal = self._lpf_ctrl

        if not clip_automations:
            clip_automations = []

        for clip in clip_automations:
            if clip.auto_type == ClipAutomationType.Volume:
                env = make_envelope(clip.graph_points, CurveScaling.DB, db_to_amp)

                # SigTo ──┐
                #         ├─(×)──┐
                # env1 ───┘      ├─(×)──> out signal
                # env2 ──────────┘
                gain_signal *= env
                envelopes.append(env)

            elif clip.auto_type in (
                ClipAutomationType.FadeIn,
                ClipAutomationType.FadeOut,
            ):
                # fades are already normalized to 0..1, no conversion needed
                env = make_envelope(clip.graph_points, CurveScaling.None_, None)
                gain_signal *= env
                envelopes.append(env)

            elif clip.auto_type == ClipAutomationType.HPF:
                # clip y-axis is percent (0-100), which interpolates linearly;
                # the log-frequency behavior lives inside the percent->hz table
                env = make_envelope(clip.graph_points, CurveScaling.None_, hpf_to_hz)
                hpf_signal *= env
                envelopes.append(env)

            elif clip.auto_type == ClipAutomationType.LPF:
                env = make_envelope(clip.graph_points, CurveScaling.None_, lpf_to_hz)
                lpf_signal *= env
                envelopes.append(env)

            # NOTE: ClipAutomation and attenuation do not support pitch

        # fixed order for all voices: source -> HPF -> LPF -> gain
        # (pitch is applied as playback speed at the source, like wwise does)
        hp = pyo.ButHP(source, freq=hpf_signal)
        lp = pyo.ButLP(hp, freq=lpf_signal)
        pre_master = lp * gain_signal
        final = pre_master * self._master_gain_ctrl

        return [
            source,
            *envelopes,
            hp,
            lp,
            pre_master,
            final,
        ]

    @property
    def volume(self) -> float:
        return amp_to_db(self._gain_ctrl.value)

    @volume.setter
    def volume(self, vol_db: float) -> None:
        self._gain_ctrl.value = db_to_amp(vol_db)

    @property
    def gain(self) -> float:
        return self._gain_ctrl.value

    @gain.setter
    def gain(self, gain: float) -> None:
        self._gain_ctrl.value = gain

    @property
    def master_gain(self) -> float:
        """UI-driven gain (voice sliders, mute), applied after the property-driven volume so the two don't clobber each other."""
        return self._master_gain_ctrl.value

    @master_gain.setter
    def master_gain(self, gain: float) -> None:
        self._master_gain_ctrl.value = gain

    @property
    def hpf(self) -> float:
        return hz_to_hpf(self._hpf_ctrl.value)

    @hpf.setter
    def hpf(self, cents: float) -> None:
        self._hpf_ctrl.value = hpf_to_hz(cents)

    @property
    def lpf(self) -> float:
        return hz_to_lpf(self._lpf_ctrl.value)

    @lpf.setter
    def lpf(self, cents: float) -> None:
        self._lpf_ctrl.value = lpf_to_hz(cents)

    @property
    def pitch(self) -> float:
        return speed_to_cents(self._speed_ctrl.value)

    @pitch.setter
    def pitch(self, cents: float) -> None:
        self._speed_ctrl.value = cents_to_speed(cents)

    @property
    def playlist(self) -> list[TrackSrcInfo]:
        return self._playlist

    @property
    def clip_index(self) -> int:
        return self._clip_index

    @property
    def current_clip(self) -> TrackSrcInfo:
        return self._playlist[self._clip_index]

    @property
    def current_path(self) -> Path:
        return self._resolve_source(self.current_clip.source_id)

    def _clip_duration(self, clip: TrackSrcInfo) -> float:
        return clip.source_duration - clip.begin_trim_offset - clip.end_trim_offset

    def _clip_end(self, clip: TrackSrcInfo) -> float:
        return clip.play_at + self._clip_duration(clip)

    def _clip_for_position(self, pos: float) -> tuple[int, float]:
        """find which clip covers an overall-timeline position, and the
        offset into its source file that corresponds to it"""
        for i, clip in enumerate(self._playlist):
            if pos < self._clip_end(clip):
                offset = clip.begin_trim_offset + max(0.0, pos - clip.play_at)
                return (i, offset)

        last = len(self._playlist) - 1
        clip = self._playlist[last]
        offset = clip.source_duration - clip.end_trim_offset
        return (last, offset)

    @property
    def duration(self) -> float:
        return self._track_duration

    @property
    def loop_start(self) -> float:
        return self._loop_start

    @property
    def loop_end(self) -> float:
        return self._loop_end

    def set_loop_points(self, start: float, end: float) -> None:
        if start < 0.0 or end < 0.0:
            raise ValueError("loop points must be >= 0")

        # 0 is how wwise says "the end of the track"
        if end == 0.0 or end > self._track_duration:
            end = self._track_duration

        self._loop_start = min(start, end)
        self._loop_end = end
        self._rearm()

    @property
    def xfade(self) -> float:
        return self._xfade

    @xfade.setter
    def xfade(self, val: float) -> None:
        self._xfade = max(val, 0.0)
        self._rearm()

    # === Position ======================================================

    @property
    def progress(self) -> float:
        return self.pos / max(self._track_duration, 1e-6)

    @property
    def pos(self) -> float:
        """Position on the track's timeline, in seconds."""
        if not self.isPlaying():
            # The clock reads 0 while stopped
            return self._paused_pos

        return self._clock.get()

    def seek(self, pos: float) -> None:
        pos = min(max(0.0, pos), max(0.0, self._track_duration - 1e-6))
        self._paused_pos = pos

        if self.isPlaying():
            self._start_at(pos)

    def play(self, dur: int = 0, delay: int = 0) -> None:
        self._loops_played = 0
        self._clock.play()
        self._start_at(self._paused_pos)

        for o in self._chain:
            o.play(dur, delay)

        return pyo.PyoObject.play(self, dur, delay)

    def stop(self, wait: int = 0) -> None:
        self._paused_pos = self.pos
        self._pending = None

        for i in range(2):
            self._players[i].stop()
            self._envs[i].stop()

        self._clock.stop()

        for o in self._chain:
            o.stop(wait)

        return pyo.PyoObject.stop(self, wait)

    def pos_trigger(self, pos: float) -> pyo.Thresh:
        """A trigger that fires whenever playback passes a timeline position."""
        return pyo.Thresh(self._clock, threshold=min(max(0.0, pos), self.duration))

    # === Scheduling ====================================================

    def _start_at(self, pos: float) -> None:
        idx, _ = self._clip_for_position(pos)
        self._cue(idx, pos, 0.0, 0.0)

    def _arm(self, pos: float) -> None:
        """Aim the clock's trigger at the first handover after `pos`."""
        clip_end = self._clip_end(self.current_clip)
        looping = self._loop_end > self._loop_start + self._DECLICK and (
            self.loop_count == 0 or self.loop_count > self._loops_played
        )

        if looping and pos < self._loop_end <= clip_end + 1e-6:
            at, target = self._loop_end, self._loop_start
            fade = min(self._xfade, (at - target) / 2)
            idx, _ = self._clip_for_position(target)
            lead = self._LEAD + fade
        elif self._clip_index + 1 < len(self._playlist):
            # Consecutive clips are spliced, their own fade automations take
            # care of any smoothing
            at = target = clip_end
            idx, fade, lead = self._clip_index + 1, 0.0, self._LEAD
        else:
            # The end needs no preparation. Firing right on time keeps the
            # tail from being cut
            at, idx, target, fade, lead = clip_end, None, None, 0.0, 0.0

        self._pending = (at, idx, target, fade)

        # Never arm behind the clock, it would never cross
        self._event_thresh.threshold = max(at - lead, pos + 1e-6)

    def _rearm(self) -> None:
        if self._pending is not None and self.isPlaying():
            self._arm(self.pos)

    def _on_event(self) -> None:
        """Called from pyo's callback thread when the armed handover is near."""
        if self._pending is None:
            return

        at, idx, target, fade = self._pending
        if idx is None:
            self.stop()
            self._trig.play()
            return

        if target != at:
            self._loops_played += 1

        # Measured rather than assumed, as the trigger only fires at the end of
        # an audio buffer and any lateness would otherwise add up
        self._cue(idx, target, max(0.0, at - self._clock.get()), fade)

    def _cue(self, idx: int, target: float, left: float, fade: float) -> None:
        """Hand playback over to the idle player.

        It is lined up to reach timeline position `target` in `left` seconds,
        when the active one would reach the handover point, and the two
        crossfade over the last `fade` seconds before that.
        """
        clip = self._playlist[idx]

        # Ideally the fade in is the material right before the target, which
        # keeps the loop length intact. Whatever the clip doesn't have there
        # (always the case for a loop starting at 0) comes from after the
        # target instead: the start of the loop then overlaps its end
        fade = max(0.0, min(fade, left))
        target += max(0.0, fade - max(0.0, target - clip.play_at))

        # Timeline seconds pass at the playback speed, envelopes and delays
        # run on wall clock time
        speed = max(self._speed_ctrl.value, 1e-6)

        # The incoming player starts right away and stays silent until its
        # fade in, unless its clip only begins later (a gap, or a loop start
        # too close to the clip's beginning). Then it waits rather than play
        # trimmed material
        start = max(target - left, clip.play_at)
        wait = (start - (target - left)) / speed

        # pyo rounds play delays to whole audio buffers, so the player waits
        # for those and its delay line for the rest
        bufdur = self.getBufferSize() / self.getSamplingRate()
        whole = math.floor(wait / bufdur + 1e-9) * bufdur

        old, new = self._active_player, 1 - self._active_player
        self._ramp(old, 1.0, 0.0, (left - fade) / speed, left / speed)
        self._ramp(new, 0.0, 1.0, max((left - fade) / speed, wait), left / speed)

        player = self._players[new]
        player.setSound(str(self._resolve_source(clip.source_id)))
        player.setOffset(clip.begin_trim_offset + start - clip.play_at)
        player.play(delay=whole)
        self._voices[new].delay = wait - whole

        self._active_player = new
        self._clip_index = idx

        # The clock follows the incoming player from here on. Positions before
        # the target are fine, `add` can be negative
        self._clock.reset()
        self._origin.value = target - left
        self._arm(target - left)

    def _ramp(
        self, idx: int, start: float, end: float, t_from: float, t_to: float
    ) -> None:
        """Hold `start` until `t_from` seconds from now, then ramp to `end`."""
        points = [(0.0, start)]
        if t_from > 0:
            points.append((t_from, start))

        points.append((max(t_to, t_from + self._DECLICK), end))

        env = self._envs[idx]
        env.setList(points)
        env.play()

    def out(
        self, chnl: int = 0, inc: int = 1, dur: int = 0, delay: int = 0
    ) -> pyo.PyoObject:
        self.play()
        return pyo.PyoObject.out(self, chnl, inc, dur, delay)

    def __getitem__(self, key: str):
        if key == "trig":
            return self._trig

        return pyo.PyoObject.__getitem__(self, key)

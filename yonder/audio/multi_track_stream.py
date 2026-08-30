from typing import Callable
from pathlib import Path
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
    make_envelope,
)


class MultiTrackStream(pyo.PyoObject):
    @classmethod
    def from_source_ids(
        cls,
        sources: int | list[int],
        resolve_source: Callable[[int], Path],
        *,
        loop: bool = False,
        volume_db: float = 0,
        hpf_cents: float = 0,
        lpf_cents: float = 0,
        pitch_semitones: float = 0,
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
            loop=loop,
            volume_db=volume_db,
            hpf_cents=hpf_cents,
            lpf_cents=lpf_cents,
            pitch_semitones=pitch_semitones,
            clip_automations=clip_automations,
            loop_start=loop_start,
            loop_end=loop_end,
            xfade=xfade,
            mul=mul,
            add=add,
        )

    """
    Plays a track built from one or more clips laid out on a timeline. Two players alternate and crossfade at clip boundaries.

    Two clocks track time because a track's clips can have different
    lengths and gaps between them:
      - clip clock: progress through the *current* clip, fires the swap
        to the next clip shortly before it ends
      - overall clock: progress through the whole track/loop region,
        used for reporting position and unaffected by per-clip timing
    """

    def __init__(
        self,
        playlist: list[TrackSrcInfo],
        resolve_source: Callable[[int], Path],
        *,
        loop: bool = False,
        volume_db: float = 0,
        hpf_cents: float = 0,
        lpf_cents: float = 0,
        pitch_semitones: float = 0,
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

        if loop_end == 0.0:
            loop_end = self._track_duration

        self._loop_start = loop_start
        self._loop_end = loop_end
        self._xfade = xfade
        self._paused_pos = 0.0
        self.loop = loop
        self.speed = pyo.SigTo(1.0, 0.05)

        # two players alternate clips and crossfade at the boundary
        # needed for looping at arbitrary points
        first_path = str(resolve_source(self._playlist[0].source_id))
        self._envs = [pyo.SigTo(0, xfade), pyo.SigTo(0, xfade)]
        self._players = [
            pyo.SfPlayer(first_path, speed=self.speed, loop=False, mul=self._envs[i])
            for i in range(2)
        ]
        self._active_player = 0
        self._clip_index = 0

        # clip clock: fires just before the current clip ends
        self._clip_clock = pyo.Phasor()
        self._pre_wrap = pyo.Thresh(self._clip_clock)
        self._swapper = pyo.TrigFunc(self._pre_wrap, self._advance)
        self._trig = pyo.Trig()

        # overall clock: constant-rate progress across the whole track
        self._overall_clock = pyo.Phasor()

        self._update_clip_clock()
        self._update_overall_clock()

        # always stereo, something like 7.1 would add a huge cpu cost otherwise
        self._mix = (self._players[0] + self._players[1]).mix(2)

        # Main controls, usually for properties
        self._gain_ctrl = pyo.SigTo(db_to_amp(volume_db), time=0.05)
        self._pitch_ctrl = pyo.SigTo(pitch_semitones, time=0.05)
        self._hpf_ctrl = pyo.SigTo(hpf_to_hz(hpf_cents), time=0.05)
        self._lpf_ctrl = pyo.SigTo(lpf_to_hz(lpf_cents), time=0.05)

        self._chain = self._setup_property_controls(self._mix, clip_automations)
        self._base_objs = sum(o.getBaseObjects() for o in self._chain)

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

        # fixed order for all voices: source -> pitch -> HPF -> LPF -> gain
        # transpo is in semitones; winsize balances latency vs. smearing
        # better, but more costly: PVAnal -> PVTranspoe -> PVSynth
        pitch = pyo.Harmonizer(source, transpo=self._pitch_ctrl, winsize=0.1)
        hp = pyo.ButHP(pitch, freq=hpf_signal)
        lp = pyo.ButLP(hp, freq=lpf_signal)
        final = lp * gain_signal

        return [
            source,
            *envelopes,
            pitch,
            hp,
            lp,
            final,
        ]

    def _recombine_hpf(self) -> None:
        # HPF cutoff rises with restrictiveness
        self._hpf_ctrl.value = max(
            self._hpf_base, self._hpf_rtpc, self._hpf_dist, self._hpf_angle
        )

    def _recombine_lpf(self) -> None:
        # LPF cutoff falls with restrictiveness
        self._lpf_ctrl.value = min(
            self._lpf_base, self._lpf_rtpc, self._lpf_dist, self._lpf_angle
        )

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
        return self._pitch_ctrl.value

    @pitch.setter
    def pitch(self, semitones: float) -> None:
        self._pitch_ctrl.value = semitones

    @property
    def rtpc_gain(self) -> float:
        return self._rtpc_gain_ctrl.value

    @rtpc_gain.setter
    def rtpc_gain(self, gain: float) -> None:
        self._rtpc_gain_ctrl.value = gain

    @property
    def rtpc_hpf(self) -> float:
        return self._hpf_rtpc

    @rtpc_hpf.setter
    def rtpc_hpf(self, cents: float) -> None:
        self._hpf_rtpc = hpf_to_hz(cents)
        self._recombine_hpf()

    @property
    def rtpc_lpf(self) -> float:
        return self._lpf_rtpc

    @rtpc_lpf.setter
    def rtpc_lpf(self, cents: float) -> None:
        self._lpf_rtpc = lpf_to_hz(cents)
        self._recombine_lpf()

    @property
    def rtpc_pitch(self) -> float:
        return self._rtpc_pitch_ctrl.value

    @rtpc_pitch.setter
    def rtpc_pitch(self, semitones: float) -> None:
        self._rtpc_pitch_ctrl.value = semitones

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

    def _update_clip_clock(self) -> None:
        dur = max(self._clip_duration(self.current_clip), 1e-6)
        self._clip_clock.freq = self.speed / dur
        self._pre_wrap.threshold = 1.0 - self._xfade / dur

    def _update_overall_clock(self) -> None:
        span = max(self._loop_end - self._loop_start, 1e-6)
        self._overall_clock.freq = self.speed / span

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
        if start < 0.0:
            raise ValueError("loop points must be >= 0")

        if end <= start:
            raise ValueError("start must be < end")

        self._loop_start = start
        self._loop_end = end
        self._update_overall_clock()

    @property
    def play_duration(self) -> float:
        if not self.loop:
            return self.duration

        return self.play_end - self.play_begin

    @property
    def play_begin(self) -> float:
        return self._loop_start

    @property
    def play_end(self) -> float:
        return min(self._loop_end, self.duration)

    @property
    def xfade(self) -> float:
        return self._xfade

    @xfade.setter
    def xfade(self, val: float) -> None:
        self._xfade = val
        self._update_clip_clock()

    def _advance(self) -> None:
        """move on to the next clip, or loop back, or stop at the end"""
        current_item = self._playlist[self._clip_index]
        next_idx = self._clip_index + 1

        if next_idx < len(self._playlist):
            next_item = self._playlist[next_idx]
            offset = next_item.begin_trim_offset
            # silence for any gap left between clips, no crossfade needed
            delay = max(0.0, next_item.play_at - self._clip_end(current_item))
        elif self.loop:
            next_idx, offset = self._clip_for_position(self._loop_start)
            delay = 0.0
        else:
            # end of playlist
            self.stop()
            self._trig.play()
            return

        player = 1 - self._active_player
        path = self._resolve_source(self._playlist[next_idx].source_id)
        self._players[player].setSound(str(path))
        self._players[player].setOffset(offset)
        self._players[player].play(delay=delay * 1000)

        self._envs[player].value = 1
        self._envs[self._active_player].value = 0
        self._active_player = player
        self._clip_index = next_idx
        self._update_clip_clock()

    @property
    def progress(self) -> float:
        return self._overall_clock.get()

    @property
    def clip_progress(self) -> float:
        return self._clip_clock.get()

    @property
    def pos(self) -> float:
        return self._loop_start + self.progress * (self._loop_end - self._loop_start)

    def seek(self, pos: float) -> None:
        span = self._loop_end - self._loop_start
        clamped = max(self._loop_start, min(pos, self._loop_start + span - 1e-6))
        self._paused_pos = clamped

        if not self.isPlaying():
            # only store position for next playback
            return

        idx, offset = self._clip_for_position(clamped)
        clip = self._playlist[idx]

        if idx != self._clip_index:
            path = self._resolve_source(clip.source_id)
            self._players[self._active_player].setSound(str(path))
            self._clip_index = idx
            self._update_clip_clock()

        player = self._players[self._active_player]
        player.setOffset(offset)
        player.play()

        clip_dur = max(self._clip_duration(clip), 1e-6)
        self._clip_clock.reset()
        self._clip_clock.phase = (offset - clip.begin_trim_offset) / clip_dur

        self._overall_clock.reset()
        self._overall_clock.phase = (clamped - self._loop_start) / span

    def play(self, dur: int = 0, delay: int = 0) -> None:
        idx, offset = self._clip_for_position(self._paused_pos)
        clip = self._playlist[idx]
        path = str(self._resolve_source(clip.source_id))

        self._players[0].setSound(path)
        self._players[0].setOffset(offset)
        self._players[0].play()
        self._players[1].stop()
        self._envs[0].value = 1
        self._envs[1].value = 0

        self._active_player = 0
        self._clip_index = idx
        self._update_clip_clock()
        self._update_overall_clock()

        clip_dur = max(self._clip_duration(clip), 1e-6)
        self._clip_clock.reset()
        self._clip_clock.phase = (offset - clip.begin_trim_offset) / clip_dur
        self._clip_clock.play()

        span = self._loop_end - self._loop_start
        self._overall_clock.reset()
        self._overall_clock.phase = (self._paused_pos - self._loop_start) / span
        self._overall_clock.play()

        for o in self._chain:
            o.play(dur, delay)

        return pyo.PyoObject.play(self, dur, delay)

    def stop(self, wait: int = 0) -> None:
        self._paused_pos = self.pos

        for i in range(2):
            self._players[i].stop()
            self._envs[i].value = 0

        self._clip_clock.stop()
        self._overall_clock.stop()

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

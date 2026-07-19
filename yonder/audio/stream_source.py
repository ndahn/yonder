from pathlib import Path
import pyo
from pyo import sndinfo


class StreamSource(pyo.PyoObject):
    def __init__(
        self,
        path: Path | str,
        loop: bool = False,
        loop_start: float = 0.0,
        loop_end: float = 0.0,
        begin_trim: float = 0.0,
        end_trim: float = 0.0,
        xfade: float = 0.05,
        mul: float = 1,
        add: float = 0,
    ):
        pyo.PyoObject.__init__(self, mul, add)

        self._path = Path(path)
        self._duration = sndinfo(str(path))[1]

        if loop_end == 0.0:
            loop_end = self._duration - abs(end_trim) - abs(begin_trim)

        self._loop_start = loop_start
        self._loop_end = loop_end
        self._begin_trim = begin_trim
        self._end_trim = end_trim
        self._xfade = xfade
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

        self.set_trims(begin_trim, end_trim)
        self.set_loop_points(loop_start, loop_end)

        # Our crossfaded sum becomes this object's audio stream
        self._done = pyo.Trig()
        self._mix = self._players[0] + self._players[1]
        self._base_objs = self._mix.getBaseObjects()

    @property
    def path(self) -> Path:
        return self._path

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
        if from_start >= self.duration - from_end:
            raise ValueError("Trims would result in play duration <= 0")

        if keep_loop_marks_stationary:
            # negative if trim reduced, positive if increased
            begin_diff = self._begin_trim - abs(from_start)
            self._loop_start = max(0.0, self._loop_start - begin_diff)

            # positive if trim reduced, negative if increased
            end_diff = self._end_trim - abs(from_end)
            self._loop_end = min(self._duration, self._loop_end - end_diff)

        # In wwise, trims are set from the beginning/end of the track
        self._begin_trim = abs(from_start)
        self._end_trim = abs(from_end)
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
        return self._duration

    @property
    def play_duration(self) -> float:
        return self.playback_end - self.playback_start

    @property
    def playback_start(self) -> float:
        return self._begin_trim + self._loop_start

    @property
    def playback_end(self) -> float:
        return min(self._begin_trim + self._loop_end, self._duration - self._end_trim)

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
            self._done.play()
            return

        # Start the second player which will take over
        nxt = 1 - self._active
        self._players[nxt].setOffset(self.playback_start)
        self._players[nxt].play()

        # Let the envelopes handle the crossfade
        self._envs[nxt].value = 1
        self._envs[self._active].value = 0
        self._active = nxt

    def seek(self, pos: float) -> None:
        self._players[self._active].setOffset(pos)
        self._clock.phase = (pos - self.playback_start) / self.play_duration

    def play(self, dur: int = 0, delay: int = 0) -> None:
        self._players[0].setOffset(0)
        self._players[0].play()
        self._envs[0].value = 1
        self._active = 0

        return pyo.PyoObject.play(self, dur, delay)

    def stop(self, wait: int = 0) -> None:
        for i in range(2):
            self._players[i].stop()
            self._envs[i].value = 0

        return pyo.PyoObject.stop(self, wait)

    def out(
        self, chnl: int = 0, inc: int = 1, dur: int = 0, delay: int = 0
    ) -> pyo.PyoObject:
        self.play()
        return pyo.PyoObject.out(self, chnl, inc, dur, delay)

    def __getitem__(self, key: str):
        if key == "trig":
            return self._done

        return pyo.PyoObject.__getitem__(self, key)

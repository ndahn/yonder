from pathlib import Path
import pyo
from pyo import sndinfo


class StreamSource:
    def __init__(
        self,
        path: Path | str,
        loop: bool = False,
        loop_start: float = 0.0,
        loop_end: float = 0.0,
        # TODO trims, loop_start relative to begin_trim, end_trim always negative and from end
        xfade: float = 0.05,
    ):
        self._path = Path(path)
        self._loop_start = loop_start
        self._loop_end = loop_end
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

        self._update()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def loop_start(self) -> float:
        return self._loop_start

    @property
    def loop_end(self) -> float:
        return self._loop_end

    def set_loop_points(self, start: float, end: float) -> None:
        if start < 0.0 or end < 0.0:
            raise ValueError("loop points must be >= 0")

        if end == 0.0:
            end = sndinfo(str(self._path))[1]

        if end <= start:
            raise ValueError("start must be < end")

        self._loop_start = start
        self._loop_end = end
        self._update()

    @property
    def duration(self) -> float:
        return self._loop_end - self._loop_start

    @property
    def xfade(self) -> float:
        return self._xfade

    @xfade.setter
    def xfade(self, val: float) -> float:
        self._xfade = val
        self._update()

    def _update(self) -> None:
        dur = self.duration
        self._clock.freq = self.speed / dur
        self._pre_wrap.threshold = 1.0 - self._xfade / dur

    def _swap(self) -> None:
        if not self.loop:
            self.stop()
            return

        # Start the second player which will take over
        nxt = 1 - self._active
        self._players[nxt].setOffset(self.loop_start)
        self._players[nxt].play()

        # Let the envelopes handle the crossfade
        self._envs[nxt].value = 1
        self._envs[self._active].value = 0
        self._active = nxt

    def seek(self, pos: float) -> None:
        self._players[self._active].setOffset(pos)
        self._clock.phase = (pos - self.loop_start) / self.duration

    def start(self) -> None:
        self._players[0].setOffset(0)
        self._players[0].play()
        self._envs[0].value = 1
        self._active = 0

    def stop(self) -> None:
        for i in range(2):
            self._players[i].stop()
            self._envs[i].value = 0

    def out(self) -> pyo.PyoObject:
        return self._players[0] + self._players[1]

    def __getattr__(self, name: str):
        return getattr(self._players[self._active], name)

from __future__ import annotations
from typing import Callable
from dataclasses import dataclass, field
import atexit
import time
from pathlib import Path
import numpy as np
import pyo

from yonder.util import logger
from .audiomath import (
    db_to_amp,
    amp_to_db,
    hpf_to_hz,
    hz_to_hpf,
    lpf_to_hz,
    hz_to_lpf,
    cents_to_speed,
    speed_to_cents,
)


@dataclass
class _Source:
    """One loaded signal or file together with every pyo object it owns.

    ``nodes`` is the chain in creation order and gets played and stopped as a
    unit. ``tables`` holds the table objects, which have no transport of their
    own but still have to stay referenced for as long as a reader points at
    them. Releasing both is `SimplePlayer._retire`'s job.
    """

    duration: float = 0.0
    framerate: int = 0
    channels: int = 0
    clock: pyo.Phasor = None
    out: pyo.PyoObject = None
    nodes: list[pyo.PyoObject] = field(default_factory=list)
    tables: list = field(default_factory=list)
    sfplayer: pyo.SfPlayer = None
    path: Path = None
    signal: np.ndarray = None
    token: int = 0


class SimplePlayer:
    """Plays a single signal or audio file through one pyo server.

    Loading a source and driving it are two separate steps: `set_signal` and
    `set_file` build the pyo chain, `play`, `pause`, `stop` and `seek` only
    operate on an already built one. 
    Chains that do get replaced are stopped and released from pyo's own
    callback thread after a short grace period, which is the same approach
    `yonder.types.HIRCNode.release_pyo` takes.

    All times are in seconds.
    """

    def __init__(
        self,
        *,
        fade_time: float = 0.1,
        on_finished: Callable[[], None] = None,
        volume_db: float = 0,
        hpf_cents: float = 0,
        lpf_cents: float = 0,
        pitch_cents: float = 0,
    ):
        self._fade_time = fade_time
        self._on_finished: Callable[[], None] = on_finished
        self._source: _Source = None
        self._source_token = 0
        self._loop = False

        # Where playback is, whenever the clock itself cannot say, and the
        # server sample count from which it can again. See _clock_reports
        self._pos = 0.0
        self._clock_ready_at = 0

        # Sources waiting out their grace period before being dropped,
        # keyed by an ascending token, see _retire
        self._retired: dict[int, tuple[_Source, pyo.CallAfter]] = {}
        self._retire_token = 0

        self._server: pyo.Server = pyo.Server(duplex=0)
        self._server.deactivateMidi()
        self._server.boot()

        # What the fader reads while nothing is loaded. Has to stay referenced
        # for as long as the fader might fall back to it
        self._silence = pyo.Sig([0, 0])
        self._input = pyo.InputFader(self._silence)
        self._gain_ctrl = pyo.SigTo(db_to_amp(volume_db), time=fade_time)
        self._hpf_ctrl = pyo.SigTo(hpf_to_hz(hpf_cents), time=fade_time)
        self._lpf_ctrl = pyo.SigTo(lpf_to_hz(lpf_cents), time=fade_time)
        speed = cents_to_speed(pitch_cents)
        self._speed_ctrl = pyo.SigTo(speed, fade_time, init=speed)

        # Could add additional processing on top (e.g. a master volume if we allow
        # mixing in additional sources)
        self._master = self._input
        self._master.out()
        self._server.start()

        # Important for proper exit
        atexit.register(self.close)

    def __del__(self):
        try:
            self.close()
        except Exception as e:
            logger.error("Failed to close player", exc_info=e)

    def close(self) -> None:
        # close is called again by __del__ and atexit, avoid closing twice
        if getattr(self, "_closed", False):
            return

        self._closed = True

        if self._server.getIsStarted():
            self._server.stop()
            # Allow the server to drain all buffers and callbacks
            time.sleep(0.25)

        # Deleting the objects is safe now that processing has ended. Any
        # pending CallAfter would never fire with the server stopped, so the
        # grace period has to be skipped here
        source, self._source = self._source, None
        self._retire(source, 0)
        for retired, _ in list(self._retired.values()):
            self._stop_nodes(retired)

        self._retired.clear()

        if self._server.getIsBooted():
            self._server.shutdown()

        atexit.unregister(self.close)

    def set_finished_callback(self, callback: Callable[[], None]) -> None:
        self._on_finished = callback

    # === Source ========================================================

    @property
    def has_source(self) -> bool:
        return self._source is not None

    @property
    def signal(self) -> np.ndarray:
        """The samples passed to `set_signal`, or None."""
        return self._source.signal if self._source else None

    @property
    def path(self) -> Path:
        """The file passed to `set_file`, or None."""
        return self._source.path if self._source else None

    @property
    def duration(self) -> float:
        return self._source.duration if self._source else 0.0

    @property
    def framerate(self) -> int:
        return self._source.framerate if self._source else 0

    @property
    def channels(self) -> int:
        return self._source.channels if self._source else 0

    def set_signal(self, signal: np.ndarray, framerate: int) -> None:
        """Load samples as the current source, without starting playback."""
        channels = signal.shape[1] if len(signal.shape) > 1 else 1
        duration = len(signal) / framerate

        data = pyo.DataTable(size=len(signal), chnls=channels)
        data.replace(signal.T.tolist())

        clock = pyo.Phasor(freq=self._speed_ctrl / max(duration, 1e-9))
        reader = pyo.Pointer2(data, clock)
        thresh = pyo.Thresh(clock, threshold=0.99)

        self._set_source(
            _Source(
                duration=duration,
                framerate=framerate,
                channels=channels,
                clock=clock,
                nodes=[clock, thresh, reader],
                tables=[data],
                signal=signal,
            ),
            feed=reader,
            trigger=thresh,
        )

    def set_file(self, path: Path) -> None:
        """Load an audio file as the current source, without starting playback."""
        path = Path(path)
        info = pyo.sndinfo(str(path))
        if not info:
            raise ValueError(f"Cannot read audio file: {path}")

        duration, framerate, channels = info[1], info[2], info[3]

        # Always looping, stopped in the trigger callback if supposed to end
        sfplayer = pyo.SfPlayer(str(path), speed=self._speed_ctrl, loop=True)
        # SfPlayer has no position readout, so a clock running at the same rate
        # provides one. Both are reset together in _apply_pos so they can't
        # drift apart
        clock = pyo.Phasor(freq=self._speed_ctrl / max(duration, 1e-9))

        self._set_source(
            _Source(
                duration=duration,
                framerate=framerate,
                channels=channels,
                clock=clock,
                nodes=[sfplayer, clock],
                sfplayer=sfplayer,
                path=path,
            ),
            feed=sfplayer,
            trigger=sfplayer["trig"],
        )

    def clear(self) -> None:
        """Release the current source and fade the output out."""
        source, self._source = self._source, None
        self._pos = 0.0

        if source is None:
            return

        self._input.setInput(self._silence, self._fade_time)
        self._retire(source)

    # === Transport =====================================================

    @property
    def playing(self) -> bool:
        return bool(self._source and self._source.clock.isPlaying())

    @property
    def pos(self) -> float:
        """Current playback position, or the one the next play starts from."""
        source = self._source
        if not source:
            return 0.0

        if not self._clock_reports():
            return self._pos

        return source.clock.get() * source.duration

    @property
    def loop(self) -> bool:
        return self._loop

    @loop.setter
    def loop(self, enabled: bool) -> None:
        self._loop = enabled

    def play(self) -> None:
        """Start, or resume from the position the last pause left off at."""
        source = self._source
        if not source or self.playing:
            return

        for node in source.nodes:
            node.play()

        self._apply_pos(self._pos)

    def pause(self) -> None:
        """Stop playback, keeping the current position for the next play."""
        source = self._source
        if not source:
            return

        self._pos = self.pos
        self._stop_nodes(source)

    def stop(self) -> None:
        """Stop playback and rewind to the start."""
        self.pause()
        self._pos = 0.0

    def seek(self, pos: float, relative: bool = False) -> None:
        source = self._source
        if not source or source.duration <= 0:
            return

        if relative:
            pos *= source.duration

        # Seeking exactly to the end would wrap straight back around
        pos = min(max(0.0, pos), max(0.0, source.duration - 1e-6))

        if self.playing:
            self._apply_pos(pos)
        else:
            # Stored for the next play, there is no clock to move yet
            self._pos = pos

    # === Properties ====================================================

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
        return speed_to_cents(self._speed_ctrl.value)

    @pitch.setter
    def pitch(self, cents: float) -> None:
        self._speed_ctrl.value = cents_to_speed(cents)

    # === Internals =====================================================

    def _set_source(
        self,
        source: _Source,
        feed: pyo.PyoObject,
        trigger: pyo.PyoObject,
    ) -> None:
        """Finish a source's chain, make it current and retire the old one."""
        self._source_token += 1
        source.token = self._source_token

        # A retired source can still fire its end trigger one last time. The
        # token makes sure a stale one can't stop whatever plays by then
        callback = pyo.TrigFunc(trigger, self._on_source_end, source.token)

        hpf = pyo.ButHP(feed, self._hpf_ctrl)
        lpf = pyo.ButLP(hpf, self._lpf_ctrl)
        sig = lpf * self._gain_ctrl

        if source.channels == 1:
            out = pyo.Pan(sig, outs=2, pan=0.5, spread=0.5)
        else:
            out = sig.mix(2)

        source.nodes = [callback, *source.nodes, hpf, lpf, sig, out]
        source.out = out

        # pyo objects play as soon as they are created, nothing should be
        # audible before play() is called
        self._stop_nodes(source)

        previous, self._source = self._source, source
        self._pos = 0.0
        self._input.setInput(out, self._fade_time)
        self._retire(previous)

    def _clock_reports(self) -> bool:
        """Whether the clock's own value can be trusted as the position.

        It reads 0 while stopped, and after being moved it keeps handing out
        its previous value until the server has run another buffer through it.
        Both windows are covered by `_pos`.
        """
        source = self._source
        if not source or not source.clock.isPlaying():
            return False

        return self._server.getCurrentTimeInSamples() >= self._clock_ready_at

    def _apply_pos(self, pos: float) -> None:
        source = self._source
        if not source or source.duration <= 0:
            return

        if source.sfplayer is not None:
            # SfPlayer only picks up a new offset when it is (re)started
            source.sfplayer.setOffset(pos)
            source.sfplayer.play()

        # Resetting zeroes the clock's own ramp, so the phase offset alone
        # determines where it reads from
        source.clock.reset()
        source.clock.phase = (pos / source.duration) % 1.0

        self._pos = pos
        self._clock_ready_at = (
            self._server.getCurrentTimeInSamples() + self._server.getBufferSize()
        )

    def _on_source_end(self, token: int) -> None:
        """Called from pyo's callback thread when a source reaches its end."""
        if not self._source or token != self._source.token:
            # Belongs to a source that has already been replaced
            return

        if not self._loop:
            self.stop()

        if self._on_finished:
            self._on_finished()

    def _retire(self, source: _Source, delay: float = None) -> None:
        """Stop a source and release its pyo objects.

        Dropping the last reference to a pyo object while the server may still
        be processing it is what hard crashes the whole app, so a replaced
        chain is parked until the server has moved past it. `pyo.CallAfter`
        runs the release from the server's own callback thread, the one place
        where nothing can be touching the streams at the same time. A delay of
        0 releases immediately and is only safe while the server is stopped,
        since no callback would ever fire to do it later.
        """
        if source is None:
            return

        if delay is None:
            # Long enough for the crossfade onto the new source to finish
            delay = self._fade_time + 0.1

        if delay <= 0 or not self._server.getIsStarted():
            self._stop_nodes(source)
            return

        self._retire_token += 1
        token = self._retire_token
        self._retired[token] = (
            source,
            pyo.CallAfter(self._release, delay, token),
        )

    def _release(self, token: int) -> None:
        """Called from pyo's callback thread once a retired source's grace period is up. Dropping the entry here is what finally frees the objects."""
        entry = self._retired.pop(token, None)
        if entry:
            self._stop_nodes(entry[0])

    @staticmethod
    def _stop_nodes(source: _Source) -> None:
        # Back to front, so nothing keeps pulling from a node that already quit
        for node in reversed(source.nodes):
            node.stop()

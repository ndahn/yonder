from __future__ import annotations
from typing import Callable
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


class SimplePlayer:
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
        self._source_nodes: list[pyo.PyoObject] = []
        self._signal_source: pyo.PyoObject = None
        self._duration: float = 0.0
        self._framerate: int = 0
        self._channels: int = 0
        self._loop = False

        self._server: pyo.Server = pyo.Server(duplex=0)
        self._server.deactivateMidi()
        self._server.boot()

        # TODO use an InputFader instead
        self._mixer = pyo.Mixer(outs=1, chnls=2, time=fade_time)
        self._gain_ctrl = pyo.SigTo(db_to_amp(volume_db), time=fade_time)
        self._hpf_ctrl = pyo.SigTo(hpf_to_hz(hpf_cents), time=fade_time)
        self._lpf_ctrl = pyo.SigTo(lpf_to_hz(lpf_cents), time=fade_time)
        speed = cents_to_speed(pitch_cents)
        self._speed_ctrl = pyo.SigTo(speed, fade_time, init=speed)

        # Could add additional processing on top (e.g. a master volume if we allow
        # mixing in additional sources)
        self._master = self._mixer
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

        if self._server.getIsBooted():
            self._server.shutdown()

        atexit.unregister(self.close)

    def set_finished_callback(self, callback: Callable[[], None]) -> None:
        self._on_finished = callback

    @property
    def playing(self) -> bool:
        return self._signal_source and self._signal_source.isPlaying()

    @property
    def duration(self) -> float:
        return self._duration

    @property
    def framerate(self) -> int:
        return self._framerate

    @property
    def channels(self) -> int:
        return self._channels

    @property
    def pos(self) -> float:
        src = self._signal_source

        if isinstance(src, pyo.Phasor):
            return src.get()
        elif hasattr(src, "phase"):
            return src.phase

        return 0.0

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

    @property
    def loop(self) -> bool:
        return self._loop

    @loop.setter
    def loop(self, enabled: bool) -> None:
        self._loop = enabled

    def _set_source(
        self, source: pyo.PyoObject, chain: list[pyo.PyoObject] = None, trigger: pyo.PyoObject = None,
    ) -> None:
        if not chain:
            chain = [source]

        if trigger:
            cb = pyo.TrigFunc(trigger, self._on_playback_end)
            chain.insert(0, cb)

        hpf = pyo.ButHP(chain[-1], self._hpf_ctrl)
        lpf = pyo.ButLP(hpf, self._lpf_ctrl)
        out = (lpf * self._gain_ctrl).mix(2)
        chain.extend([hpf, lpf, out])

        self._mixer.addInput(0, out)
        self._mixer.setAmp(0, 0, 1.0)

        # Wait for the crossfade to finish before allowing the old sources
        # to be garbage collected
        time.sleep(self._fade_time + 0.05)
        self._source_nodes = chain
        self._signal_source = source

    def play_file(self, path: Path, loop: bool = False) -> None:
        # Always looping, will be stopped in the trigger callback if supposed to end
        player = pyo.SfPlayer(str(path), speed=self._speed_ctrl, loop=True)

        info = pyo.sndinfo(str(path))
        self._duration = info[1]
        self._framerate = info[2]
        self._channels = info[3]
        self._loop = loop

        self._set_source(player, trigger=player["trig"])

    def play_signal(
        self, signal: np.ndarray, framerate: int, loop: bool = False
    ) -> None:
        channels = signal.shape[1] if len(signal.shape) > 1 else 1
        duration = len(signal) / framerate

        data = pyo.DataTable(size=len(signal), chnls=channels)
        data.replace(signal.T.tolist())

        phasor = pyo.Phasor(freq=self._speed_ctrl / duration)
        reader = pyo.Pointer2(data, phasor)
        thresh = pyo.Thresh(phasor, threshold=0.99)

        self._duration = duration
        self._framerate = framerate
        self._channels = channels
        self._loop = loop

        self._set_source(phasor, [data, phasor, thresh, reader], thresh)

    def stop(self) -> None:
        self._signal_source.stop()

    def seek(self, pos: float, relative: bool = False) -> None:
        if not self._signal_source or self._duration == 0:
            return

        src = self._signal_source
        if hasattr(src, "setOffset"):
            if relative:
                pos *= self._duration
            src.setOffset(pos)
        elif isinstance(src, pyo.Phasor):
            if not relative:
                pos /= self._duration
            
            p = src.get() - src.phase
            src.phase = (pos - p) % 1.0

    def _on_playback_end(self) -> None:
        if not self._loop:
            self.stop()

        if self._on_finished:
            self._on_finished()

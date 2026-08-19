from __future__ import annotations
from pathlib import Path
import time
import atexit

# If there is no official wheel yet:
# pip install -i https://test.pypi.org/simple/ pyo
import pyo

from yonder.types import Soundbank, HIRCNode
from yonder.util import logger
from .equalizer import Equalizer
from .play_context import PlayContext


# TODO
# - fix playback
# - use S/MT duration instead of file info?
# - attenuation distance handling
# - guess steam directory for resolution


class Player:
    def __init__(
        self,
        bnk: Soundbank,
        entrypoint: HIRCNode,
        vgmstream_exe: Path | str,
        wem_search_paths: list[Path] = None,
    ):
        if not isinstance(entrypoint, HIRCNode):
            entrypoint = bnk[entrypoint]

        self.bnk = bnk
        self.entrypoint = entrypoint
        self.ctx = PlayContext(bnk, vgmstream_exe, wem_search_paths or [])
        self._playing = False

        # NOTE crashes on some systems with input enabled, but we don't need it
        self._server: pyo.Server = pyo.Server(duplex=0)
        self._server.deactivateMidi()
        self._server.boot()

        self._mixer = pyo.Mixer(outs=1, chnls=1, time=0.05)
        self._equalizer = Equalizer(self._mixer[0])
        self._gate = pyo.SigTo(value=1.0, time=0.05)
        
        # master chain: mixer -> gate -> dac
        self._master = self._equalizer * self._gate
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
        self.entrypoint.stop(self.ctx)

        if self._server.getIsStarted():
            self._server.stop()
            # Allow the server to drain all buffers and callbacks
            time.sleep(0.25)

        if self._server.getIsBooted():
            self._server.shutdown()

        atexit.unregister(self.close)

    @property
    def playing(self) -> bool:
        return self._playing

    def seek(self, pos: float) -> float:
        logger.error("Seek is not implemented yet")

    def play(self, dur: float = 0, delay: float = 0) -> None:
        if self._playing:
            return

        self._playing = True
        node_out = self.entrypoint.pyo(self.ctx)
        self.entrypoint.play(self.ctx)
        self._mixer.clear()
        self._mixer.addInput(0, node_out)
        self._mixer.setAmp(0, 0, 1)

    def stop(self, wait: float = 0) -> None:
        self.entrypoint.stop(self.ctx)
        self._playing = False

    def set_master_volume(self, vol: float, time: float = 0.05) -> None:
        self._gate.time = time
        self._gate.value = vol

    def set_muted(self, muted: bool) -> None:
        self._gate.time = 0.05
        self._gate.value = 0.0 if muted else 1.0

    def set_equalizer(self, values: list[float] = None) -> None:
        self._equalizer.set_values(values)

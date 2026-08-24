from __future__ import annotations
from pathlib import Path
import time
import atexit

# If there is no official wheel yet:
# pip install -i https://test.pypi.org/simple/ pyo
import pyo

from yonder.types import Soundbank, HIRCNode, Sound, MusicTrack
from yonder.types.mixins import StateMixin, RtpcMixin
from yonder.util import logger
from .equalizer import Equalizer
from .play_context import PlayContext


# TODO
# - fix playback
# - attenuation distance handling
# - guess steam directory for resolution


class HIRCPlayer:
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
        self.context = PlayContext(bnk, vgmstream_exe, wem_search_paths or [])
        self._voice_gains: dict[int, float] = {}
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
        self.entrypoint.stop(self.context)

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

    def collect_control_states(
        self, active_only: bool
    ) -> tuple[list[int], dict[int, set[int]]]:
        rtpcs: list[int] = []
        states: dict[int, set[int]] = {}
        todo: list[HIRCNode] = [self.entrypoint]

        while todo:
            node = todo.pop()

            if not active_only or node.is_pyo_initialized():
                if isinstance(node, StateMixin):
                    for group in node.states.state_group_chunks:
                        group_states = states.setdefault(group.state_group_id, set())
                        group_states.update([s.state_id for s in group.states])

                if isinstance(node, RtpcMixin):
                    for rtpc in node.rtpcs:
                        rtpcs.append(rtpc.id)

                for _, ref in node.get_references():
                    child = self.bnk.get(ref)
                    if child:
                        todo.append(child)

        return (states, rtpcs)

    def collect_voices(self, active_only: bool) -> list[Sound | MusicTrack]:
        sources = []
        todo = [self.entrypoint]

        while todo:
            node = todo.pop()

            if (not active_only or node.is_pyo_initialized()) and isinstance(
                node, (Sound, MusicTrack)
            ):
                sources.append(node)

        return sources

    def set_volume(self, voice_id: int | None, vol_db: float) -> None:
        if voice_id is None:
            for node in self.collect_voices(True):
                self.set_volume(node.id, vol_db)
        else:
            node = self.bnk[voice_id]
            node.pyo(self.context)[1].volume = vol_db

    def set_muted(self, voice_id: int | None, muted: bool) -> None:
        if voice_id is None:
            for node in self.collect_voices(True):
                self.set_muted(node.id, muted)
        else:
            _, voice = node.pyo(self.context)
            if muted:
                if voice.gain > 0:
                    self._voice_gains[node.id] = voice.gain
                    voice.gain = 0
            else:
                voice.gain = self._voice_gains.get(node.id, 1.0)

    def set_master_volume(self, vol: float, time: float = 0.05) -> None:
        self._gate.time = time
        self._gate.value = vol

    def set_equalizer(self, values: list[float] = None) -> None:
        self._equalizer.set_values(values)

    def apply_context(self, ctx: PlayContext = None) -> None:
        if not ctx:
            ctx = self.context

        self.entrypoint.update_playback(ctx)
        self.context = ctx

    def seek(self, pos: float) -> float:
        logger.error("Seek is not implemented yet")

    def play(self, dur: float = 0, delay: float = 0) -> None:
        if self._playing:
            return

        self._playing = True
        node_out = self.entrypoint.pyo(self.context)
        self.entrypoint.play(self.context)
        self._mixer.clear()
        self._mixer.addInput(0, node_out)
        self._mixer.setAmp(0, 0, 1)

    def stop(self, wait: float = 0) -> None:
        self.entrypoint.stop(self.context)
        self._playing = False

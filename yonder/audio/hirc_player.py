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
        context: PlayContext,
    ):
        if not isinstance(entrypoint, HIRCNode):
            entrypoint = bnk[entrypoint]

        self.bnk = bnk
        self.entrypoint = entrypoint
        self.context = context
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

    def collect_voices(
        self, active_only: bool, start_from: int | HIRCNode = None
    ) -> list[Sound | MusicTrack]:
        if not start_from:
            start_from = self.entrypoint.id

        sources = []
        todo = [start_from]

        while todo:
            node_id = todo.pop()
            node = self.bnk.get(node_id)

            if not node:
                continue

            if (not active_only or node.is_pyo_initialized()) and isinstance(
                node, (Sound, MusicTrack)
            ):
                sources.append(node)

                for _, ref in node.get_references():
                    child = self.bnk.get(ref)
                    if child:
                        todo.append(child)

        return sources

    def collect_effective_contexts(
        self, active_only: bool = True, start_from: int | HIRCNode = None
    ) -> dict[int, PlayContext]:
        if not start_from:
            start_from = self.entrypoint.id

        ret = {}
        todo = [(start_from, self.context)]

        while todo:
            node_id, ctx = todo.pop()
            node = self.bnk.get(node_id)

            if not node:
                continue

            if not active_only or node.is_pyo_initialized():
                node_ctx = ctx.merge(node)
                ret[node.id] = node_ctx

                for _, ref in node.get_references():
                    child = self.bnk.get(ref)
                    if child:
                        todo.append((child, node_ctx))

        return ret

    def set_volume(self, node_id: int | None, vol_db: float) -> None:
        for node in self.collect_voices(True, node_id):
            node.pyo(self.context).playback.volume = vol_db

    def set_muted(self, node_id: int | None, muted: bool) -> None:
        for node in self.collect_voices(True, node_id):
            voice = node.pyo(self.context).playback
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
        node_out = self.entrypoint.pyo(self.context).playback
        self.entrypoint.play(self.context)
        self._mixer.clear()
        self._mixer.addInput(0, node_out)
        self._mixer.setAmp(0, 0, 1)

    def stop(self, wait: float = 0) -> None:
        self.entrypoint.stop(self.context)
        self._playing = False

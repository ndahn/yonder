from __future__ import annotations
import time
import atexit
from typing import Callable

# If there is no official wheel yet:
# pip install -i https://test.pypi.org/simple/ pyo
import pyo

from yonder.types import Soundbank, HIRCNode, Sound, MusicTrack
from yonder.util import logger
from .audiomath import db_to_amp
from .equalizer import Equalizer
from .play_context import PlayContext


class HIRCPlayer:
    def __init__(
        self,
        entrypoint: HIRCNode,
        context: PlayContext,
        on_finished: Callable[[], None] = None,
    ):
        # TODO need to include the AMX uptree

        self.entrypoint = entrypoint
        self.context = context
        self._voice_gains: dict[int, float] = {}
        self._playing = False
        self._play_epoch = 0
        self._on_finished: Callable[[], None] = on_finished

        # NOTE crashes on some systems with input enabled, but we don't need it
        self._server: pyo.Server = pyo.Server(duplex=0)
        self._server.deactivateMidi()
        self._server.boot()

        self._mixer = pyo.Mixer(outs=1, chnls=2, time=0.05)
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

    def init_pyo(self) -> None:
        if not self.entrypoint.is_pyo_initialized():
            self.entrypoint.pyo(self.context)

    def close(self) -> None:
        # close is called again by __del__ and atexit, avoid closing twice
        if getattr(self, "_closed", False):
            return

        self._closed = True

        if self._server.getIsStarted():
            self._server.stop()
            # Allow the server to drain all buffers and callbacks
            time.sleep(0.25)

        # Deleting the objects is safe now that processing has ended
        self.entrypoint.release_pyo(self.context, 0)

        if self._server.getIsBooted():
            self._server.shutdown()

        atexit.unregister(self.close)

    @property
    def playing(self) -> bool:
        return self._playing

    def collect_voices(
        self, start_from: int | HIRCNode = None
    ) -> list[Sound | MusicTrack]:
        if not start_from:
            start_from = self.entrypoint.id

        sources = []
        todo = [start_from]

        while todo:
            node_id = todo.pop()
            node = self.context.bank.get(node_id)

            if not node:
                continue

            if isinstance(node, (Sound, MusicTrack)):
                sources.append(node)

                for _, ref in node.get_references():
                    child = self.context.bank.get(ref)
                    if child:
                        todo.append(child)

        return sources

    def set_equalizer(self, values: list[float] = None) -> None:
        self._equalizer.set_values(values)

    def set_master_volume(self, vol: float, time: float = 0.05) -> None:
        self._gate.time = time
        self._gate.value = db_to_amp(vol)

    def set_volume(self, vol: float, node_id: int = None) -> None:
        gain = db_to_amp(vol)
        node: Sound | MusicTrack
        for node in self.collect_voices(True, node_id):
            state = node.pyo_state()
            if state:
                state.output.master_gain = gain

    def set_muted(self, muted: bool, node_id: int = None) -> None:
        node: Sound | MusicTrack
        for node in self.collect_voices(True, node_id):
            state = node.pyo_state()
            if not state:
                continue

            voice = state.output
            if muted:
                if voice.master_gain > 0:
                    self._voice_gains[node.id] = voice.master_gain
                    voice.master_gain = 0
            else:
                voice.master_gain = self._voice_gains.get(node.id, 1.0)

    def seek(self, pos: float, node_id: int = None) -> float:
        node: Sound | MusicTrack
        for node in self.collect_voices(True, node_id):
            state = node.pyo_state()
            if state:
                state.output.seek(pos)

    def play(self, dur: float = 0, delay: float = 0) -> None:
        if self._playing:
            return

        self._playing = True
        node_out = self.entrypoint.pyo(self.context).output
        self.entrypoint.play(self.context)

        # Notice when playback ends on its own. Triggers armed here may outlive 
        # this play (e.g. when the user stops early), so the epoch invalidates 
        # them instead of letting them finish a later play
        self._play_epoch += 1
        epoch = self._play_epoch

        def on_end(ctx: PlayContext) -> None:
            if epoch == self._play_epoch:
                self._finish()

        self.entrypoint.register_end_trigger(self.context, on_end)

        self._mixer.clear()
        self._mixer.addInput(0, node_out)
        self._mixer.setAmp(0, 0, 1)

    def apply_context(self, ctx: PlayContext = None) -> None:
        if not ctx:
            ctx = self.context

        self.context = ctx
        self.entrypoint.update_playback(ctx)

    def _finish(self) -> None:
        # Stop everything so the next play() starts from a clean slate
        self.stop()

        if self._on_finished:
            self._on_finished()

    def stop(self, wait: float = 0) -> None:
        self._play_epoch += 1
        self.entrypoint.stop(self.context)
        self._playing = False

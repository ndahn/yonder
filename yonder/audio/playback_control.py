from __future__ import annotations
from typing import Literal, Callable, Iterable
import random
import numpy as np
import pyo

from .voice import Voice


class PlaybackControl: ...
Playable = PlaybackControl | Voice


class VoiceManager:
    def __init__(self, nodes: list[Playable]):
        self.nodes = nodes
        # maintained by the owning PlaybackControl
        self.active: list[Playable] = []
        self.jump: Callable[[Playable | list[Playable]], None] = None

    @property
    def duration(self) -> float:
        # a seek can never pass this node
        return np.inf

    @property
    def pos(self) -> float:
        return max((n.pos for n in self.active), default=0.0)

    def seek(self, pos: float) -> float:
        # reposition what plays, discard the remainder
        for n in self.active:
            n.seek(pos)

        return 0.0

    def __next__(self) -> Playable | list[Playable]:
        raise NotImplementedError()


class RandomManager(VoiceManager):
    def __init__(self, nodes: list[Playable], weights: list[int]):
        super().__init__(nodes)
        self.weights = list(weights)

    def __next__(self) -> Playable:
        return random.choices(self.nodes, self.weights)[0]


class ShuffleManager(VoiceManager):
    def __init__(
        self,
        nodes: list[Playable],
        weights: list[int],
        wrap: bool = True,
        shuffle_after_wrap: bool = False,
    ):
        super().__init__(nodes)
        self.weights = weights
        self.wrap = wrap
        self.shuffle_after_wrap = shuffle_after_wrap
        self.index = -1
        self.playlist = []
        self.shuffle()

    @property
    def duration(self) -> float:
        # wrapping shuffles never end
        if self.wrap:
            return np.inf

        return sum(n.duration for n in self.nodes)

    @property
    def pos(self) -> float:
        if self.index < 0:
            return 0.0

        past = sum(n.duration for n in self.playlist[: self.index])
        return past + self.playlist[self.index].pos

    def seek(self, pos: float) -> float:
        for idx, node in enumerate(self.playlist):
            if pos < node.duration:
                self.index = idx
                self.jump(node)
                return node.seek(pos)

            pos -= node.duration

        return pos

    def shuffle(self) -> list[Playable]:
        probabilities = np.asarray(self.weights) / np.sum(self.weights)

        self.playlist = np.random.choice(
            self.nodes,
            len(self.nodes),
            replace=False,
            p=probabilities,
        ).tolist()

        return self.playlist

    def __next__(self) -> Playable:
        self.index += 1

        if self.wrap:
            self.index %= len(self.nodes)
            if self.index == 0 and self.shuffle_after_wrap:
                self.shuffle()
        elif self.index >= len(self.nodes):
            raise StopIteration()

        return self.playlist[self.index]


class PlaylistManager(VoiceManager):
    def __init__(self, nodes: list[Playable], wrap: bool = True):
        super().__init__(nodes)
        self.wrap = wrap
        self.index = 0

    @property
    def current(self) -> Playable:
        return self.nodes[max(0, self.index)]

    @property
    def duration(self) -> float:
        # a wrapping playlist never ends
        if self.wrap:
            return np.inf

        return sum(n.duration for n in self.nodes)

    @property
    def pos(self) -> float:
        past = sum(n.duration for n in self.nodes[: self.index])
        return past + self.current.pos

    def seek(self, pos: float) -> float:
        total = sum(n.duration for n in self.nodes)

        if self.wrap and np.isfinite(total):
            pos %= total

        for idx, node in enumerate(self.nodes):
            if pos < node.duration:
                # inf children land here
                self.index = idx
                self.jump(node)
                return node.seek(pos)

            pos -= node.duration

        return pos

    def __next__(self) -> Playable:
        self.index += 1

        if self.wrap:
            self.index %= len(self.nodes)
        elif self.index >= len(self.nodes):
            raise StopIteration()

        return self.nodes[self.index]


class ParallelManager(VoiceManager):
    def __init__(
        self,
        nodes: list[Playable],
        whitelist: Iterable[int] = None,
        blacklist: Iterable[int] = None,
    ):
        super().__init__(nodes)
        self.whitelist = set(whitelist or [])
        self.blacklist = set(blacklist or [])

    @property
    def valid(self) -> list[Playable]:
        ret = list(enumerate(self.nodes))

        if self.whitelist:
            ret = [(i, n) for i, n in ret if i in self.whitelist]

        if self.blacklist:
            ret = [(i, n) for i, n in ret if i not in self.blacklist]

        return [x[1] for x in ret]

    @property
    def duration(self) -> float:
        return max((n.duration for n in self.valid), default=0.0)

    def seek(self, pos: float) -> float:
        residuals = [n.seek(pos) for n in self.active]

        if any(r <= 0 for r in residuals):
            return 0.0

        return min(residuals)

    def __next__(self) -> list[Playable]:
        return self.valid


class SwitchManager(VoiceManager):
    def __init__(
        self,
        nodes: list[Playable],
        switch_map: dict[int, list[int]] = None,
        default_state: int = None,
    ):
        super().__init__(nodes)
        self.switch_map = switch_map or {}
        self.state: int = default_state
        self.default_state = default_state

    def __next__(self) -> Playable:
        indices = self.switch_map.get(self.state)
        if indices is None:
            indices = self.switch_map.get(self.default_state, [])

        return [self.nodes[i] for i in indices]


class ManualManager(VoiceManager):
    def __init__(self, nodes: list[Playable], index: int = 0):
        super().__init__(nodes)
        self.index = index

    def __next__(self) -> Playable:
        return self.nodes[self.index]


class PlaybackControl(pyo.PyoObject):
    def __init__(
        self,
        children: Playable | list[Playable],
        playback_mode: Literal[
            "random", "shuffle", "playlist", "parallel", "switch", "manual"
        ] = "random",
        weights: list[int] = None,
        mul: float = 1,
        add: float = 0,
    ):
        pyo.PyoObject.__init__(self, mul, add)

        self.children: list[Playable] = []
        self.weights: list[int] = []
        self.selector: VoiceManager = None
        self._pending: set[int] = set()
        self._watchers: list[pyo.TrigFunc] = []
        self._current_voices: list[Playable] = []
        self._playing = False

        # audio side: children feed an internal mixer whose output is this
        # object's stream. addInput lets children join while audio runs
        self._mixer = pyo.Mixer(outs=1, chnls=1, time=0.05)
        self._base_objs = self._mixer[0].getBaseObjects()
        self._trig = pyo.Trig()

        self._playback_mode = None
        self.playback_mode = playback_mode

        if children:
            if not isinstance(children, list):
                children = [children]

            if not weights:
                weights = [50000] * len(children)

            for child, weight in zip(children, weights):
                self.add_child(child, weight)

    @property
    def playback_mode(self) -> str:
        return self._playback_mode

    @playback_mode.setter
    def playback_mode(
        self,
        mode: Literal["random", "shuffle", "playlist", "parallel", "switch", "manual"],
    ) -> None:
        if mode == "random":
            self.selector = RandomManager(self.children, self.weights)
        elif mode == "shuffle":
            self.selector = ShuffleManager(self.children, self.weights)
        elif mode == "playlist":
            self.selector = PlaylistManager(self.children, True)
        elif mode == "parallel":
            self.selector = ParallelManager(self.children)
        elif mode == "switch":
            self.selector = SwitchManager(self.children)
        elif mode == "manual":
            self.selector = ManualManager(self.children)
        else:
            raise ValueError(f"Unknown playback mode {mode}")

        self.selector.jump = self._activate
        self._playback_mode = mode

    def add_child(self, child: Playable, weight: int = 50000) -> None:
        idx = len(self.children)

        # selectors share our list instances, so this is enough
        self.children.append(child)
        self.weights.append(weight)

        self._mixer.addInput(idx, child)
        self._mixer.setAmp(idx, 0, 1.0)

        # Wire up the child's end trigger
        self._watchers.append(
            pyo.TrigFunc(child["trig"], self._on_child_finished, arg=idx)
        )

    def _on_child_finished(self, idx: int) -> None:
        if not self._playing:
            return

        self._pending.discard(idx)
        if self._pending:
            return

        self._advance()

    def _advance(self, inc: int = 1) -> None:
        if inc <= 0:
            raise ValueError("inc must be > 0")

        try:
            for _ in range(inc):
                selected = next(self.selector)
        except StopIteration:
            self._on_finish()
            return

        self._activate(selected)

    def _activate(self, selected: Playable | list[Playable]) -> None:
        if not isinstance(selected, list):
            selected = [selected]

        for voice in self._current_voices:
            if voice not in selected:
                voice.stop()

        self._current_voices = selected
        self._pending = {self.children.index(n) for n in selected}
        self.selector.active = selected

        for voice in selected:
            voice.play()

    @property
    def duration(self) -> float:
        return self.selector.duration

    @property
    def pos(self) -> float:
        return self.selector.pos

    def seek(self, pos: float) -> float:
        residual = self.selector.seek(pos)

        if residual > 0:
            # Seeked past our end. Don't tri
            self.stop()

        return residual

    def play(self, dur: float = 0, delay: float = 0) -> pyo.PyoObject:
        self._playing = True
        self._advance()
        return pyo.PyoObject.play(self, dur, delay)

    def stop(self, wait: float = 0) -> pyo.PyoObject:
        self._playing = False
        for voice in self._current_voices:
            voice.stop()

        return pyo.PyoObject.stop(self, wait)

    def out(
        self, chnl: int = 0, inc: int = 1, dur: float = 0, delay: float = 0
    ) -> pyo.PyoObject:
        self.play()
        return pyo.PyoObject.out(self, chnl, inc, dur, delay)

    def _on_finish(self) -> None:
        self._playing = False
        self._trig.play()

    def __getitem__(self, key: str):
        if key == "trig":
            return self._trig

        return pyo.PyoObject.__getitem__(self, key)

from typing import Literal, Generator, Iterable
import random
import numpy as np
import pyo


class NodeSelector:
    def __init__(self, nodes: list[pyo.PyoObject]):
        self.nodes = nodes

    def __next__(self) -> pyo.PyoObject:
        raise NotImplementedError()


class RandomSelector(NodeSelector):
    def __init__(self, nodes: list[pyo.PyoObject], weights: list[int]):
        super().__init__(nodes)
        self.weights = list(weights)

    def __next__(self) -> Generator[pyo.PyoObject, None, None]:
        yield random.choices(self.nodes, self.weights)[0]


class ShuffleSelector(NodeSelector):
    def __init__(self, nodes: list[pyo.PyoObject], weights: list[int], wrap: bool = True, shuffle_after_wrap: bool = False):
        super().__init__(nodes)
        self.weights = weights
        self.wrap = wrap
        self.shuffle_after_wrap = shuffle_after_wrap
        self.index = -1
        self.playlist = []
        self.shuffle()

    def shuffle(self) -> list[pyo.PyoObject]:
        probabilities = np.asarray(self.weights) / np.sum(self.weights)
        self.playlist = np.random.choice(
            self.nodes,
            len(self.nodes),
            replace=False,
            p=probabilities,
        ).tolist()
        return self.playlist

    def __next__(self) -> Generator[pyo.PyoObject, None, None]:
        self.index += 1

        if self.wrap:
            self.index %= len(self.nodes)
            if self.index == 0 and self.shuffle_after_wrap:
                self.shuffle()
        elif self.index >= len(self.nodes):
            raise StopIteration()

        yield self.playlist[self.index]


class PlaylistSelector(NodeSelector):
    def __init__(self, nodes: list[pyo.PyoObject], wrap: bool = True):
        super().__init__(nodes)
        self.wrap = wrap
        self.index = -1

    def __next__(self) -> Generator[pyo.PyoObject, None, None]:
        self.index += 1

        if self.wrap:
            self.index %= len(self.nodes)
        elif self.index >= len(self.nodes):
            raise StopIteration()

        yield self.nodes[self.index]


class ParallelSelector(NodeSelector):
    def __init__(
        self,
        nodes: list[pyo.PyoObject],
        whitelist: Iterable[int] = None,
        blacklist: Iterable[int] = None,
    ):
        super().__init__(nodes)
        self.whitelist = set(whitelist or [])
        self.blacklist = set(blacklist or [])

    @property
    def valid(self) -> list[pyo.PyoObject]:
        ret = list(enumerate(self.nodes))

        if self.whitelist:
            ret = [(i, n) for i, n in ret if i in self.whitelist]
        if self.blacklist:
            ret = [(i, n) for i, n in ret if i not in self.blacklist]

        return [x[1] for x in ret]

    def __next__(self) -> Generator[list[pyo.PyoObject], None, None]:
        yield self.valid


class IndexSelector(NodeSelector):
    def __init__(self, nodes: list[pyo.PyoObject], index: int = 0):
        super().__init__(nodes)
        self.index = index

    def __next__(self) -> Generator[pyo.PyoObject, None, None]:
        yield self.nodes[self.index]


class PlaybackControl(pyo.PyoObject):
    def __init__(
        self,
        children: pyo.PyoObject | list[pyo.PyoObject],
        playback_mode: Literal[
            "random", "shuffle", "playlist", "parallel", "select"
        ] = "random",
        weights: list[int] = None,
        mul: float = 1,
        add: float = 0,
    ):
        pyo.PyoObject.__init__(self, mul, add)

        self.children: list[pyo.PyoObject] = []
        self.weights: list[int] = []
        self.selector: NodeSelector = None
        self._pending: set[int] = set()
        self._watchers: list[pyo.TrigFunc] = []
        self._current_voices: list[pyo.PyoObject] = []
        self._playing = False

        # audio side: children feed an internal mixer whose output is this
        # object's stream. addInput lets children join while audio runs
        self._mixer = pyo.Mixer(outs=1, chnls=1, time=0.05)
        self._base_objs = self._mixer[0].getBaseObjects()
        self._trig = pyo.Trig()

        self._playback_mode = None
        self.playback_mode = playback_mode
        
        if children:
            if isinstance(children, pyo.PyoObject):
                children = [children]

            if not weights:
                weights = [50000] * len(children)

            for child, weight in zip(children, weights):
                self.add_child(child, weight)

    @property
    def playback_mode(self) -> str:
        return self._playback_mode

    @playback_mode.setter
    def playback_mode(self, mode: Literal["random", "shuffle", "playlist", "parallel", "select"]) -> None:
        if mode == "random":
            self.selector = RandomSelector(self.children, self.weights)
        elif mode == "shuffle":
            self.selector = ShuffleSelector(self.children, self.weights)
        elif mode == "playlist":
            self.selector = PlaylistSelector(self.children, self.weights)
        elif mode == "parallel":
            self.selector = ParallelSelector(self.children)
        elif mode == "select":
            self.selector = IndexSelector(self.children)
        else:
            raise ValueError(f"Unknown playback mode {mode}")

    def add_child(self, child: pyo.PyoObject, weight: int = 50000) -> None:
        idx = len(self.children)

        # selectors share our list instances, so this is enough
        self.children.append(child)
        self.weights.append(weight)

        self._mixer.addInput(idx, child)
        self._mixer.seAmp(idx, 0, 1.0)

        # Wire up the child's end trigger
        self._watchers.append(pyo.TrigFunc(child["trig"], self._on_child_finished, arg=idx))

    def _on_child_finished(self, idx: int) -> None:
        if not self._playing:
            return

        self._pending.discard(idx)
        if self._pending:
            return

        self._advance()

    def _advance(self) -> None:
        try:
            selected = next(self.selector)
        except StopIteration:
            self._on_finish()

        if not isinstance(selected, list):
            selected = [selected]
        
        self._current_voices = selected
        self._pending = {self.children.index(v) for v in selected}

        for voice in selected:
            voice.play()

    def play(self, dur: float = 0, delay: float = 0) -> pyo.PyoObject:
        self._playing = True
        self._advance()
        return pyo.PyoObject.play(self, dur, delay)

    def stop(self, wait: float = 0) -> pyo.PyoObject:
        self._playing = False
        for voice in self._current_voices:
            voice.stop()
        
        return pyo.PyoObject.stop(self, wait)

    def out(self, chnl: int = 0, inc: int = 1, dur: float = 0, delay: float = 0) -> pyo.PyoObject:
        self.play()
        return pyo.PyoObject.out(self,chnl, inc, dur, delay)

    def _on_finish(self) -> None:
        self._playing = False
        self._trig.play()

    def __getitem__(self, key: str):
        if key == "trig":
            return self._trig
        
        return pyo.PyoObject.__getitem__(self, key)

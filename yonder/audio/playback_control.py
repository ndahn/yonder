from typing import Literal, Generator, Iterable
import random
import numpy as np
import pyo


class NodeSelector:
    def __init__(self, nodes: list[pyo.PyoObject]):
        self.nodes = list(nodes)

    def __next__(self) -> pyo.PyoObject:
        raise NotImplementedError()


class RandomSelector(NodeSelector):
    def __init__(self, nodes: list[pyo.PyoObject], weights: list[int] = None):
        super().__init__(nodes)

        if not weights:
            weights = [50000] * len(nodes)

        self.weights = list(weights)

    def __next__(self) -> Generator[pyo.PyoObject, None, None]:
        yield random.choices(self.nodes, self.weights)[0]


class ShuffleSelector(NodeSelector):
    def __init__(self, nodes: list[pyo.PyoObject], weights: list[int] = None, wrap: bool = True, shuffle_after_wrap: bool = False):
        super().__init__(nodes)

        if not weights:
            weights = [50000] * len(nodes)

        self.weights = list(weights)
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


class PlaybackControl:
    def __init__(
        self,
        children: pyo.PyoObject | list[pyo.PyoObject],
        playback_mode: Literal[
            "random", "shuffle", "playlist", "parallel", "select"
        ] = "random",
        weights: list[int] = None,
    ):
        if isinstance(children, pyo.PyoObject):
            children = [children]

        self.selector: NodeSelector = None
        self._playback_mode = None

        self.children = children
        self.playback_mode = playback_mode
        self.weights = list(weights) if weights else [50000] * len(children)

        self._current_voices: list[pyo.PyoObject] = []
        self._playing = False

        # TODO we should use pyo's event API for this
        for voice in children:
            voice.on_voice_finished = self._advance

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
        self.children.append(child)
        self.weights.append(weight)

        self.selector.nodes.append(child)
        if hasattr(self.selector, "weights"):
            self.selector.weights.append(weight)

        # TODO wire up the child's end trigger

    def play(self) -> None:
        self._playing = True
        self._advance()

    def stop(self) -> None:
        self._playing = False
        for voice in self._current_voices:
            voice.stop()

    def _advance(self) -> None:
        if not self._playing:
            return

        selected = next(self.selector)
        if not isinstance(selected, list):
            selected = [selected]
        
        self._current_voices = selected
        for voice in selected:
            voice.play()

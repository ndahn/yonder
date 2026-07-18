from typing import Literal
import random
import pyo


class PlaybackControl:
    def __init__(
        self,
        children: pyo.PyoObject | list[pyo.PyoObject],
        playback_mode: Literal["random", "shuffle", "playlist", "parallel", "select"] = "random",
        weights: list[int] = None,
    ):
        if isinstance(children, pyo.PyoObject):
            children = [children]

        self.children = children
        self.playback_mode = playback_mode
        self.weights = list(weights) if weights else [50000] * len(children)

        self._current_voice: pyo.PyoObject = None
        self._playing = False
        self._selected = 0

        # TODO Voice should implement pyo's event interface for this
        for voice in children:
            voice.on_voice_finished = self._advance

    def add_child(self, child: pyo.PyoObject, weight: float = 50000) -> None:
        self.children.append(child)
        self.weights.append(weight)

    def select(self, idx: int) -> None:
        self._selected = idx

    def play(self) -> None:
        self._playing = True
        self._advance()

    def stop(self) -> None:
        self._playing = False

        voices = self._current_voice or []
        if isinstance(voices, pyo.PyoObject):
            voices = [voices]

        for voice in voices:
            voice.stop()

    def _advance(self) -> None:
        if not self._playing:
            return

        # TODO could move playback control into separate classes
        if self.playback_mode == "random":
            self._current_voice = random.choices(self.children, self.weights)[0]
            self._current_voice.play()

        elif self.playback_mode == "shuffle":
            try:
                idx = self.children.index(self._current_voice)
            except ValueError:
                idx = -1

            # TODO make a random playlist and follow it, this is wrong
            self._current_voice = random.choices(
                [v for i, v in enumerate(self.children) if i != idx],
                [w for i, w in enumerate(self.weights) if i != idx],
            )
            self._current_voice.play()

        elif self.playback_mode == "playlist":
            try:
                idx = self.children.index(self._current_voice)
            except ValueError:
                idx = 0

            self._current_voice = self.children[(idx + 1) % len(self.children)]
            self._current_voice.play()

        elif self.playback_mode == "parallel":
            self._current_voice = self.children
            for voice in self.children:
                voice.play()

        elif self.playback_mode == "select":
            self._current_voice = self.children[self._selected]
            self._current_voice.play()

        else:
            raise ValueError(f"Unknown playback mode {self.playback_mode}")

from typing import Literal
import random

from .voice import Voice


class PlaybackControl:
    def __init__(
        self,
        children: list[Voice],
        playback_mode: Literal["random", "shuffle", "playlist", "parallel"] = "random",
        weights: list[int] = None,
    ):
        self.children = children
        self.playback_mode = playback_mode
        self.weights = list(weights) if weights else [1] * len(children)

        self._current_voice: Voice = None
        self._playing = False

        for voice in children:
            voice.on_voice_finished = self._advance

    def start(self) -> None:
        self._playing = True
        self._advance()

    def stop(self) -> None:
        self._playing = False

        voices = self._current_voice or []
        if isinstance(voices, Voice):
            voices = [voices]

        for voice in voices:
            voice.stop()

    def advance(self) -> None:
        if not self._playing:
            return

        if self.playback_mode == "random":
            self._current_voice = random.choices(self.children, self.weights)[0]
            self._current_voice.start()

        elif self.playback_mode == "shuffle":
            try:
                idx = self.children.index(self._current_voice)
            except ValueError:
                idx = -1

            self._current_voice = random.choices(
                [v for i, v in enumerate(self.children) if i != idx],
                [w for i, w in enumerate(self.weights) if i != idx],
            )
            self._current_voice.start()

        elif self.playback_mode == "playlist":
            try:
                idx = self.children.index(self._current_voice)
            except ValueError:
                idx = 0

            self._current_voice = self.children[(idx + 1) % len(self.children)]
            self._current_voice.start()

        elif self.playback_mode == "parallel":
            self._current_voice = self.children
            for voice in self.children:
                voice.start()

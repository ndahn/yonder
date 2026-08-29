from dataclasses import dataclass, field
import pyo

from .play_context import PlayContext


@dataclass
class PlaybackState:
    ctx: PlayContext
    playing: bool = False
    output: pyo.PyoObject = None
    cache: dict = field(default_factory=dict)

    def play(self, dur: int = 0, delay: int = 0) -> None:
        self.output.play(dur, delay)

    def stop(self, wait: int = 0) -> None:
        self.output.stop(wait)

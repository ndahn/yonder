from dataclasses import dataclass, field
from typing import ClassVar

from .structure import _HIRCNodeBody
from .rewwise_base_types import MusicNodeParams


@dataclass
class MusicMarkerWwise:
    id: int
    position: float = 0.0
    string_length: int = 0
    string: str = ""


@dataclass
class MusicSegment(_HIRCNodeBody):
    body_type: ClassVar[int] = 10
    music_node_params: MusicNodeParams = field(default_factory=MusicNodeParams)
    duration: float = 0.0
    marker_count: int = 0
    markers: list[MusicMarkerWwise] = field(default_factory=list)

    @property
    def parent(self) -> int:
        return self.music_node_params.node_base_params.direct_parent_id
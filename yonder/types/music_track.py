from dataclasses import dataclass, field
from typing import ClassVar

from .structure import _HIRCNodeBody
from .rewwise_base_types import (
    NodeBaseParams,
    BankSourceData,
    RTPCGraphPoint,
    PropBundle,
)
from .rewwise_enums import ClipAutomationType
from .mixins import PropertyMixin


@dataclass
class ClipAutomation:
    clip_index: int
    auto_type: ClipAutomationType = ClipAutomationType.Volume
    graph_point_count: int = 0
    graph_points: list[RTPCGraphPoint] = field(default_factory=list)


@dataclass
class TrackSrcInfo:
    track_id: int
    source_id: int
    event_id: int = 0
    play_at: float = 0.0
    begin_trim_offset: float = 0.0
    end_trim_offset: float = 0.0
    source_duration: float = 0.0


@dataclass
class MusicTrack(PropertyMixin, _HIRCNodeBody):
    body_type: ClassVar[int] = 11
    flags: int = 0
    source_count: int = 0
    sources: list[BankSourceData] = field(default_factory=list)
    playlist_item_count: int = 0
    playlist: list[TrackSrcInfo] = field(default_factory=list)
    subtrack_count: int = 0
    clip_item_count: int = 0
    clip_items: list[ClipAutomation] = field(default_factory=list)
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    track_type: int = 0
    look_ahead_time: int = 0

    @property
    def parent(self) -> int:
        return self.node_base_params.direct_parent_id

    @parent.setter
    def parent(self, new_parent: int) -> None:
        self.node_base_params.direct_parent_id = new_parent

    @property
    def properties(self) -> list[PropBundle]:
        return self.node_base_params.node_initial_params.prop_initial_values

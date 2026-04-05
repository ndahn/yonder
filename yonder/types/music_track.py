from dataclasses import dataclass, field
from typing import ClassVar
from pathlib import Path

from yonder.wem import get_wem_metadata
from .structure import _HIRCNodeBody, HIRCNode
from .rewwise_base_types import (
    NodeBaseParams,
    BankSourceData,
    MediaInformation,
    RTPCGraphPoint,
    PropBundle,
)
from .rewwise_enums import ClipAutomationType, PropID, PluginId, SourceType
from .mixins import PropertyMixin


@dataclass
class ClipAutomation:
    clip_index: int
    auto_type: ClipAutomationType = ClipAutomationType.Volume
    graph_point_count: int = 0
    graph_points: list[RTPCGraphPoint] = field(default_factory=list)


@dataclass
class TrackSrcInfo:
    track_id: int = 0
    source_id: int
    event_id: int = 0
    play_at: float = 0.0
    begin_trim_offset: float = 0.0
    end_trim_offset: float = 0.0
    source_duration: float = 0.0

    def get_references(self) -> list[tuple[str, int]]:
        # TODO not sure about track_id and event_id
        # source_id might also match an fx effect
        return [("source_id", self.source_id)]


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

    @classmethod
    def new(
        cls,
        nid: int | str,
        wem: Path = None,
        begin_trim: float = 0.0,
        end_trim: float = 0.0,
        source_type: SourceType = SourceType.Embedded,
        props: dict[PropID, float] = None,
        parent: int = 0,
    ) -> "HIRCNode[MusicTrack]":
        obj = HIRCNode(nid, cls())

        if wem:
            obj.body.add_source_from_wem(wem, begin_trim, end_trim, source_type=source_type)

        if props:
            for prop, val in props.items():
                obj.body.set_property(prop, val)

        obj.body.parent = parent
        return obj

    @property
    def parent(self) -> int:
        return self.node_base_params.direct_parent_id

    @parent.setter
    def parent(self, new_parent: int) -> None:
        self.node_base_params.direct_parent_id = new_parent

    @property
    def properties(self) -> list[PropBundle]:
        return self.node_base_params.node_initial_params.prop_initial_values

    def add_source_from_wem(
        self,
        wem: Path,
        begin_trim: float = 0.0,
        end_trim: float = 0.0,
        source_type: SourceType = SourceType.Embedded,
    ) -> BankSourceData:
        wem_id = wem.stem
        meta = get_wem_metadata(wem)
        size = meta["in_memory_size"]
        duration = meta["duration"]

        self.add_source(
            wem_id,
            size,
            duration,
            begin_trim=begin_trim,
            end_trim=end_trim,
            source_type=source_type,
        )

    def add_source(
        self,
        source_id: int,
        media_size: int,
        duration: float,
        begin_trim: float = 0.0,
        end_trim: float = 0.0,
        source_type: SourceType = SourceType.Embedded,
    ) -> BankSourceData:
        self.sources.append(
            BankSourceData(
                source_type=source_type,
                media_information=MediaInformation(source_id, media_size),
            )
        )
        self.playlist.append(
            TrackSrcInfo(
                source_id=source_id,
                play_at=-begin_trim,
                begin_trim_offset=begin_trim,
                end_trim_offset=end_trim,
                source_duration=duration,
            )
        )

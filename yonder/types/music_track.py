from dataclasses import dataclass, field
from typing import ClassVar
from pathlib import Path
from field_properties import field_property

from yonder.wem import get_wem_metadata
from .structure import HIRCNode
from .rewwise_base_types import (
    NodeBaseParams,
    BankSourceData,
    MediaInformation,
    RTPCGraphPoint,
    PropBundle,
)
from yonder.enums import ClipAutomationType, PropID, SourceType
from .mixins import PropertyMixin


@dataclass
class ClipAutomation:
    clip_index: int
    auto_type: ClipAutomationType = ClipAutomationType.Volume
    graph_point_count: int = field_property(init=False, raw=True)
    graph_points: list[RTPCGraphPoint] = field(default_factory=list)

    @field_property(graph_point_count)
    def get_graph_point_count(self) -> int:
        return len(self.graph_points)


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
class MusicTrack(PropertyMixin, HIRCNode):
    body_type: ClassVar[int] = 11
    flags: int = 0
    source_count: int = field_property(init=False, raw=True)
    sources: list[BankSourceData] = field(default_factory=list)
    playlist_item_count: int = field_property(init=False, raw=True)
    playlist: list[TrackSrcInfo] = field(default_factory=list)
    subtrack_count: int = field_property(init=False, raw=True)
    clip_item_count: int = field_property(init=False, raw=True)
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
        source_type: SourceType = SourceType.Streaming,
        props: dict[PropID, float] = None,
        parent: int = 0,
    ) -> "MusicTrack":
        super().__init__(nid)
        obj = cls()

        if wem:
            obj.add_source_from_wem(wem, begin_trim, end_trim, source_type=source_type)

        if props:
            for prop, val in props.items():
                obj.set_property(prop, val)

        obj.parent = parent
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

    @property
    def source_ids(self) -> list[int]:
        return [s.media_information.source_id for s in self.sources]

    @field_property(source_count)
    def get_source_count(self) -> int:
        return len(self.sources)

    @field_property(playlist_item_count)
    def get_playlist_item_count(self) -> int:
        return len(self.playlist)

    @field_property(subtrack_count)
    def get_subtrack_count(self) -> int:
        # TODO not clear what to return here
        return 0

    @field_property(clip_item_count)
    def get_clip_item_count(self) -> int:
        return len(self.clip_items)

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
        begin_trim = abs(begin_trim)
        self.playlist.append(
            TrackSrcInfo(
                source_id=source_id,
                play_at=-begin_trim,
                begin_trim_offset=begin_trim,
                end_trim_offset=-abs(end_trim),
                source_duration=duration,
            )
        )

    def add_clip(
        self,
        clip_type: ClipAutomationType,
        points: list[RTPCGraphPoint],
    ) -> ClipAutomation:
        clip = ClipAutomation(
            len(self.clip_items),
            clip_type,
            graph_points=points,
        )
        self.clip_items.append(clip)
        return clip

    def set_trims(self, begin_trim: float, end_trim: float, idx: int = 0) -> None:
        begin_trim = abs(begin_trim)
        self.playlist[idx].begin_trim_offset = begin_trim
        self.playlist[idx].play_at = -begin_trim
        self.playlist[idx].end_trim_offset = -abs(end_trim)

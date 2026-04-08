from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar, Any
from field_properties import field_property

from yonder.hash import calc_hash
from .hirc_node import HIRCNode
from .base_types import MusicNodeParams, PropBundle, Children, MusicMarkerWwise
from yonder.enums import PropID
from .mixins import PropertyMixin


@dataclass
class MusicSegment(PropertyMixin, HIRCNode):
    body_type: ClassVar[int] = 10
    music_node_params: MusicNodeParams = field(default_factory=MusicNodeParams)
    duration: float = 0.0
    marker_count: int = field_property(default=0)
    markers: list[MusicMarkerWwise] = field(default_factory=list)

    @classmethod
    def new(
        cls,
        nid: int | str,
        tracks: int | list[int] = None,
        markers: list[int | str, float] = None,
        props: dict[PropID, float] = None,
        parent: int = 0,
    ) -> MusicSegment:
        obj = cls(nid)

        if tracks:
            if isinstance(tracks, int):
                tracks = [tracks]
            obj.music_node_params.children.items = tracks

        if markers:
            for mid, pos in markers:
                obj.set_marker(mid, pos)

        if props:
            for prop, val in props.items():
                obj.set_property(prop, val)

        obj.parent = parent
        return obj

    @property
    def parent(self) -> int:
        return self.music_node_params.node_base_params.direct_parent_id

    @parent.setter
    def parent(self, new_parent: int) -> None:
        self.music_node_params.node_base_params.direct_parent_id = new_parent

    @property
    def children(self) -> Children:
        return self.music_node_params.children

    @property
    def properties(self) -> list[PropBundle]:
        return self.music_node_params.node_base_params.node_initial_params.prop_initial_values

    @field_property(marker_count)
    def get_marker_count(self) -> int:
        return len(self.markers)

    def set_marker(
        self, mid: int | str, pos: float, update: bool = True
    ) -> MusicMarkerWwise:
        if isinstance(mid, str):
            label = mid
            mid = calc_hash(mid)
        else:
            label = ""

        for marker in self.markers:
            if marker.id == mid:
                if update:
                    marker.position = pos
                else:
                    raise ValueError(f"Marker {mid} ({label}) already exists")

                return marker
        else:
            marker = MusicMarkerWwise(
                mid,
                pos,
                string_length=len(label) + 1 if label else 0,
                string=label,
            )
            self.markers.append(marker)

        return marker

    def get_marker(self, mid: int | str, default: Any = None) -> MusicMarkerWwise:
        if isinstance(mid, str):
            mid = calc_hash(mid)

        for marker in self.markers:
            if marker.id == mid:
                return marker

        return default

    def remove_marker(self, mid: int | str, missing_ok: bool = True) -> None:
        if isinstance(mid, str):
            mid = calc_hash(mid)

        for idx, marker in enumerate(self.markers):
            if marker.id == mid:
                self.markers.pop(idx)
                return

        if not missing_ok:
            raise ValueError(f"Marker {mid} not found")

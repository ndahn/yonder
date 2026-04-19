from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar, Any

from yonder.hash import calc_hash
from yonder.enums import PropID, MarkerId
from yonder.util import logger
from .hirc_node import HIRCNode
from .base_types import MusicNodeParams, PropBundle, Children, MusicMarkerWwise, RTPC
from .music_track import MusicTrack
from .mixins import PropertyMixin


@dataclass(repr=False)
class MusicSegment(PropertyMixin, HIRCNode):
    body_type: ClassVar[int] = 10
    music_node_params: MusicNodeParams = field(default_factory=MusicNodeParams)
    duration: float = 0.0
    marker_count: int = 0
    markers: list[MusicMarkerWwise] = field(default_factory=list)

    @classmethod
    def new(
        cls,
        nid: int | str,
        tracks: int | list[int] = None,
        markers: list[int | str, float] = None,
        props: dict[PropID, float] = None,
        parent: int | HIRCNode = 0,
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
    def parent(self, new_parent: int | HIRCNode) -> None:
        if isinstance(new_parent, HIRCNode):
            new_parent = new_parent.id
        self.music_node_params.node_base_params.direct_parent_id = new_parent

    @property
    def children(self) -> Children:
        return self.music_node_params.children

    @property
    def properties(self) -> list[PropBundle]:
        return self.music_node_params.node_base_params.node_initial_params.prop_initial_values

    @property
    def rtpcs(self) -> list[RTPC]:
        return self.music_node_params.node_base_params.initial_rtpc.rtpcs

    def attach(self, other: int | HIRCNode) -> None:
        if isinstance(other, HIRCNode):
            if not isinstance(other, MusicTrack):
                logger.warning("Attaching a non-MusicTrack to a MusicSegment is highly unusual and may result in an invalid soundbank!")

            if other.parent not in (0, self.id):
                logger.warning(
                    f"{other} is already parented to {other.parent} and will be detached"
                )
            other.parent = self.id
            other = other.id

        self.children.add(other)

    def detach(self, other: int | HIRCNode) -> None:
        if isinstance(other, HIRCNode):
            other = other.id

        if other in self.children:
            self.children.remove(other)

    def set_marker(
        self, mid: int | str | MarkerId, pos: float, update: bool = True
    ) -> MusicMarkerWwise:
        if isinstance(mid, str):
            label = mid
            mid = calc_hash(mid)
        else:
            label = ""

        mid = int(mid)

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

    def get_marker_pos(self, mid: int | str | MarkerId, default: float = 0.0) -> float:
        if isinstance(mid, str):
            mid = calc_hash(mid)

        mid = int(mid)

        for marker in self.markers:
            if marker.id == mid:
                return marker.position

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

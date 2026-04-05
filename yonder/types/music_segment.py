from dataclasses import dataclass, field
from typing import ClassVar
from field_properties import field_property

from yonder.hash import calc_hash
from .structure import _HIRCNodeBody, HIRCNode
from .rewwise_base_types import MusicNodeParams, PropBundle, Children
from yonder.enums import PropID
from .mixins import PropertyMixin, ContainerMixin


@dataclass
class MusicMarkerWwise:
    id: int
    position: float = 0.0
    string_length: int = 0
    string: str = ""


@dataclass
class MusicSegment(PropertyMixin, ContainerMixin, _HIRCNodeBody):
    body_type: ClassVar[int] = 10
    music_node_params: MusicNodeParams = field(default_factory=MusicNodeParams)
    duration: float = 0.0
    marker_count: int = field_property(init=False, raw=True)
    markers: list[MusicMarkerWwise] = field(default_factory=list)

    @classmethod
    def new(
        cls,
        nid: int | str,
        tracks: int | list[int] = None,
        markers: list[int | str, float] = None,
        props: dict[PropID, float] = None,
        parent: int = 0,
    ) -> "HIRCNode[MusicSegment]":
        obj = HIRCNode(nid, cls())

        if tracks:
            if isinstance(tracks, int):
                tracks = [tracks]
            obj.body.music_node_params.children.items = tracks

        if markers:
            for mid, pos in markers:
                obj.body.set_marker(mid, pos)

        if props:
            for prop, val in props.items():
                obj.body.set_property(prop, val)

        obj.body.parent = parent
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

    def set_marker(self, mid: int | str, pos: float, update: bool = True) -> None:
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

                break
        else:
            self.markers.append(
                MusicMarkerWwise(
                    mid,
                    pos,
                    string_length=len(label) + 1 if label else 0,
                    string=label,
                )
            )

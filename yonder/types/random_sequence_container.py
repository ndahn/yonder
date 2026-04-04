from dataclasses import dataclass, field
from typing import ClassVar

from .structure import _HIRCNodeBody
from .rewwise_base_types import NodeBaseParams, Children, PropBundle
from .mixins import PropertyMixin, ContainerMixin


@dataclass
class PlaylistItem:
    play_id: int
    weight: int = 50

    def get_references(self) -> list[tuple[str, int]]:
        return [("play_id", self.play_id)]


@dataclass
class Playlist:
    count: int = 0
    items: list[PlaylistItem] = field(default_factory=list)


@dataclass
class RandomSequenceContainer(PropertyMixin, ContainerMixin, _HIRCNodeBody):
    body_type: ClassVar[int] = 5
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    loop_count: int = 0
    loop_mod_min: int = 0
    loop_mod_max: int = 0
    transition_time: float = 0.0
    transition_time_mod_min: float = 0.0
    transition_time_mod_max: float = 0.0
    avoid_repeat_count: int = 0
    transition_mode: int = 0
    random_mode: int = 0
    mode: int = 0
    flags: int = 0
    children: Children = field(default_factory=Children)
    playlist: Playlist = field(default_factory=Playlist)

    @property
    def parent(self) -> int:
        return self.node_base_params.direct_parent_id

    @parent.setter
    def parent(self, new_parent: int) -> None:
        self.node_base_params.direct_parent_id = new_parent

    @property
    def properties(self) -> list[PropBundle]:
        return self.node_base_params.node_initial_params.prop_initial_values

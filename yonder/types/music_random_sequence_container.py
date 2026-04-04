from dataclasses import dataclass, field
from typing import ClassVar

from .structure import _HIRCNodeBody
from .rewwise_base_types import (
    MusicNodeParams,
    MusicTransNodeParams,
    PropBundle,
    Children,
)
from .mixins import PropertyMixin, ContainerMixin


@dataclass
class MusicRanSeqPlaylistItem:
    segment_id: int
    playlist_item_id: int = 0
    child_count: int = 0
    ers_type: int = 0
    loop_base: int = 0
    loop_min: int = 0
    loop_max: int = 0
    weight: int = 50
    avoid_repeat_count: int = 0
    use_weight: int = 0
    shuffle: int = 0


@dataclass
class MusicRandomSequenceContainer(PropertyMixin, ContainerMixin, _HIRCNodeBody):
    body_type: ClassVar[int] = 13
    music_node_params: MusicNodeParams = field(default_factory=MusicNodeParams)
    music_trans_node_params: MusicTransNodeParams = field(
        default_factory=MusicTransNodeParams
    )
    playlist_item_count: int = 0
    playlist_items: list[MusicRanSeqPlaylistItem] = field(default_factory=list)

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

from dataclasses import dataclass, field
from typing import ClassVar

from .structure import _HIRCNodeBody
from .rewwise_base_types import (
    MusicNodeParams,
    MusicTransNodeParams,
    GameSync,
    DecisionTreeNode,
    PropBundle,
)
from .rewwise_enums import GroupType, DecisionTreeMode
from .mixins.properties import PropertyMixin


@dataclass
class MusicSwitchContainer(PropertyMixin, _HIRCNodeBody):
    body_type: ClassVar[int] = 12
    music_node_params: MusicNodeParams = field(default_factory=MusicNodeParams)
    music_trans_node_params: MusicTransNodeParams = field(
        default_factory=MusicTransNodeParams
    )
    continue_playback: int = 0
    tree_depth: int = 0
    arguments: list[GameSync] = field(default_factory=list)
    group_types: list[GroupType] = field(default_factory=list)
    tree_size: int = 0
    tree_mode: DecisionTreeMode = DecisionTreeMode.BestMatch
    tree: DecisionTreeNode = field(
        default_factory=lambda: DecisionTreeNode(key=0, node_id=0, first_child_index=0)
    )

    @property
    def parent(self) -> int:
        return self.music_node_params.node_base_params.direct_parent_id

    @parent.setter
    def parent(self, new_parent: int) -> None:
        self.music_node_params.node_base_params.direct_parent_id = new_parent

    @property
    def children(self) -> list[int]:
        return self.music_node_params.children

    @property
    def properties(self) -> list[PropBundle]:
        return self.music_node_params.node_base_params.node_initial_params.prop_initial_values

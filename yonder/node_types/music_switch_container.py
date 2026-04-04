from dataclasses import dataclass, field
from typing import ClassVar

from .structure import _HIRCNodeBody
from .rewwise_base_types import MusicNodeParams, MusicTransNodeParams, GameSync, DecisionTreeNode
from .rewwise_enums import GroupType, DecisionTreeMode


@dataclass
class MusicSwitchContainer(_HIRCNodeBody):
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

    @property
    def children(self) -> list[int]:
        return self.music_node_params.children

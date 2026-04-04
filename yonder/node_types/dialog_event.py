from dataclasses import dataclass, field
from typing import ClassVar

from .structure import _HIRCNodeBody
from .rewwise_base_types import (
    GameSync,
    DecisionTreeNode,
    PropBundle,
    PropRangedModifiers,
)
from .rewwise_enums import DecisionTreeMode, GroupType


@dataclass
class DialogueEvent(_HIRCNodeBody):
    body_type: ClassVar[int] = 15
    probability: int = 100
    tree_depth: int = 0
    arguments: list[GameSync] = field(default_factory=list)
    group_types: list[GroupType] = field(default_factory=list)
    tree_size: int = 0
    tree_mode: DecisionTreeMode = DecisionTreeMode.BestMatch
    tree: DecisionTreeNode = field(
        default_factory=lambda: DecisionTreeNode(key=0, node_id=0, first_child_index=0)
    )
    prop_bundle: list[PropBundle] = field(default_factory=list)
    ranged_modifiers: PropRangedModifiers = field(default_factory=PropRangedModifiers)

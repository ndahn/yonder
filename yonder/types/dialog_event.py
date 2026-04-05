from dataclasses import dataclass, field
from typing import ClassVar

from .structure import _HIRCNodeBody, HIRCNode
from .rewwise_base_types import (
    GameSync,
    DecisionTreeNode,
    PropBundle,
    PropRangedModifiers,
)
from .rewwise_enums import DecisionTreeMode, GroupType, PropID
from .mixins import PropertyMixin


@dataclass
class DialogueEvent(PropertyMixin, _HIRCNodeBody):
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

    @classmethod
    def new(
        cls, nid: int | str, props: dict[PropID, float]
    ) -> "HIRCNode[DialogueEvent]":
        dlg = HIRCNode(nid, cls())

        if props:
            for prop, val in props.items():
                dlg.body.set_property(prop, val)

        return dlg

    @property
    def properties(self) -> list[PropBundle]:
        return self.prop_bundle

    # TODO add same management stuff as MusicSwitchContainer
    # TODO children should be kept in sync with the decision tree
    # (or be updated during validate)

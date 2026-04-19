from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar

from yonder.enums import PropID, SWITCH_GROUP_IDS
from yonder.util import logger
from .hirc_node import HIRCNode
from .base_types import (
    NodeBaseParams,
    Children,
    PropBundle,
    SwitchPackage,
    SwitchNodeParams,
    RTPC,
)
from .mixins import PropertyMixin


@dataclass(repr=False)
class SwitchContainer(PropertyMixin, HIRCNode):
    body_type: ClassVar[int] = 6
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    group_type: int = 0
    group_id: int = 0
    default_switch: int = 0
    continuous_validation: int = 0
    children: Children = field(default_factory=Children)
    switch_group_count: int = 0
    switch_groups: list[SwitchPackage] = field(default_factory=list)
    switch_param_count: int = 0
    switch_params: list[SwitchNodeParams] = field(default_factory=list)

    @classmethod
    def new(
        cls,
        nid: int | str,
        switch_groups: list[list[int]],
        props: dict[PropID, float] = None,
        parent: int | HIRCNode = 0,
    ) -> SwitchContainer:
        obj = cls(nid)

        if switch_groups:
            for idx, nodes in enumerate(switch_groups):
                obj.switch_groups.append(
                    SwitchPackage(
                        switch_id=SWITCH_GROUP_IDS[idx],
                        nodes=nodes,
                    )
                )

        if props:
            for prop, val in props.items():
                obj.set_property(prop, val)

        obj.parent = parent
        return obj

    @property
    def parent(self) -> int:
        return self.node_base_params.direct_parent_id

    @parent.setter
    def parent(self, new_parent: int | HIRCNode) -> None:
        if isinstance(new_parent, HIRCNode):
            new_parent = new_parent.id
        self.node_base_params.direct_parent_id = new_parent

    @property
    def properties(self) -> list[PropBundle]:
        return self.node_base_params.node_initial_params.prop_initial_values

    @property
    def rtpcs(self) -> list[RTPC]:
        return self.node_base_params.initial_rtpc.rtpcs

    def attach(self, other: int | HIRCNode) -> None:
        if isinstance(other, HIRCNode):
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

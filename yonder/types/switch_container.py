from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar
from field_properties import field_property

from .structure import HIRCNode
from .base_types import (
    NodeBaseParams,
    Children,
    PropBundle,
    SwitchPackage,
    SwitchNodeParams,
)
from yonder.enums import PropID, SWITCH_GROUP_IDS
from .mixins import PropertyMixin


@dataclass(slots=True)
class SwitchContainer(PropertyMixin, HIRCNode):
    body_type: ClassVar[int] = 6
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    group_type: int = 0
    group_id: int = 0
    default_switch: int = 0
    continuous_validation: int = 0
    children: Children = field(default_factory=Children)
    switch_group_count: int = field_property(default=0)
    switch_groups: list[SwitchPackage] = field(default_factory=list)
    switch_param_count: int = field_property(default=0)
    switch_params: list[SwitchNodeParams] = field(default_factory=list)

    @classmethod
    def new(
        cls,
        nid: int | str,
        switch_groups: list[list[int]],
        props: dict[PropID, float] = None,
        parent: int = 0,
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

    @property
    def properties(self) -> list[PropBundle]:
        return self.node_base_params.node_initial_params.prop_initial_values

    @field_property(switch_group_count)
    def get_switch_group_count(self) -> int:
        return len(self.switch_groups)

    @field_property(switch_param_count)
    def get_switch_param_count(self) -> int:
        return len(self.switch_params)

    # TODO sync up children with switch groups/params

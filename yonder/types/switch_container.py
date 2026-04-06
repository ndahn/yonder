from dataclasses import dataclass, field
from typing import ClassVar
from field_properties import field_property

from .structure import HIRCNode
from .rewwise_base_types import NodeBaseParams, Children, PropBundle
from yonder.enums import PropID, SWITCH_GROUP_IDS
from .mixins import PropertyMixin


@dataclass
class SwitchPackage:
    switch_id: int
    node_count: int = field_property(init=False, raw=True)
    nodes: list[int] = field(default_factory=list)

    @field_property(node_count)
    def get_node_count(self) -> int:
        return len(self.nodes)

    def get_references(self) -> list[tuple[str, int]]:
        return [(f"nodes:{i}", nid) for i, nid in enumerate(self.nodes)]


@dataclass
class SwitchNodeParams:
    node_id: int
    unk1: bool = False
    unk2: bool = False
    unk3: bool = False
    unk4: bool = False
    unk5: bool = False
    unk6: bool = False
    continue_playback: bool = False
    is_first_only: bool = False
    unk9: bool = False
    unk10: bool = False
    unk11: bool = False
    unk12: bool = False
    unk13: bool = False
    unk14: bool = False
    unk15: bool = False
    unk16: bool = False
    fade_out_time: int = 0
    fade_in_time: int = 0

    def get_references(self) -> list[tuple[str, int]]:
        return [("node_id", self.node_id)]


@dataclass
class SwitchContainer(PropertyMixin, HIRCNode):
    body_type: ClassVar[int] = 6
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    group_type: int = 0
    group_id: int = 0
    default_switch: int = 0
    continuous_validation: int = 0
    children: Children = field(default_factory=Children)
    switch_group_count: int = field_property(init=False, raw=True)
    switch_groups: list[SwitchPackage] = field(default_factory=list)
    switch_param_count: int = field_property(init=False, raw=True)
    switch_params: list[SwitchNodeParams] = field(default_factory=list)

    @classmethod
    def new(
        cls,
        nid: int | str,
        switch_groups: list[list[int]],
        props: dict[PropID, float] = None,
        parent: int = 0,
    ) -> "SwitchContainer":
        super().__init__(nid)
        obj = cls()

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

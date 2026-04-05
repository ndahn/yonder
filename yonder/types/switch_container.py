from dataclasses import dataclass, field
from typing import ClassVar
from field_properties import field_property

from .structure import _HIRCNodeBody, HIRCNode
from .rewwise_base_types import NodeBaseParams, Children, PropBundle
from yonder.enums import PropID
from .mixins import PropertyMixin, ContainerMixin


# Seems to be a fixed sequence, probably hashes
switch_group_ids = [
    3542429633,
    2515591576,
    866585565,
    847446114,
    1150349822,
    1902202008,
    483902209,
    1441934824,
    514904032,
    56759204,
    3126989719,
    1489354423,
    3905525753,
    1971625096,
    3637915147,
    1616602882,
    3894496501,
    3481581068,
    2271924278,
    1004196637,
    1442528243,
    4013339729,
    2796307820,
    613742101,
    525485163,
    4192883481,
    1292925647,
    518062628,
    1025216116,
    1568474447,
    2596938600,
    4206702229,
    3559404471,
    1784841708,
    3765513826,
    2037129417,
    4272577682,
    2135765449,
    2599511129,
    2613716188,
    2613716189,
    2613716190,
    1538950451,
    2078827875,
    1575902214,
    1476027921,
    4236723293,
    1933317553,
    4053036951,
    4017163688,
    2004483904,
    4019004407,
    412461880,
    2108245638,
    1945499476,
    2862950052,
    1836395786,
    1888528824,
    1462887001,
    33890273,
    1563051363,
    909606183,
    3977549511,
    1508413002,
    16109090,
    2003766585,
    2522610764,
    473615746,
    3159832036,
    4184793337,
    2418102691,
    3331638571,
    1605139770,
    520439139,
    3225389263,
    447954687,
    3692604948,
    3779067511,
    2426704050,
    1922044877,
    3079245127,
    3787844203,
    2653478244,
    3991679221,
    532698448,
    32379660,
    1454810063,
    1257305533,
    1089779977,
    2115764262,
    1323658502,
    3336129037,
    2814860561,
    2081655754,
    3005002201,
    4125122048,
    518912088,
    4068273420,
    1089688443,
    1431954419,
    3956179598,
    2326066381,
    437457885,
    1695064557,
    567805169,
    4002554925,
    24264894,
    1993718132,
    1575440872,
    4271758898,
    997184810,
    1291441777,
    597197681,
    1012311631,
    940968422,
]


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
class SwitchContainer(PropertyMixin, ContainerMixin, _HIRCNodeBody):
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
    ) -> "HIRCNode[SwitchContainer]":
        obj = HIRCNode(nid, cls())

        if switch_groups:
            for idx, nodes in enumerate(switch_groups):
                obj.body.switch_groups.append(
                    SwitchPackage(
                        switch_id=switch_group_ids[idx],
                        nodes=nodes,
                    )
                )

        if props:
            for prop, val in props.items():
                obj.body.set_property(prop, val)

        obj.body.parent = parent
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

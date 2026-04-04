from dataclasses import dataclass, field
from typing import ClassVar

from .soundbank import _HIRCNodeBody
from .rewwise_base_types import NodeBaseParams, Children


@dataclass
class SwitchPackage:
    switch_id: int
    node_count: int = 0
    nodes: list[int] = field(default_factory=list)


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


@dataclass
class SwitchContainer(_HIRCNodeBody):
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

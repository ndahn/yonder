from __future__ import annotations
from typing import Union
from dataclasses import dataclass, field

from .object_id import ObjectId
from .rewwise_base_types import (
    IAkPlugin,
    ConversionTable,
    StateGroup,
    SwitchGroup,
    RTPCRamping,
    AkAcousticTexture,
    AkStateTransition,
)
from .rewwise_nodes import AkNodeType as HIRCObjectBody


@dataclass
class ENVSSection:
    conversion_table: ConversionTable = field(default_factory=ConversionTable)


@dataclass
class BKHDSection:
    version: int
    bank_id: int
    language_fnv_hash: int = 0
    wem_alignment: int = 0
    project_id: int = 0
    padding: list[int] = field(default_factory=list)


@dataclass
class INITSection:
    plugin_count: int = 0
    plugins: list[IAkPlugin] = field(default_factory=list)


@dataclass
class DIDXSection:
    descriptors: list[DIDXDescriptor] = field(default_factory=list)


@dataclass
class DIDXDescriptor:
    id: int
    offset: int
    size: int


@dataclass
class DATASection:
    data: list[int] = field(default_factory=list)


@dataclass
class PLATSection:
    string_length: int = 0
    string: str = ""


@dataclass
class TodoSection:
    data: list[int] = field(default_factory=list)


@dataclass
class STIDSection:
    string_encoding: int = 0
    entry_count: int = 0
    entries: list[STIDSectionEntry] = field(default_factory=list)


@dataclass
class STIDSectionEntry:
    bnk_id: int
    name_length: int = 0
    name: list[int] = field(default_factory=list)

    string_encoding: int = 0
    entry_count: int = 0
    entries: list[STIDSectionEntry] = field(default_factory=list)


@dataclass
class STMGSection:
    volume_threshold: float
    max_voice_instances: int
    max_num_dangerous_virt_voices_limit_internal: int = 0
    state_group_count: int = 0
    state_groups: list[StateGroup] = field(default_factory=list)
    switch_group_count: int = 0
    switch_groups: list[SwitchGroup] = field(default_factory=list)
    ramping_param_count: int = 0
    ramping_params: list[RTPCRamping] = field(default_factory=list)
    texture_count: int = 0
    textures: list[AkAcousticTexture] = field(default_factory=list)


@dataclass
class STMGSectionStateGroup:
    id: int
    default_transition_time: int = 0
    state_transition_count: int = 0
    state_transitions: list[AkStateTransition] = field(default_factory=list)


@dataclass
class HIRCObject:
    id: ObjectId
    body: HIRCObjectBody
    size: int = 0

    @property
    def body_type(self) -> int:
        return type(self.body).body_type


@dataclass
class HIRCSection:
    object_count: int = 0
    objects: list[HIRCObject] = field(default_factory=list)


SectionBody = Union[
    BKHDSection,
    DIDXSection,
    DATASection,
    ENVSSection,
    TodoSection,
    HIRCSection,
    STIDSection,
    STMGSection,
    INITSection,
    PLATSection,
]


@dataclass
class Section:
    magic: list[int]
    size: int = 0
    body: SectionBody


@dataclass
class Soundbank:
    sections: list[Section] = field(default_factory=list)

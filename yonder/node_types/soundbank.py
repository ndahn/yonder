from __future__ import annotations
from typing import Union
from dataclasses import dataclass, field

from .rewwise_base_types import (
    IAkPlugin,
    ConversionTable,
    StateGroup,
    SwitchGroup,
    RTPCRamping,
    AcousticTexture,
    StateTransition,
)
from .rewwise_parse import serialize, deserialize
from .object_id import ObjectId


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
    textures: list[AcousticTexture] = field(default_factory=list)


@dataclass
class STMGSectionStateGroup:
    id: int
    default_transition_time: int = 0
    state_transition_count: int = 0
    state_transitions: list[StateTransition] = field(default_factory=list)


@dataclass
class HIRCSection:
    object_count: int = 0
    objects: list[HIRCNode] = field(default_factory=list)


@dataclass
class _HIRCNodeBody:
    def to_dict(self) -> dict:
        # rewwise inserts the class name of the node type into the hierarchy
        # (e.g. body: {Sound: ...})
        return {type(self).__name__: serialize(self)}

    @classmethod
    def from_dict(cls, data: dict) -> "_HIRCNodeBody":
        for sub in cls.__subclasses__():
            if sub.__name__ in data:
                return deserialize(sub, data[sub.__name__])

        raise ValueError(f"Not a valid _HIRCNodeBody: {data}")


@dataclass
class HIRCNode:
    id: ObjectId
    body: _HIRCNodeBody

    @property
    def type_id(self) -> int:
        return type(self.body).body_type

    @property
    def type_name(self) -> str:
        return type(self.body).__name__

    def to_dict(self) -> dict:
        ser = serialize(self)
        ser.update(
            {
                # These two are just here to make rewwise happy
                "body_type": self.type_id,
                "size": 0,
            }
        )
        return ser


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


NODE_TYPE_MAP = {cls.body_type: cls for cls in _HIRCNodeBody.__subclasses__()}


@dataclass
class Section:
    magic: list[int]
    size: int = 0
    body: SectionBody


@dataclass
class Soundbank:
    sections: list[Section] = field(default_factory=list)

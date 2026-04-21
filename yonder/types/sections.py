from __future__ import annotations
from typing import Any
from dataclasses import dataclass, field
import json

from yonder.hash import calc_hash, lookup_name
from .base_types import (
    IAkPlugin,
    ObsConversionTable,
    StateGroup,
    SwitchGroup,
    RTPCRamping,
    AcousticTexture,
    StateTransition,
)
from .hirc_node import HIRCNode
from .mixins import DataNode
from .serialization import _serialize_value, _deserialize_fields


# NOTE IMPORTANT NOTE
# Don't use slots on dataclasses participating in inheritance, it breaks
# serialization in subtle ways like duplicate class definitions.


@dataclass(slots=True)
class SectionHeader:
    magic: list[int] = field(default_factory=list)
    size: int = 0


@dataclass
class Section(DataNode):
    _header: SectionHeader = field(default_factory=SectionHeader)

    @property
    def name(self) -> str:
        return type(self).__name__[:4].upper()

    def to_dict(self) -> dict:
        data = _serialize_value(self)
        trans = {
            **data.pop("_header"),
            "body": {
                self.name: {**data},
            },
        }
        return trans

    @classmethod
    def from_dict(cls, data: dict) -> Section:
        section_type = next(iter(data["body"].keys()))
        header = {
            "magic": data.pop("magic"),
            "size": data.pop("size"),
        }
        trans = {
            "_header": header,
            **data["body"][section_type],
        }

        if cls.__name__.startswith(section_type):
            return _deserialize_fields(cls, trans)

        for sub in cls.__subclasses__():
            if sub.__name__.upper().startswith(section_type):
                return _deserialize_fields(sub, trans)

        raise ValueError(f"Unknown section type {section_type}")


@dataclass
class BKHDSection(Section):
    version: int = 0
    bank_id: int = 0
    language_fnv_hash: int = 0
    wem_alignment: int = 0
    project_id: int = 0
    padding: list[int] = field(default_factory=list)

    @property
    def bank_name(self) -> str:
        return lookup_name(self.bank_id)

    @bank_name.setter
    def bank_name(self, name: str) -> None:
        self.bank_id = calc_hash(name)

    def get_bank_name(self, default: Any = None) -> str:
        name = self.bank_name
        return name if name else default


@dataclass
class DATASection(Section):
    data: list[int] = field(default_factory=list)


@dataclass(slots=True)
class DIDXDescriptor:
    id: int = 0
    offset: int = 0
    size: int = 0


@dataclass
class DIDXSection(Section):
    descriptors: list[DIDXDescriptor] = field(default_factory=list)


@dataclass
class ENVSSection(Section):
    conversion_table: ObsConversionTable = field(default_factory=ObsConversionTable)


@dataclass
class HIRCSection(Section):
    object_count: int = 0
    objects: list[HIRCNode] = field(default_factory=list)

    def json_short(self) -> str:
        data = self.to_dict()
        data["body"]["HIRC"]["objects"] = "<skipped>"
        return json.dumps(data, indent=2)


@dataclass
class INITSection(Section):
    plugin_count: int = 0
    plugins: list[IAkPlugin] = field(default_factory=list)


@dataclass
class PLATSection(Section):
    string_length: int = 0
    string: str = ""


@dataclass(slots=True)
class STIDSectionEntry:
    bnk_id: int = 0
    name_length: int = 0
    name: str = field(default_factory=list)


@dataclass
class STIDSection(Section):
    string_encoding: int = 0
    entry_count: int = 0
    entries: list[STIDSectionEntry] = field(default_factory=list)


@dataclass(slots=True)
class STMGSectionStateGroup:
    id: int = 0
    default_transition_time: int = 0
    state_transition_count: int = 0
    state_transitions: list[StateTransition] = field(default_factory=list)


@dataclass
class STMGSection(Section):
    volume_threshold: float = 0.0
    max_voice_instances: int = 1
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
class TodoSection(Section):
    data: list[int] = field(default_factory=list)

from __future__ import annotations
from dataclasses import dataclass, field

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
from .serialization import _serialize_value, _deserialize_fields


# NOTE IMPORTANT NOTE
# Don't use slots on dataclasses participating in inheritance, it breaks
# serialization in subtle ways like duplicate class definitions.


@dataclass(slots=True)
class SectionHeader:
    magic: list[int] = field(default_factory=list)
    size: int = 0


@dataclass
class Section():
    _header: SectionHeader = field(default_factory=SectionHeader)

    @classmethod
    def section_name(cls) -> str:
        return cls.__name__[:4].upper()

    def to_dict(self) -> dict:
        data = _serialize_value(self)
        trans = {
            **data.pop("_header"),
            "body": {
                self.section_name(): {**data},
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

        for sub in cls.__subclasses__():
            if sub.section_name() == section_type:
                return _deserialize_fields(sub, trans)

        raise ValueError(f"Unknown section type {section_type}")


@dataclass
class ENVSSection(Section):
    conversion_table: ObsConversionTable = field(default_factory=ObsConversionTable)


@dataclass
class BKHDSection(Section):
    version: int = 0
    bank_id: int = 0
    language_fnv_hash: int = 0
    wem_alignment: int = 0
    project_id: int = 0
    padding: list[int] = field(default_factory=list)

    @property
    def name(self) -> str:
        return lookup_name(self.bank_id)

    def set_name(self, new_name: str) -> None:
        self.bank_id = calc_hash(new_name)

    def get_name(self, default: str = None) -> str:
        name = self._bank_id.name
        if name:
            return name
        return default


@dataclass
class INITSection(Section):
    plugin_count: int = 0
    plugins: list[IAkPlugin] = field(default_factory=list)


@dataclass(slots=True)
class DIDXDescriptor:
    id: int = 0
    offset: int = 0
    size: int = 0


@dataclass
class DIDXSection(Section):
    descriptors: list[DIDXDescriptor] = field(default_factory=list)


@dataclass
class DATASection(Section):
    data: list[int] = field(default_factory=list)


@dataclass
class PLATSection(Section):
    string_length: int = 0
    string: str = ""


@dataclass
class TodoSection(Section):
    data: list[int] = field(default_factory=list)


@dataclass(slots=True)
class STIDSectionEntry:
    bnk_id: int = 0
    name_length: int = 0
    name: list[int] = field(default_factory=list)


@dataclass
class STIDSection(Section):
    string_encoding: int = 0
    entry_count: int = 0
    entries: list[STIDSectionEntry] = field(default_factory=list)


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
class HIRCSection(Section):
    object_count: int = 0
    objects: list[HIRCNode] = field(default_factory=list)


@dataclass(slots=True)
class STMGSectionStateGroup:
    id: int = 0
    default_transition_time: int = 0
    state_transition_count: int = 0
    state_transitions: list[StateTransition] = field(default_factory=list)


NODE_TYPE_MAP = {cls.body_type: cls for cls in HIRCNode.__subclasses__()}

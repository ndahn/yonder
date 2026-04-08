from __future__ import annotations
from typing import Any, ClassVar
from abc import ABCMeta
from dataclasses import dataclass, field, fields, is_dataclass, InitVar
from copy import deepcopy
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
from .serialization import _serialize_value, _deserialize_fields
from .object_id import ObjectId


# NOTE IMPORTANT NOTE
# Don't use slots on dataclasses participating in inheritance, it breaks
# serialization in subtle ways like duplicate class definitions.


@dataclass(slots=True)
class SectionHeader:
    magic: list[int] = field(default_factory=list)
    size: int = 0


@dataclass
class Section(metaclass=ABCMeta):
    _header: SectionHeader = field(default_factory=SectionHeader)

    @classmethod
    def section_name(cls) -> str:
        return cls.__name__[:4].upper()

    def to_dict(self) -> dict:
        data = _serialize_value(self)
        trans = {
            **data.pop("_header"),
            "body": {
                type(self).__name__: {**data},
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


@dataclass(slots=True)
class HIRCNodeHeader:
    # These two are just here to make rewwise happy
    body_type: int = 0
    size: int = 0
    id: ObjectId = None

    def to_dict(self) -> dict:
        ser = _serialize_value(self)
        ser.pop("_id", None)
        ser["id"] = self.id.to_dict()
        return ser

    @classmethod
    def from_dict(cls, data: dict) -> HIRCNode:
        return _deserialize_fields(cls, data)


@dataclass
class HIRCNode(metaclass=ABCMeta):
    # Expected to be set on class definition
    body_type: ClassVar[int] = 0
    id: InitVar[int]
    _header: HIRCNodeHeader = field(default_factory=HIRCNodeHeader)

    @property
    def id(self) -> int:
        return self._header.id.hash

    @id.setter
    def id(self, new_id: int) -> None:
        self._header.id.hash = new_id

    @property
    def name(self) -> str:
        return self._header.id.name

    @name.setter
    def name(self, new_name: str) -> None:
        self._header.id.name = new_name

    @property
    def type_name(self) -> str:
        return type(self).__name__

    def get_name(self, default: str = None) -> str:
        return self._header.id.get_name(default)

    def json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def copy(self) -> HIRCNode:
        return deepcopy(self)

    def glob(self, pattern: str) -> list:
        segments = pattern.split("/")

        def match(node: dataclass, segs: list[str]):
            if not segs:
                yield node
                return

            seg, rest = segs[0], segs[1:]
            if not is_dataclass(node):
                return

            if seg == "**":
                yield from match(node, rest)
                for field in fields(node):
                    yield from match(getattr(node, field.name), segs)
            elif seg == "*":
                for field in fields(node):
                    yield from match(getattr(node, field.name), rest)
            elif hasattr(node, seg):
                yield from match(getattr(node, seg), rest)

        return list(match(self, segments))

    def to_dict(self) -> dict:
        # rewwise inserts the class name of the node type into the hierarchy
        # (e.g. body: {Sound: ...})
        data = _serialize_value(self)
        return {
            **data.pop("_header"),
            "body": {
                self.type_name: {**data},
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> HIRCNode:
        node_type = next(iter(data["body"].keys()))
        header = {
            "body_type": data.pop("body_type"),
            "size": data.pop("size"),
            "id": data.pop("id"),
        }

        # It's much more convenient to store all the header data in a nested dataclass
        # and keep the actual node params at root level, so we have to massage the data
        # rewwise spits out a little bit
        trans = {
            "_header": header,
            **data["body"][node_type],
        }

        for sub in cls.__subclasses__():
            if sub.__name__ == node_type:
                return _deserialize_fields(sub, trans)

        raise ValueError(f"Unknown node type {node_type}")

    def get_references(self) -> list[tuple[str, int]]:
        def delve(obj: Any, path: str = "") -> list[tuple[str, int]]:
            ret = []

            # Use get_references() only on objects other than self
            if (
                obj is not self
                and hasattr(obj, "get_references")
                and callable(obj.get_references)
            ):
                for key, val in obj.get_references():
                    if isinstance(val, int) and val > 0:
                        ret.append((f"{path}/{key}", val))

                # get_references() already handled this object's subtree
                return ret

            if is_dataclass(obj):
                for f in fields(obj):
                    ret.extend(delve(getattr(obj, f.name), f"{path}/{f.name}"))
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    ret.extend(delve(item, f"{path}:{i}"))
            elif isinstance(obj, dict):
                for key, val in obj.items():
                    ret.extend(delve(val, f"{path}/{key}"))

            return ret

        return delve(self)

    def __hash__(self) -> int:
        return self.id

    def __lt__(self, other: HIRCNode) -> bool:
        return self.id < other.id

    def __str__(self) -> str:
        if self.name:
            return self.name
        return f"{self.type_name} #{self.id}"


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

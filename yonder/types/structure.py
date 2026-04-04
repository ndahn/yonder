from __future__ import annotations
from typing import Any, Union, ClassVar, Generic, TypeVar
from dataclasses import dataclass, field, fields, is_dataclass, replace
import json

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
    _bank_id: ObjectId
    language_fnv_hash: int = 0
    wem_alignment: int = 0
    project_id: int = 0
    padding: list[int] = field(default_factory=list)

    @property
    def bank_id(self) -> int:
        return self._bank_id.hash

    @bank_id.setter
    def bank_id(self, new_id: int) -> None:
        self._bank_id.hash = new_id

    @property
    def name(self) -> str:
        return self._bank_id.name

    @name.setter
    def name(self, new_name: str) -> None:
        self._bank_id.name = new_name

    def get_name(self, default: str = None) -> str:
        name = self._bank_id.name
        if name:
            return name
        return default


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
    body_type: ClassVar[int] = 0

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

    def get_references(self) -> list[tuple[str, int]]:
        def delve(obj: Any, path: str = "") -> list[tuple[str, int]]:
            ret = []

            if hasattr(obj, "get_references") and callable(obj.get_references):
                for key, val in obj.get_references():
                    if isinstance(val, int) and val > 0:
                        ret.extend((f"{path}/{key}", val))
            
            if is_dataclass(obj):
                for f in fields(obj):
                    ret.extend(delve(f, f"{path}/{f.name}"))

            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    ret.extend(delve(item, f"{path}:{i}"))

            elif isinstance(obj, dict):
                for key, val in obj.items():
                    ret.extend(delve(item, f"{path}/{key}"))

            return ret

        return delve(self)


_BodyType = TypeVar("_BodyType", bound=_HIRCNodeBody)


@dataclass
class HIRCNode(Generic[_BodyType]):
    _id: ObjectId
    body: _BodyType

    def __init__(self, id: int | str, body: _BodyType):
        self._id = ObjectId(id)
        self.body = body

    @property
    def id(self) -> int:
        return self._id.hash

    @id.setter
    def id(self, new_id: int) -> None:
        self._id.hash = new_id

    @property
    def name(self) -> str:
        return self._id.name

    @name.setter
    def name(self, new_name: str) -> None:
        self._id.name = new_name

    def get_name(self, default: str = None) -> str:
        return self._id.get_name(default)

    @property
    def type_id(self) -> int:
        return type(self.body).body_type

    @property
    def type_name(self) -> str:
        return type(self.body).__name__

    def json(self) -> str:
        return json.dumps(self.to_dict())

    def apply(self, data: dict) -> str:
        def apply_dict(obj, data: dict):
            for f in fields(obj):
                if f.name not in data:
                    continue

                value = data[f.name]
                current = getattr(obj, f.name)

                if is_dataclass(current):
                    apply_dict(current, value)
                elif isinstance(current, dict):
                    current.clear()
                    current.update(value)
                elif isinstance(current, list):
                    current.clear()
                    current.extend(value)
                else:
                    setattr(obj, f.name, value)

        return apply_dict(self.body, data)

    def to_dict(self) -> dict:
        ser = serialize(self)
        ser.pop("_id", None)
        ser.update(
            {
                "id": self._id.to_dict(),
                # These two are just here to make rewwise happy
                "body_type": self.type_id,
                "size": 0,
            }
        )
        return ser

    @classmethod
    def from_dict(cls, data: dict) -> "HIRCNode":
        data["_id"] = data.pop("id")
        return deserialize(cls, data)

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

        return list(match(self.body, segments))

    def get_references(self) -> list[tuple[str, int]]:
        # For convenience
        return self.body.get_references()

    def __hash__(self) -> int:
        return self.id

    def __str__(self) -> str:
        return f"{self.type_name} #{self.id}"


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


NODE_TYPE_MAP = {cls.body_type: cls for cls in _HIRCNodeBody.__subclasses__()}

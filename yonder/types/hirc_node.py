from __future__ import annotations
from typing import Any, ClassVar
from abc import ABCMeta
from dataclasses import dataclass, field, fields, is_dataclass, InitVar
from copy import deepcopy
import json

from .serialization import _serialize_value, _deserialize_fields
from .object_id import ObjectId


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

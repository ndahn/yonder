from __future__ import annotations
from dataclasses import dataclass, field, InitVar
from typing import Any

from .hirc_node import HIRCNode
from .serialization import _serialize_value


@dataclass(repr=False, eq=False)
class UnknownObject(HIRCNode):
    body_type: int = 0
    id: InitVar[int]
    node_type: str = None
    data: dict[str, Any] | str = field(default_factory=dict)

    def __post_init__(self, id: int):
        return super().__post_init__(id)
    
    @property
    def type_name(self) -> str:
        return self.node_type

    @classmethod
    def from_dict(cls, data: dict, node_type: str) -> UnknownObject:
        # Should only ever be called from HIRCNode
        body_type = data.pop("_header")["body_type"]
        oid = data.pop("id")
        return UnknownObject(body_type, oid, node_type, data)

    def to_dict(self) -> dict:
        # rewwise inserts the class name of the node type into the hierarchy
        # (e.g. body: {Sound: ...})
        data = _serialize_value(self)
        header = data["_header"]
        actual_data = data["data"]

        trans = {
            **header,
            "body": {
                self.node_type: actual_data,
            },
        }
        return trans

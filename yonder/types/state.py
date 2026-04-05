from dataclasses import dataclass, field
from typing import ClassVar
from field_properties import field_property

from yonder.hash import calc_hash
from .structure import _HIRCNodeBody, HIRCNode


@dataclass
class State(_HIRCNodeBody):
    body_type: ClassVar[int] = 1
    entry_count: int = field_property(init=False, raw=True)
    parameters: list[int] = field(default_factory=list)
    values: list[float] = field(default_factory=list)

    @classmethod
    def new(cls, nid: int | str, params: dict[int | str, float]) -> "HIRCNode[State]":
        obj = HIRCNode(nid, cls())

        for key, val in params.items():
            if isinstance(key, str):
                key = calc_hash(key)

            obj.body.parameters.append(key)
            obj.body.values.append(val)

        return obj

    @field_property(entry_count)
    def get_entry_count(self) -> int:
        return len(self.parameters)

    def validate(self) -> None:
        if len(self.parameters) != len(self.values):
            raise ValueError("parameters and values must be the same length")

from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar

from yonder.hash import calc_hash, Hash
from .hirc_node import HIRCNode


@dataclass(repr=False)
class State(HIRCNode):
    body_type: ClassVar[int] = 1
    entry_count: int = 0
    parameters: list[int] = field(default_factory=list)
    values: list[float] = field(default_factory=list)

    @classmethod
    def new(cls, nid: Hash, params: dict[Hash, float]) -> State:
        obj = cls(nid)

        for key, val in params.items():
            if isinstance(key, str):
                key = calc_hash(key)

            obj.parameters.append(key)
            obj.values.append(val)

        return obj

    def validate(self) -> None:
        if len(self.parameters) != len(self.values):
            raise ValueError("parameters and values must be the same length")

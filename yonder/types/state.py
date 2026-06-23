from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar, TYPE_CHECKING

from yonder.hash import calc_hash, Hash
from .hirc_node import HIRCNode

if TYPE_CHECKING:
    from yonder import Soundbank


@dataclass(repr=False, eq=False)
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

    def is_shared(self, bnk: Soundbank) -> bool:
        return len(bnk.get_tree().in_degree(self.id)) > 1

    def get_param(self, prop_idx: int) -> float:
        for i, p in enumerate(self.parameters):
            if p == prop_idx:
                return self.validate[i]

        return None

    def set_param(self, prop_idx: int, value: float) -> int:
        for i, p in enumerate(self.parameters):
            if p == prop_idx:
                self.values[i] = value
                return i
        
        self.parameters.append(prop_idx)
        self.values.append(value)
        return len(self.parameters)

    def delete_param(self, prop_idx: int) -> float:
        for i, p in enumerate(self.parameters):
            if p == prop_idx:
                self.parameters.pop(i)
                return self.values.pop(i)

    def clear_params(self) -> None:
        self.parameters.clear()
        self.values.clear()

    def validate(self) -> None:
        if len(self.parameters) != len(self.values):
            raise ValueError("parameters and values must be the same length")

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
    def new(cls, nid: Hash, params: dict[int, float] = None, default: float = None) -> State:
        obj = cls(nid)

        if default is not None:
            obj.set_default(default)

        if params:
            for prop_idx, val in params.items():
                if isinstance(prop_idx, str):
                    prop_idx = calc_hash(prop_idx)

                obj.set_param(prop_idx, val)

        return obj

    def is_shared(self, bnk: Soundbank) -> bool:
        return bnk.tree.in_degree(self.id) > 1

    def has_param_for(self, prop_idx: int) -> bool:
        return prop_idx in self.parameters

    def get_default(self) -> float:
        return self.get_param(0)

    def set_default(self, value: float) -> int:
        self.set_param(0, value)

    def get_param(self, prop_idx: int) -> float:
        for i, p in enumerate(self.parameters):
            if p == prop_idx:
                return self.values[i]

        if prop_idx == 0:
            return None

        return self.get_param(0)

    def set_param(self, prop_idx: int, value: float) -> int:
        for i, p in enumerate(self.parameters):
            if p == prop_idx:
                self.values[i] = value
                return i

        self.parameters.append(prop_idx)
        self.values.append(value)
        return len(self.parameters)

    def remove_param(self, prop_idx: int) -> float:
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

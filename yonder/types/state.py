from dataclasses import dataclass, field
from typing import ClassVar

from yonder.hash import calc_hash
from .structure import _HIRCNodeBody, HIRCNode


@dataclass
class State(_HIRCNodeBody):
    body_type: ClassVar[int] = 1
    entry_count: int = 0
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

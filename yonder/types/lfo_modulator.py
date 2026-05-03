from __future__ import annotations
from dataclasses import dataclass
from typing import ClassVar

from yonder.hash import Hash
from .hirc_node import HIRCNode


@dataclass(repr=False, eq=False)
class LFOModulator(HIRCNode):
    body_type: ClassVar[int] = 19
    data: str = ""

    @classmethod
    def new(cls, nid: Hash) -> LFOModulator:
        return cls(nid)

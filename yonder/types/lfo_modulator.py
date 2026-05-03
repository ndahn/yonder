from __future__ import annotations
from dataclasses import dataclass
from typing import ClassVar

from yonder.hash import Hash
from .hirc_node import HIRCNode


@dataclass(repr=False, eq=False)
class LFOModulator(HIRCNode):
    body_type: ClassVar[int] = 19
    # TODO figure this out once rewwise does
    # https://www.audiokinetic.com/en/public-library/2025.1.7_9143/?source=Help&id=working_with_lfos
    data: str = ""

    @classmethod
    def new(cls, nid: Hash) -> LFOModulator:
        return cls(nid)

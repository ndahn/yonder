from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar

from yonder.hash import Hash
from yonder.enums import PropID
from .hirc_node import HIRCNode
from .base_types import PropBundle, PropRangedModifiers, InitialRTPC, RTPC


@dataclass(repr=False, eq=False)
class TimeModulator(HIRCNode):
    body_type: ClassVar[int] = 22
    prop_bundle: list[PropBundle] = field(default_factory=list)
    ranged_modifiers: PropRangedModifiers = field(default_factory=PropRangedModifiers)
    initial_rtpc: InitialRTPC = field(default_factory=InitialRTPC)

    @classmethod
    def new(
        cls,
        nid: Hash,
        props: dict[PropID, float] = None,
    ) -> TimeModulator:
        obj = cls(nid)

        if props:
            for prop, val in props.items():
                obj.set_property(prop, val)

        return obj

    @property
    def rtpcs(self) -> list[RTPC]:
        return self.initial_rtpc.rtpcs

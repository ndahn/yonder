from dataclasses import dataclass, field
from typing import ClassVar

from .structure import _HIRCNodeBody, HIRCNode
from .rewwise_base_types import PropBundle, PropRangedModifiers, InitialRTPC
from yonder.enums import PropID


@dataclass
class TimeModulator(_HIRCNodeBody):
    body_type: ClassVar[int] = 22
    prop_bundle: list[PropBundle] = field(default_factory=list)
    ranged_modifiers: PropRangedModifiers = field(default_factory=PropRangedModifiers)
    initial_rtpc: InitialRTPC = field(default_factory=InitialRTPC)

    @classmethod
    def new(
        cls,
        nid: int | str,
        props: dict[PropID, float] = None,
    ) -> "HIRCNode[TimeModulator]":
        obj = HIRCNode(nid, cls)

        if props:
            for prop, val in props.items():
                obj.body.set_property(prop, val)

        return obj

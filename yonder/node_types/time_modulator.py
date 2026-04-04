from dataclasses import dataclass, field
from typing import ClassVar

from .soundbank import _HIRCNodeBody
from .rewwise_base_types import PropBundle, PropRangedModifiers, InitialRTPC


@dataclass
class TimeModulator(_HIRCNodeBody):
    body_type: ClassVar[int] = 22
    prop_bundle: list[PropBundle] = field(default_factory=list)
    ranged_modifiers: PropRangedModifiers = field(default_factory=PropRangedModifiers)
    initial_rtpc: InitialRTPC = field(default_factory=InitialRTPC)

from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar

from .hirc_node import HIRCNode
from .base_types import FxBaseInitialValues


@dataclass
class EffectCustom(HIRCNode):
    body_type: ClassVar[int] = 17
    fx_base_initial_values: FxBaseInitialValues = field(
        default_factory=lambda: FxBaseInitialValues(fx_id=0)
    )

    @classmethod
    def new(cls, nid: int | str) -> EffectCustom:
        return cls(nid)

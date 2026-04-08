from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar

from .structure import HIRCNode
from .base_types import FxBaseInitialValues


@dataclass
class EffectShareSet(HIRCNode):
    body_type: ClassVar[int] = 16
    fx_base_initial_values: FxBaseInitialValues = field(
        default_factory=lambda: FxBaseInitialValues(fx_id=0)
    )

    @classmethod
    def new(cls, nid: int | str) -> EffectShareSet:
        return cls(nid)

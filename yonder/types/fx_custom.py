from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar

from yonder.hash import Hash
from yonder.types.mixins import StateMixin
from .hirc_node import HIRCNode
from .base_types import FxBaseInitialValues, RTPC, StateChunk


@dataclass(repr=False, eq=False)
class EffectCustom(StateMixin, HIRCNode):
    body_type: ClassVar[int] = 17
    fx_base_initial_values: FxBaseInitialValues = field(
        default_factory=lambda: FxBaseInitialValues(fx_id=0)
    )

    @classmethod
    def new(cls, nid: Hash) -> EffectCustom:
        return cls(nid)

    @property
    def rtpcs(self) -> list[RTPC]:
        return self.fx_base_initial_values.initial_rtpc.rtpcs

    @property
    def states(self) -> StateChunk:
        return self.fx_base_initial_values.state_chunk

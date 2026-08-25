from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar

from yonder.hash import Hash
from yonder.enums import EffectPlugin
from yonder.types.mixins import StateMixin, RtpcMixin
from yonder.game.effects_data import EffectInfo
from .hirc_node import HIRCNode
from .base_types import FxBaseInitialValues, RTPC, StateChunk


@dataclass(repr=False, eq=False)
class _EffectBase(StateMixin, RtpcMixin, HIRCNode):
    fx_base_initial_values: FxBaseInitialValues = field(
        default_factory=lambda: FxBaseInitialValues(fx_id=0)
    )

    @classmethod
    def new(cls, nid: Hash):
        return cls(nid)

    @property
    def plugin(self) -> EffectPlugin:
        return EffectPlugin(self.fx_base_initial_values.fx_id)

    @property
    def info(self) -> EffectInfo:
        return EffectInfo.get(self.plugin)

    @property
    def params(self) -> dict[str, int | float]:
        # Store trailing bytes we were not able to decode yet
        params, self._trailing = self.info.decode_params(
            self.fx_base_initial_values.params
        )
        return params

    @params.setter
    def params(self, values: dict | list) -> None:
        trailing = getattr(self, "_trailing", bytes())
        self.fx_base_initial_values.params = self.info.encode_params(values, trailing)

    @property
    def rtpcs(self) -> list[RTPC]:
        return self.fx_base_initial_values.initial_rtpc.rtpcs

    @property
    def states(self) -> StateChunk:
        return self.fx_base_initial_values.state_chunk


@dataclass(repr=False, eq=False)
class EffectShareSet(_EffectBase):
    body_type: ClassVar[int] = 16


@dataclass(repr=False, eq=False)
class EffectCustom(_EffectBase):
    body_type: ClassVar[int] = 17

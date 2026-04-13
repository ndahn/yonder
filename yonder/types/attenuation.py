from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar

from .hirc_node import HIRCNode
from .base_types import InitialRTPC, ConversionTable, ConeParams, RTPC
from yonder.enums import CurveParameters


@dataclass
class Attenuation(HIRCNode):
    body_type: ClassVar[int] = 14
    is_cone_enabled: int = 0
    cone_params: ConeParams = field(default_factory=ConeParams)
    curves_to_use: list[int] = field(
        default_factory=lambda: [CurveParameters.None_.value] * 7
    )
    curve_count: int = 0
    curves: list[ConversionTable] = field(default_factory=list)
    initial_rtpc: InitialRTPC = field(default_factory=InitialRTPC)

    @classmethod
    def new(
        cls,
        nid: int | str,
        curves_to_use: list[CurveParameters],
        curves: list[ConversionTable],
        cone_params: ConeParams = None,
    ) -> Attenuation:
        if len(curves_to_use) != 7:
            raise ValueError("Curves to use must be exactly 7 elements")

        return cls(
            nid,
            curves_to_use=[crv.value for crv in curves_to_use],
            curves=curves,
            is_cone_enabled=bool(cone_params),
            cone_params=cone_params or ConeParams(),
        )

    def validate(self) -> None:
        if len(self.curves_to_use) != 7:
            raise ValueError("Curves to use must be exactly 7 elements")

    @property
    def rtpcs(self) -> list[RTPC]:
        return self.initial_rtpc.rtpcs

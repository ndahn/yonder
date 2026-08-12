from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar

from yonder.hash import Hash
from yonder.enums import CurveParameters
from yonder.util import logger
from .hirc_node import HIRCNode
from .base_types import InitialRTPC, ConversionTable, ConeParams, RTPC


@dataclass(repr=False, eq=False)
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
        nid: Hash,
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

        bad_curves = []
        for idx, curve in enumerate(self.curves):
            if len(curve.points) > 1:
                if not all(curve.points[i].from_ > curve.points[i-1].from_ for i in range(1, len(curve.points))):
                    bad_curves.append(idx)

        if bad_curves:
            logger.warning(f"{self} has non-monotonic curves {bad_curves}")

    @property
    def rtpcs(self) -> list[RTPC]:
        return self.initial_rtpc.rtpcs

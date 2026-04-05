from dataclasses import dataclass, field
from typing import ClassVar

from .structure import _HIRCNodeBody, HIRCNode
from .rewwise_base_types import InitialRTPC, RTPCGraphPoint
from .rewwise_enums import CurveScaling, CurveParameters


@dataclass
class ConeParams:
    inside_degrees: float = 0.0
    outside_degrees: float = 0.0
    outside_volume: float = 0.0
    low_pass: float = 0.0
    high_pass: float = 0.0


@dataclass
class ConversionTable:
    curve_scaling: CurveScaling = CurveScaling.Nothing
    point_count: int = 0
    points: list[RTPCGraphPoint] = field(default_factory=list)


@dataclass
class Attenuation(_HIRCNodeBody):
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
    ) -> "HIRCNode[Attenuation]":
        if len(curves_to_use) != 7:
            raise ValueError("Curves to use must be exactly 7 elements")

        return HIRCNode(
            nid,
            cls(
                curves_to_use=[crv.value for crv in curves_to_use],
                curves=curves,
            ),
        )

    def validate(self) -> None:
        if len(self.curves_to_use) != 7:
            raise ValueError("Curves to use must be exactly 7 elements")

from dataclasses import dataclass, field
from typing import ClassVar
from field_properties import field_property

from .structure import HIRCNode
from .rewwise_base_types import InitialRTPC, RTPCGraphPoint
from yonder.enums import CurveScaling, CurveParameters


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
    point_count: int = field_property(init=False, raw=True)
    points: list[RTPCGraphPoint] = field(default_factory=list)

    @field_property(point_count)
    def get_point_count(self) -> int:
        return len(self.points)


@dataclass
class Attenuation(HIRCNode):
    body_type: ClassVar[int] = 14
    is_cone_enabled: int = 0
    cone_params: ConeParams = field(default_factory=ConeParams)
    curves_to_use: list[int] = field(
        default_factory=lambda: [CurveParameters.None_.value] * 7
    )
    curve_count: int = field_property(init=False, raw=True)
    curves: list[ConversionTable] = field(default_factory=list)
    initial_rtpc: InitialRTPC = field(default_factory=InitialRTPC)

    @classmethod
    def new(
        cls,
        nid: int | str,
        curves_to_use: list[CurveParameters],
        curves: list[ConversionTable],
    ) -> "Attenuation":
        if len(curves_to_use) != 7:
            raise ValueError("Curves to use must be exactly 7 elements")

        super().__init__(nid)
        return cls(
            curves_to_use=[crv.value for crv in curves_to_use],
            curves=curves,
        )

    @field_property(curve_count)
    def get_curve_count(self) -> int:
        return len(self.curves)

    def validate(self) -> None:
        if len(self.curves_to_use) != 7:
            raise ValueError("Curves to use must be exactly 7 elements")

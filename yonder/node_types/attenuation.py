from dataclasses import dataclass, field
from typing import ClassVar

from .structure import _HIRCNodeBody
from .rewwise_base_types import InitialRTPC, RTPCGraphPoint
from .rewwise_enums import CurveScaling


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
    curves_to_use: list[int] = field(default_factory=lambda: [-1] * 7)
    curve_count: int = 0
    curves: list[ConversionTable] = field(default_factory=list)
    initial_rtpc: InitialRTPC = field(default_factory=InitialRTPC)

from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar

from yonder.hash import Hash
from yonder.enums import AttenuationProperty
from yonder.util import logger
from .hirc_node import HIRCNode
from .base_types import InitialRTPC, ConversionTable, ConeParams, RTPC
from .mixins import RtpcMixin


NO_CURVE = -1


@dataclass(repr=False, eq=False)
class Attenuation(RtpcMixin, HIRCNode):
    body_type: ClassVar[int] = 14
    is_cone_enabled: int = 0
    cone_params: ConeParams = field(default_factory=ConeParams)
    # NOTE Each of the 7 AttenuationProperties can have a custom distance-driven curve.
    # Attenuation is also driven by obstruction, occlusion, diffraction and transmission,
    # however, these are project-wide settings and cannot be defined per attenuation object.
    # Obstruction and occlusion can be found in the ENV section of the init.bnk, while
    # diffraction and transmission are set throug the acoustic textures of the STMG section.
    curves_to_use: list[int] = field(default_factory=lambda: [NO_CURVE] * 7)
    curve_count: int = 0
    curves: list[ConversionTable] = field(default_factory=list)
    initial_rtpc: InitialRTPC = field(default_factory=InitialRTPC)

    @classmethod
    def new(
        cls,
        nid: Hash,
        curves_to_use: list[int],
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

    def get_curve(self, prop: AttenuationProperty) -> ConversionTable:
        idx = self.curves_to_use[prop.value]
        if idx == NO_CURVE:
            return None

        return self.curves[idx]

    def get_cone_attenuation_factor(
        self, angle_deg: float, force_enabled: bool = False
    ) -> float:
        if not force_enabled and not self.is_cone_enabled:
            return 0.0

        # For 0 to 360: min(self._angle % 360, 360 - self._angle % 360)
        angle_deg = abs((angle_deg + 180) % 360 - 180)
        inner_half = self.cone_params.inside_degrees / 2
        outer_half = self.cone_params.outside_degrees / 2

        if angle_deg <= inner_half:
            # within the inner cone, no additional attenuation
            return 0.0

        if outer_half > inner_half:
            if angle_deg <= outer_half:
                # transition zone
                return (angle_deg - inner_half) / (outer_half - inner_half)
            else:
                # outside outer cone, maximum attenuation
                return 1.0

        return 1.0

    def get_attenuated_value(
        self, prop: AttenuationProperty, distance: float, angle: float = 0.0
    ) -> float:
        from yonder.audio.audiomath import eval_curve

        curve = self.get_curve(prop)
        if not curve:
            return 0.0

        y = eval_curve(curve.points, distance, curve.curve_scaling)

        if prop == AttenuationProperty.Volume:
            f = self.get_cone_attenuation_factor(angle)
            y += f * self.cone_params.outside_volume
        elif prop == AttenuationProperty.HPF:
            f = self.get_cone_attenuation_factor(angle)
            y += f * self.cone_params.high_pass
        elif prop == AttenuationProperty.LPF:
            f = self.get_cone_attenuation_factor(angle)
            y += f * self.cone_params.low_pass

        return y

    def get_attenuated_values(self, distance: float, angle: float = 0.0) -> dict:
        return {
            p: self.get_attenuated_value(p, distance, angle)
            for p in AttenuationProperty
        }

    def validate(self) -> None:
        if len(self.curves_to_use) != 7:
            raise ValueError("Curves to use must be exactly 7 elements")

        bad_curves = []
        for idx, curve in enumerate(self.curves):
            if len(curve.points) > 1:
                if not all(
                    curve.points[i].from_ > curve.points[i - 1].from_
                    for i in range(1, len(curve.points))
                ):
                    bad_curves.append(idx)

        if bad_curves:
            logger.warning(f"{self} has non-monotonic curves {bad_curves}")

    @property
    def rtpcs(self) -> list[RTPC]:
        return self.initial_rtpc.rtpcs

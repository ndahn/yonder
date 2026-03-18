from typing import Iterable
from dataclasses import dataclass

from yonder.enums import CurveType


@dataclass(slots=True)
class GraphPoint:
    x: float
    y: float
    interp: CurveType = "Linear"

    @classmethod
    def from_wwise(cls, point: dict) -> "GraphPoint":
        return cls(point["from"], point["to"], point["interpolation"])

    def to_wwise(self) -> dict:
        return {
            "from": self.x,
            "to": self.y,
            "interpolation": self.interp,
        }

    @property
    def coords(self) -> tuple[float, float]:
        return (self.x, self.y)

    def __str__(self) -> str:
        return f"GraphPoint<{self.interp}> ({self.x}, {self.y})"


class GraphCurve(list[GraphPoint]):
    @classmethod
    def from_wwise(cls, curve_type: str, data: list[dict]) -> "GraphCurve":
        return cls(curve_type, [GraphPoint.from_wwise(d) for d in data])

    def __init__(self, curve_type: str, points: Iterable[GraphPoint]):
        self.curve_type = curve_type
        super().__init__(points)

    def copy(self) -> "GraphCurve":
        return GraphCurve(self.curve_type, self)

    @property
    def x(self) -> Iterable[float]:
        for p in self:
            yield p.x

    @property
    def y(self) -> Iterable[float]:
        for p in self:
            yield p.y

    @property
    def interp(self) -> Iterable[str]:
        for p in self:
            yield p.interp

    @property
    def coords(self) -> Iterable[tuple[float, float]]:
        for p in self:
            yield p.coords

    def __str__(self) -> str:
        return f"GraphCurve<{self.curve_type}> [{[p for p in self]}]"

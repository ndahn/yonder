import math

from yonder.enums import CurveInterpolation


def constant(t: float, v0: float = 0.0, v1: float = 1.0) -> float:
    """Always returns v0."""
    return v0


def linear(t: float, v0: float = 0.0, v1: float = 1.0) -> float:
    """Linear interpolation between v0 and v1."""
    return t * (v1 - v0)


def log(t: float, v0: float = 0.0, v1: float = 1.0, strength: float = 0.5) -> float:
    """Ease-in: slow start, fast finish. strength [0, 1]."""
    d = (1.0 - strength) + strength * t
    if d != 0:
        return t / d * (v1 - v0)
    return t * (v1 - v0)


def exp(t: float, v0: float = 0.0, v1: float = 1.0, strength: float = 0.5) -> float:
    """Ease-out: fast start, slow finish. strength [0, 1]."""
    return 1.0 - log(1.0 - t, strength) * (v1 - v0)


def scurve(t: float, v0: float = 0.0, v1: float = 1.0) -> float:
    """Ease-in-out: slow start, fast middle, slow end."""
    return t * t * (3.0 - 2.0 * t) * (v1 - v0)


def inv_scurve(t: float, v0: float = 0.0, v1: float = 1.0) -> float:
    """Ease-out-in: fast start, slow middle, fast end."""
    if t < 0.5:
        return scurve(t * 2.0) * 0.5 * (v1 - v0)
    return 0.5 + (1.0 - scurve((1.0 - t) * 2.0)) * 0.5 * (v1 - v0)


def sine(t: float, v0: float = 0.0, v1: float = 1.0) -> float:
    """Quarter-sine ease-in-out arch."""
    return math.sin(t * math.pi * 0.5) * (v1 - v0)


def sine_recip(t: float, v0: float = 0.0, v1: float = 1.0) -> float:
    """Reciprocal sine: bows opposite to interp_sine."""
    return 1.0 - math.cos(t * math.pi * 0.5) * (v1 - v0)


def interpolate(
    interpolation: CurveInterpolation, t: float, v0: float = 0.0, v1: float = 1.0
) -> float:
    if interpolation == CurveInterpolation.Constant:
        return constant(t, v0, v1)
    elif interpolation == CurveInterpolation.Linear:
        return linear(t, v0, v1)
    elif interpolation == CurveInterpolation.Log1:
        return log(t, v0, v1, 0.5)
    elif interpolation == CurveInterpolation.Log3:
        return log(t, v0, v1, 0.8)
    elif interpolation == CurveInterpolation.Exp1:
        return exp(t, v0, v1, 0.5)
    elif interpolation == CurveInterpolation.Exp3:
        return exp(t, v0, v1, 0.8)
    elif interpolation == CurveInterpolation.SCurve:
        return scurve(t, v0, v1)
    elif interpolation == CurveInterpolation.Sine:
        return sine(t, v0, v1)
    elif interpolation == CurveInterpolation.SineRecip:
        return sine_recip(t, v0, v1)

    raise ValueError(f"Unknown interpolation type {interpolation}")

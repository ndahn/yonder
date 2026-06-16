import math

from yonder.enums import CurveInterpolation


def _lerp(shaped: float, v0: float, v1: float) -> float:
    """Map a normalized shape value onto [v0, v1]."""
    return v0 + shaped * (v1 - v0)


def _log_shape(t: float, strength: float) -> float:
    """Ease-out shape: fast start, leveling off. strength [0, 1]."""
    d = (1.0 - strength) + strength * t
    return t / d if d != 0.0 else t


def constant(t: float, v0: float = 0.0, v1: float = 1.0) -> float:
    """Hold the start value across the whole segment."""
    return v0


def linear(t: float, v0: float = 0.0, v1: float = 1.0) -> float:
    """Straight line from v0 to v1."""
    return _lerp(t, v0, v1)


def log(t: float, v0: float = 0.0, v1: float = 1.0, strength: float = 0.5) -> float:
    """Ease-out: fast start, gentle finish. strength [0, 1]."""
    return _lerp(_log_shape(t, strength), v0, v1)


def exp(t: float, v0: float = 0.0, v1: float = 1.0, strength: float = 0.5) -> float:
    """Ease-in: gentle start, fast finish (mirror of log). strength [0, 1]."""
    return _lerp(1.0 - _log_shape(1.0 - t, strength), v0, v1)


def scurve(t: float, v0: float = 0.0, v1: float = 1.0) -> float:
    """Ease-in-out (smoothstep): slow ends, fast middle."""
    return _lerp(t * t * (3.0 - 2.0 * t), v0, v1)


def inv_scurve(t: float, v0: float = 0.0, v1: float = 1.0) -> float:
    """Ease-out-in: fast ends, slow middle (inverse smoothstep)."""
    arg = max(-1.0, min(1.0, 1.0 - 2.0 * t))  # clamp guards float drift
    return _lerp(0.5 - math.sin(math.asin(arg) / 3.0), v0, v1)


def sine(t: float, v0: float = 0.0, v1: float = 1.0) -> float:
    """Sine ease-out: quick start, gentle settle."""
    return _lerp(math.sin(t * math.pi * 0.5), v0, v1)


def sine_recip(t: float, v0: float = 0.0, v1: float = 1.0) -> float:
    """Sine ease-in: gentle start, quick finish."""
    return _lerp(1.0 - math.cos(t * math.pi * 0.5), v0, v1)


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
    elif interpolation == CurveInterpolation.InvSCurve:
        return inv_scurve(t, v0, v1)
    elif interpolation == CurveInterpolation.Sine:
        return sine(t, v0, v1)
    elif interpolation == CurveInterpolation.SineRecip:
        return sine_recip(t, v0, v1)

    raise ValueError(f"Unknown interpolation type {interpolation}")
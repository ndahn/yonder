from __future__ import annotations
from typing import Callable
import math
import pyo

from yonder.types.base_types import RTPCGraphPoint
from yonder.enums import (
    PropID,
    RtpcAccum,
    WwiseCutoffFrequencies,
    CurveInterpolation,
    CurveScaling,
)
from yonder.interpolation import interpolate


def db_to_amp(db: float) -> float:
    return 10.0 ** (db / 20.0)


def amp_to_db(amp: float) -> float:
    return 20.0 * math.log10(max(amp, 1e-9))


def lpf_to_hz(val: float) -> float:
    lower = int(max(0, val))
    upper = int(min(100, val + 1))
    return interpolate(
        CurveInterpolation.Linear,
        val - lower,
        WwiseCutoffFrequencies[lower],
        WwiseCutoffFrequencies[upper],
    )


def hpf_to_hz(val: float) -> float:
    return lpf_to_hz(100 - val)


def cents_to_speed(cents: float) -> float:
    return 2.0 ** (cents / 1200.0)


def to_pyo_domain(prop: PropID, val: float) -> float:
    if prop == PropID.Volume:
        return db_to_amp(val)
    elif prop == PropID.LPF:
        return lpf_to_hz(val)
    elif prop == PropID.HPF:
        return hpf_to_hz(val)
    elif prop == PropID.Pitch:
        # semitones (same log domain as cents): no exp, just rescale
        return val / 100
    else:
        raise ValueError(f"Unhandled property {prop}")


def _scaling_domain(scaling: CurveScaling) -> tuple[Callable, Callable]:
    """Curve scaling picks which domain the *interpolation itself* happens in, not a post-hoc conversion of the interpolated result:
    - decibel curves interpolate in linear amplitude (halfway between 0dB and -96.3dB is ~-6dB, i.e. half amplitude, not -48.15dB)
    - frequency curves interpolate in octaves / log2 (halfway between 1000hz and 4000hz is 2000hz, one octave up, not 2500hz)

    See https://www.audiokinetic.com/en/public-library/2025.1.9_9197/?source=SDK&id=plugin_xml_properties.html

    Parameters
    ----------
    scaling : CurveScaling
        The scaling domain.

    Returns
    -------
    tuple[Callable, Callable]
        (to_interp_domain, from_interp_domain)
    """
    if scaling == CurveScaling.DB:
        return db_to_amp, amp_to_db
    elif scaling == CurveScaling.DBToLin:
        # same interpolation domain as DB, but the result stays linear instead of converting
        # back - for targets whose native unit is already linear rather than dB
        return db_to_amp, lambda v: v
    elif scaling == CurveScaling.Log:
        return lambda v: math.log2(max(v, 1e-6)), lambda v: 2.0**v

    # None_: raw linear interpolation
    return lambda v: v, lambda v: v


def make_envelope(
    points: list[RTPCGraphPoint],
    scaling: CurveScaling = CurveScaling.None_,
    out_conv: Callable[[float], float] = None,
    resolution: int = 8,
) -> pyo.Linseg:
    # scaling picks the domain interpolation happens in.
    # out_conv is a separate, final step converting the curve's native unit
    # (dB, percent, ...) into whatever unit the pyo chain expects (amp, hz)
    to_domain, from_domain = _scaling_domain(scaling)
    if not out_conv:
        out_conv = lambda v: v

    def value_at(p: RTPCGraphPoint, nxt: RTPCGraphPoint, t: float) -> float:
        y = interpolate(p.interpolation, t, to_domain(p.to), to_domain(nxt.to))
        return out_conv(from_domain(y))

    segs = []
    if points[0].from_ > 0.0:
        # Constant before first point
        segs.append((0.0, out_conv(points[0].to)))

    for p, nxt in zip(points[:-1], points[1:]):
        span = nxt.from_ - p.from_
        if span <= 0.0:
            continue

        n = int(span * resolution)
        for i in range(n):
            t = i / n
            segs.append((p.from_ + t * span, value_at(p, nxt, t)))

    # Extrapolate past final point
    segs.append((points[-1].from_, out_conv(points[-1].to)))
    return pyo.Linseg(segs)


def eval_curve(
    points: list[RTPCGraphPoint], x: float, scaling: CurveScaling = CurveScaling.None_
) -> float:
    if x <= points[0].from_:
        return points[0].to

    if x >= points[-1].from_:
        return points[-1].to

    to_domain, from_domain = _scaling_domain(scaling)
    for p, nxt in zip(points[:-1], points[1:]):
        if x > p.from_:
            t = (x - p.from_) / (nxt.from_ - p.from_)
            y = interpolate(p.interpolation, t, to_domain(p.to), to_domain(nxt.to))
            return from_domain(y)

    # fallback, shouldn't be reachable
    return points[-1].to


def accumulate(base: float, val: float, accum: RtpcAccum) -> float:
    if accum == RtpcAccum.Additive:
        return base + val
    elif accum == RtpcAccum.Multiply:
        return base * val
    elif accum == RtpcAccum.Boolean:
        return val if val > 0 else base
    elif accum == RtpcAccum.Maximum:
        return max(base, val)
    elif accum == RtpcAccum.Filter:
        # lpf/hpf are stored as 0-100 percent where higher = more filtering,
        # so "most restrictive wins" is the same operation as maximum
        return max(base, val)
    elif accum == RtpcAccum.Exclusive:
        return val

    return base

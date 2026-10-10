from __future__ import annotations
from typing import Callable
import math
import numpy as np
import pyo

from yonder.types.base_types import RTPCGraphPoint
from yonder.enums import (
    RtpcAccum,
    WwiseCutoffFrequencies,
    CurveInterpolation,
    CurveScaling,
)
from yonder.interpolation import interpolate
from .wavesignal import to_channels


# Lowest volume threshold in Wwise
DB_FLOOR = -93.0


def db_to_amp(db: float) -> float:
    return 10.0 ** (db / 20.0)


def amp_to_db(amp: float) -> float:
    return 20.0 * math.log10(max(amp, 1e-9))


def lpf_to_hz(val: float) -> float:
    val = max(0.0, min(100.0, val))
    lower = int(max(0, val))
    upper = int(min(100, val + 1))
    return interpolate(
        CurveInterpolation.Linear,
        val - lower,
        WwiseCutoffFrequencies[lower],
        WwiseCutoffFrequencies[upper],
    )


def hz_to_lpf(hz: float) -> float:
    if hz < 0:
        raise ValueError("Value must be >= 0")

    for key in range(101):
        upper = WwiseCutoffFrequencies[key]
        lower = WwiseCutoffFrequencies.get(key + 1, 0.0)
        if upper > hz > lower:
            return upper + (upper - hz) / (upper - lower)

    return 0.0


def hpf_to_hz(val: float) -> float:
    return lpf_to_hz(100 - val)


def hz_to_hpf(hz: float) -> float:
    return 100 - hz_to_lpf(hz)


def cents_to_speed(cents: float) -> float:
    return 2.0 ** (cents / 1200.0)


def speed_to_cents(speed: float) -> float:
    return 1200.0 * math.log(speed) / math.log(2)


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
    if not points:
        return 0.0

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


def _fft_resample(signal: np.ndarray, n_out: int) -> np.ndarray:
    """Resample to ``n_out`` frames by resizing the signal's spectrum."""
    n_in = len(signal)
    spec = np.fft.rfft(signal, axis=0)

    n_bins = n_out // 2 + 1
    out_spec = np.zeros((n_bins,) + spec.shape[1:], dtype=spec.dtype)
    # Zero padding interpolates, truncating both decimates and acts as the
    # anti-alias filter - there is nothing left above the new Nyquist to fold
    # back down.
    n_keep = min(len(spec), n_bins)
    out_spec[:n_keep] = spec[:n_keep]

    # The bin at Nyquist is unpaired, so it contributes once where every other
    # bin contributes twice. Whenever it changes role between the two lengths
    # its amplitude has to be split or doubled to compensate.
    n_common = min(n_in, n_out)
    nyquist = n_common // 2
    if n_common % 2 == 0 and nyquist < n_bins:
        if n_out > n_in:
            out_spec[nyquist] *= 0.5  # was Nyquist, now an ordinary paired bin
        elif n_out < n_in:
            out_spec[nyquist] *= 2.0  # was paired, now Nyquist

    # irfft normalizes by the output length, so undo the length change
    return np.fft.irfft(out_spec, n=n_out, axis=0) * (n_out / n_in)


def resample(signal: np.ndarray, framerate: int, target_framerate: int) -> np.ndarray:
    """Resample a signal to a different sample rate.

    Works in the frequency domain: transform, resize the spectrum to the new
    length, transform back. That is O(n log n) and band-limited in both
    directions, which matters because the alternative available without scipy
    - linear interpolation - filters poorly enough to dull the result audibly.

    Parameters
    ----------
    signal : numpy.ndarray
        Samples shaped ``(n_frames,)`` or ``(n_frames, n_channels)``.
    framerate : int
        Sample rate of ``signal``.
    target_framerate : int
        Sample rate to convert to.

    Returns
    -------
    numpy.ndarray
        The resampled signal, same shape bar the frame count. Returned as-is
        when the rates already match.
    """
    if framerate == target_framerate or len(signal) == 0:
        return signal

    ratio = target_framerate / framerate
    n_in = len(signal)
    n_out = max(1, round(n_in * ratio))

    # The transform treats the signal as periodic, so a clip that does not
    # begin and end near zero rings where its end wraps onto its start. Pad
    # both ends and cut the padding back off, putting that seam outside the
    # audio we keep.
    pad = min(n_in, 1024)
    silence = np.zeros((pad,) + signal.shape[1:], dtype=signal.dtype)
    padded = np.concatenate([silence, signal, silence])

    out = _fft_resample(padded, max(1, round(len(padded) * ratio)))

    start = round(pad * ratio)
    out = out[start : start + n_out]
    if len(out) < n_out:  # rounding slop at the tail
        missing = np.zeros((n_out - len(out),) + out.shape[1:], dtype=out.dtype)
        out = np.concatenate([out, missing])

    return out.astype(signal.dtype, copy=False)


def fade_edges(signal: np.ndarray, n_samples: int) -> np.ndarray:
    """Return a copy of ``signal`` faded in and out over ``n_samples``."""
    n_samples = min(n_samples, len(signal) // 2)
    if n_samples <= 0:
        return signal

    ramp = np.linspace(
        0.0, 1.0, n_samples, endpoint=False, dtype=signal.dtype
    )[:, np.newaxis]

    signal = signal.copy()  # never touch the caller's array
    signal[:n_samples] *= ramp
    signal[-n_samples:] *= ramp[::-1]
    return signal


def mix(
    signals: list[np.ndarray],
    offsets: list[float],
    framerates: list[int],
    *,
    mono: bool = False,
    target_framerate: int = None,
    fade: float = 0.003,
    normalize: bool = True,
) -> tuple[np.ndarray, int]:
    """Down-mix several signals onto a single timeline.

    Parameters
    ----------
    signals : list of numpy.ndarray
        Samples per track, shaped ``(n_frames,)`` or ``(n_frames, n_channels)``
        and normalized to ``[-1, 1]``. Trimming is the caller's job: pass only
        the audio that should be heard.
    offsets : list of float
        Where each signal starts on the timeline, in seconds. Audio placed
        before 0 is cut off rather than shifting the mix, so that output
        sample 0 stays pinned to timeline 0 and markers keep lining up.
    framerates : list of int
        Sample rate of each signal.
    mono : bool
        Fold the result to one channel instead of two.
    target_framerate : int, optional
        Rate to mix at. Defaults to the highest input rate, so no track gets
        band-limited by a lower-rate neighbour.
    fade : float
        Seconds of fade applied to each signal's own start and end. Clips
        trimmed to start or end mid-waveform click without it.
    normalize : bool
        Scale the result back into ``[-1, 1]`` if summing the tracks
        overshot. Only ever attenuates, and only when it has to - dividing by
        the track count unconditionally would make every mix quieter than the
        last.

    Returns
    -------
    tuple of (numpy.ndarray, int)
        The mix, shaped ``(n_frames, 1 or 2)``, and its sample rate.
    """
    if not len(signals) == len(offsets) == len(framerates):
        raise ValueError("signals, offsets and framerates must be the same length")

    if target_framerate is None:
        target_framerate = max(framerates, default=0)

    channels = 1 if mono else 2

    placed: list[tuple[int, np.ndarray]] = []
    for signal, offset, framerate in zip(signals, offsets, framerates):
        # Fold channels before resampling - halves the work for stereo -> mono
        signal = to_channels(signal, channels)
        # Fade before resampling, not after: a clip trimmed to start or end
        # mid-waveform is a step discontinuity, and a band-limited resampler
        # rings at one. Fading first means it never reaches the transform.
        signal = fade_edges(signal, round(fade * framerate))
        signal = resample(signal, framerate, target_framerate)

        # Offsets are rounded to whole samples here and nowhere else, so the
        # output length can never disagree with where the clips land. Rounding
        # after resampling also keeps the two roundings from compounding.
        start = round(offset * target_framerate)
        if start < 0:
            signal = signal[-start:]
            start = 0

        if len(signal):
            placed.append((start, signal))

    if not placed:
        return np.zeros((0, channels), dtype=np.float32), target_framerate

    total = max(start + len(signal) for start, signal in placed)
    out = np.zeros((total, channels), dtype=np.float32)

    for start, signal in placed:
        out[start : start + len(signal)] += signal

    if normalize:
        peak = np.abs(out).max()
        if peak > 1.0:
            out /= peak

    return out, target_framerate

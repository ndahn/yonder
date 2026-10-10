from pathlib import Path
import numpy as np
import wave
import sounddevice


def read_wav(path: Path, mono: bool = False) -> tuple[np.ndarray, int]:
    """Read a wav file into normalized float samples.

    Parameters
    ----------
    path : Path
        File to read.
    mono : bool
        If True the returned audio data will be mono.

    Returns
    -------
    tuple of (numpy.ndarray, int)
        Samples shaped ``(n_frames, n_channels)`` in ``[-1, 1]``, and the
        sample rate.
    """
    with wave.open(str(path), "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        raw = wf.readframes(wf.getnframes())

    if sampwidth == 1:
        # 8 bit wav is unsigned
        data = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
        data = (data - 128.0) / 128.0
    elif sampwidth == 2:
        data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 2.0**15
    elif sampwidth == 3:
        # 24 bit has no numpy dtype - widen to int32 keeping the sign
        packed = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        widened = np.zeros((len(packed), 4), dtype=np.uint8)
        widened[:, 1:] = packed  # shift into the high bytes so the sign carries
        data = widened.view("<i4").ravel().astype(np.float32) / 2.0**31
    elif sampwidth == 4:
        data = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2.0**31
    else:
        raise ValueError(f"Unsupported sample width: {sampwidth * 8} bit")

    data = data.reshape(-1, n_channels)

    # The audio backend is limited by the soundcard's channel count. This is usually
    # not an issue, but cutscene audio may sometimes have 8 channels.
    max_channels = sounddevice.query_devices(kind="output")["max_output_channels"]
    if max_channels < n_channels:
        data = data.mean(axis=1, keepdims=True)
        data = np.tile(data, (1, max_channels))

    if mono:
        data = data.mean(axis=1)

    return data, framerate


def write_wav(
    path: Path, signal: np.ndarray, framerate: int, sampwidth: int = 2
) -> None:
    """Write normalized float samples to a wav file.

    Parameters
    ----------
    path : Path
        File to write.
    signal : numpy.ndarray
        Samples shaped ``(n_frames,)`` or ``(n_frames, n_channels)``, expected
        in ``[-1, 1]``. Anything outside that range is clipped.
    framerate : int
        Sample rate to tag the file with.
    sampwidth : int
        Bytes per sample: 1, 2 or 4. Writing 24 bit is not supported.
    """
    if signal.ndim == 1:
        signal = signal[:, np.newaxis]

    signal = np.clip(signal, -1.0, 1.0)

    # Scale by the positive peak, not 2**(bits-1): the signed range is
    # asymmetric, so +1.0 would wrap to the most negative value instead.
    if sampwidth == 1:
        data = (signal * 127.0 + 128.0).round().astype(np.uint8)
    elif sampwidth == 2:
        data = (signal * (2.0**15 - 1)).round().astype("<i2")
    elif sampwidth == 4:
        data = (signal * (2.0**31 - 1)).round().astype("<i4")
    else:
        raise ValueError(f"Unsupported sample width: {sampwidth * 8} bit")

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(signal.shape[1])
        wf.setsampwidth(sampwidth)
        wf.setframerate(framerate)
        wf.writeframes(data.tobytes())


def minmax_envelope(
    signal: np.ndarray, time: np.ndarray, n_buckets: int
) -> tuple[np.ndarray, np.ndarray]:
    """Downsample a signal to a drawable min/max envelope.

    Splits the signal into ``n_buckets`` and keeps the extremes of each, so
    the plotted trace still shows the true peaks instead of whatever the
    decimation happened to land on.

    Parameters
    ----------
    signal : numpy.ndarray
        Mono samples.
    time : numpy.ndarray
        Timestamp per sample, the same length as ``signal``.
    n_buckets : int
        Buckets to reduce to; clamped to the sample count.

    Returns
    -------
    tuple of (numpy.ndarray, numpy.ndarray)
        ``(t, y)`` of length ``2 * n_buckets``, ready to plot as a filled
        waveform.
    """
    if not len(signal):
        return np.empty(0), np.empty(0)

    # Clamp so we never request more buckets than samples
    n_buckets = max(1, min(n_buckets, len(signal)))
    trim = (len(signal) // n_buckets) * n_buckets
    sig_buckets = signal[:trim].reshape(n_buckets, -1)
    t_buckets = time[:trim].reshape(n_buckets, -1)

    mins = sig_buckets.min(axis=1)
    maxs = sig_buckets.max(axis=1)
    t_mid = t_buckets.mean(axis=1)

    # Interleave: for each bucket emit (t, max) then (t, min) for a
    # continuous envelope trace
    t_out = np.empty(2 * n_buckets)
    y_out = np.empty(2 * n_buckets)
    t_out[0::2] = t_mid
    t_out[1::2] = t_mid
    y_out[0::2] = maxs
    y_out[1::2] = mins

    return t_out, y_out


def to_channels(signal: np.ndarray, channels: int) -> np.ndarray:
    """Fold a signal to exactly ``channels`` channels, as float32."""
    signal = np.asarray(signal, dtype=np.float32)
    if signal.ndim == 1:
        signal = signal[:, np.newaxis]

    if signal.shape[1] == channels:
        return signal

    if channels == 1:
        # Average, never sum - summing raises the level by the channel count
        return signal.mean(axis=1, keepdims=True)

    if signal.shape[1] == 1:
        return np.repeat(signal, channels, axis=1)

    # More channels than we want. A real surround fold-down needs the channel
    # layout, which a plain wav header does not carry, so keep the front pair.
    return signal[:, :channels]

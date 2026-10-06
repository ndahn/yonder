"""Loop point finder (ai generated, avoids librosa / scipy / numba).

WHAT IS A LOOP HERE
    A loop is a pair (start, end) of sample positions. Playback runs to `end`,
    then jumps back to `start`. The jump is inaudible if the music right before
    `end` flows into the music right after `start`.
    The easy case: the track repeats itself (e.g. the body is played twice). Two
    copies of the same spot are then a perfect pair. This module searches for such
    pairs and can also reward pairs whose jump is musically smooth when nothing
    repeats exactly (bar length, chord motion, note continuity).

VOCABULARY
    frame      N_FFT samples analysed together. Frames start every HOP samples,
               so neighbours overlap by 75 %.
    spectrum   energy per frequency inside one frame (magnitude of the FFT).
    chroma     12 numbers per frame: energy per pitch class (A, A#, B, C, ... G#,
               index 0 = A). Says "which notes sound", ignoring octave and instrument.
    onset      the moment a new note starts.
    flux       how much the spectrum grew since the previous frame. Peaks at onsets.
    candidate  a frame we consider as a loop point (onsets only).
    gap        end - start of a pair = loop length in samples.

THE CORE IDEA: ONE SCORE MATRIX
    With n candidates, every score is an (n, n) matrix: row i = candidate used as
    `start`, column j = candidate used as `end`. Each term below fills such a
    matrix, they are simply added, and the best cell wins.

PIPELINE (step numbers are used in the code comments)
    1. STFT: cut the audio into overlapping frames, FFT each frame.
    2. Per-frame features: chroma (which notes), flux (new note?), level (dB).
    3. Candidates: loop points sit on note starts, so only onset peaks are tried
       (~300 instead of thousands of frames, which keeps the pair search cheap).
    4. Score every (start, end) pair
       a. similarity: compare chroma around both points, 4 s ahead and 4 s behind
          (near frames count more). One matching frame proves little, a matching
          passage proves a lot.
          then: - small loudness-mismatch penalty (a hint, never a veto)
                + small bonus for longer loops (tie-breaker)
       b. optional transition terms ("does the music flow across the seam?"
          instead of "do the two spots sound alike?"), each with a weight, 0 = off:
          - bars:   is the loop a whole number of bars long?
          - chords: chord before `end` -> chord after `start`, rated by root motion
                    (same chord, 4th/5th = V->I / IV->I best, tritone worst)
          - seam:   do the notes just before `end` match the notes just after `start`?
    5. Refine: frames are coarse, so slide `end` by up to +-N_FFT/2 samples to where
       the waveform lines up best with `start` (cross-correlation) -> no click.

READING ORDER
    Start with `find_loops` at the bottom: it calls the helpers in pipeline order.
"""

from __future__ import annotations

import wave
from dataclasses import dataclass
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

N_FFT = (
    8192  # samples per frame (~186 ms at 44.1 kHz): long enough to tell low notes apart
)
HOP = 2048  # a new frame starts every 2048 samples (46 ms at 44.1 kHz)
FMIN, FMAX = (
    110.0,
    4000.0,
)  # Hz band for chroma / level: where musical notes live (A2 ... ~B7)
BLK = 512  # samples per block of the fine onset envelope (11.6 ms at 44.1 kHz)


@dataclass(frozen=True)
class LoopPair:
    """One loop proposal: play until `end`, then jump back to `start`."""

    start: int  # sample index where the loop restarts
    end: int  # sample index where playback jumps back to `start`
    score: float  # higher is better; only meaningful for comparing pairs of one track


# ---------------------------------------------------------------- input


def read_wav(path: str) -> tuple[np.ndarray, int]:
    """Read a PCM wav file with the stdlib `wave` module.

    Parameters
    ----------
    path : str
        Path to an uncompressed 8, 16, 24 or 32 bit integer wav file.

    Returns
    -------
    tuple[np.ndarray, int]
        (mono float32 samples scaled to -1..1, sample rate in Hz). Channels are averaged.
    """
    with wave.open(path, "rb") as w:
        ch, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
        raw = w.readframes(
            w.getnframes()
        )  # raw bytes, `width` bytes per sample, channels interleaved

    if width == 1:  # 8 bit wav is unsigned, centred on 128
        x = (np.frombuffer(raw, np.uint8).astype(np.float32) - 128) / 128
    elif (
        width == 3
    ):  # 24 bit: numpy has no int24, so add one zero low byte -> int32 (sample * 256)
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3)
        x = np.pad(b, ((0, 0), (1, 0))).view("<i4")[:, 0] / 2.0**31
    else:  # 16 / 32 bit: little-endian signed ints
        x = np.frombuffer(raw, f"<i{width}") / 2.0 ** (8 * width - 1)

    return x.reshape(-1, ch).mean(axis=1).astype(
        np.float32
    ), rate  # (samples, ch) -> mono


# ---------------------------------------------------------------- steps 1-3: features and candidates


def _features(x: np.ndarray, rate: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Steps 1+2: turn audio into three per-frame descriptions.

    Parameters
    ----------
    x : np.ndarray
        Mono samples.
    rate : int
        Sample rate in Hz.

    Returns
    -------
    tuple[np.ndarray, np.ndarray, np.ndarray]
        chroma (frames, 12): unit-length vector of "which notes sound". Frame f
            covers samples f * HOP ... f * HOP + N_FFT.
        flux (frames,): how much the spectrum grew vs. the previous frame (onset detector).
        level (frames,): band loudness in dB (only differences between frames matter).
    """
    # --- 1. STFT: windowed FFT of every frame, keeping only the FMIN..FMAX bins.
    freqs = np.fft.rfftfreq(N_FFT, 1 / rate)  # centre frequency (Hz) of every FFT bin
    band = (freqs >= FMIN) & (freqs <= FMAX)  # bins that are kept

    # sliding_window_view = every possible frame as a *view* (no copy); [::HOP] keeps every HOP-th.
    # Hann window: fades the frame edges to 0 so the cut-out doesn't smear the spectrum.
    frames, win = sliding_window_view(x, N_FFT)[::HOP], np.hanning(N_FFT)
    # Done in chunks of 256 frames so the full (frames, N_FFT) matrix never sits in memory.
    mag = np.concatenate(
        [
            np.abs(np.fft.rfft(frames[i : i + 256] * win, axis=1))[:, band]
            for i in range(0, len(frames), 256)
        ]
    )  # (frames, bins): energy per frame and frequency

    # --- 2a. level: total power of the band per frame, in dB
    level = 10 * np.log10(
        (mag**2).sum(axis=1) + 1e-12
    )  # +1e-12: log(0) guard for digital silence

    # --- 2b. flux: sum over frequencies of every *increase* of the dB spectrum between
    #     neighbouring frames. Decreases (notes fading) are ignored: only new sound counts.
    #     The -80 dB floor stops tiny noise fluctuations from counting as growth.
    db = np.maximum(20 * np.log10(mag / mag.max() + 1e-9), -80)
    flux = np.r_[
        0.0, np.maximum(np.diff(db, axis=0), 0).sum(axis=1)
    ]  # frame 0 has no predecessor

    # --- 2c. chroma: fold all frequencies onto the 12 pitch classes
    #     12 * log2(f / 440) = semitones above A440; rounding picks the nearest note;
    #     % 12 drops the octave, so A2, A3 and A4 all land in class 0.
    pitch_class = np.round(12 * np.log2(freqs[band] / 440)).astype(int) % 12

    # np.eye(12)[pitch_class] is a (bins, 12) one-hot matrix, so the matrix product
    # sums the energy of all bins that belong to the same pitch class.
    chroma = mag @ np.eye(12)[pitch_class]
    chroma = np.log1p(
        1000 * chroma / chroma.max()
    )  # compress: loud notes don't drown quiet ones
    chroma -= chroma.mean(
        axis=0
    )  # remove the track's average colour, keep what *changes*
    chroma[level < level.max() - 60] = (
        0  # near-silence has no pitch -> neutral zero vector
    )
    # Unit length, so a plain dot product of two frames is their cosine similarity (-1..1).
    chroma /= np.linalg.norm(chroma, axis=1, keepdims=True) + 1e-9

    return chroma, flux, level


def _candidates(flux: np.ndarray, max_n: int = 300) -> np.ndarray:
    """Step 3: pick the frames that are worth trying as loop points.

    Loop points sit on note starts, so we take local maxima of the flux curve.
    Trying every frame would make the pair matrix thousands x thousands.

    Parameters
    ----------
    flux : np.ndarray
        Onset strength per frame from `_features`.
    max_n : int
        Keep at most this many peaks (the strongest ones).

    Returns
    -------
    np.ndarray
        Sorted frame indices, always including frame 0 (the classic loop start).
        Falls back to a regular grid if there are almost no onsets (ambient music).
    """
    f = flux
    # peak = higher than the left neighbour, at least as high as the right one,
    # and clearly above average (mean + half a standard deviation) so noise is skipped
    is_peak = (
        (f[1:-1] > f[:-2]) & (f[1:-1] >= f[2:]) & (f[1:-1] > f.mean() + 0.5 * f.std())
    )

    pk = np.flatnonzero(is_peak) + 1  # +1: is_peak starts at frame 1
    pk = np.sort(
        pk[np.argsort(f[pk])[-max_n:]]
    )  # keep only the strongest, back in time order

    if (
        len(pk) < 8
    ):  # no clear onsets -> regular grid so the search still has something to try
        pk = np.arange(0, len(f), max(1, len(f) // max_n))

    return np.union1d(pk, [0])


def _onset_env(x: np.ndarray) -> np.ndarray:
    """Fine time-domain onset curve: loudness *rises* per 11.6 ms block.

    The STFT frames are long (186 ms), so they locate onsets only roughly. This curve
    is cheap and precise, and is used for (a) snapping candidates onto the note and
    (b) estimating the beat.

    Returns
    -------
    np.ndarray
        (len(x) // BLK - 1,): index i = loudness rise between block i and block i + 1.
    """
    # RMS loudness per block: reshape the signal into (blocks, BLK) rows
    env = np.sqrt((x[: len(x) // BLK * BLK].reshape(-1, BLK) ** 2).mean(axis=1))
    return np.maximum(np.diff(env), 0)  # keep rises only


def _snap_to_onset(onset: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Move candidate positions from "frame start" to "where the note really starts".

    A flux peak marks the frame in which a note first shows up, so that frame starts
    ~100 ms *before* the note. The transition terms need the position of the note itself.

    Parameters
    ----------
    onset : np.ndarray
        Output of `_onset_env`.
    t : np.ndarray
        Candidate positions as frame starts, in samples.

    Returns
    -------
    np.ndarray
        Positions in samples, accurate to about one block (11.6 ms). Sample 0 stays 0.
    """
    # For every candidate: the BLK-blocks that lie inside its frame (N_FFT // BLK = 16 of them) ...
    idx = np.minimum(t[:, None] // BLK + np.arange(N_FFT // BLK), len(onset) - 1)
    # ... pick the block with the biggest loudness rise; +1 because onset[i] is the rise
    # *into* block i + 1. Convert block index -> sample position.
    snapped = (idx[np.arange(len(t)), np.argmax(onset[idx], axis=1)] + 1) * BLK
    return np.where(t == 0, 0, snapped)  # keep sample 0, the classic loop start


# ---------------------------------------------------------------- step 4a: similarity


def _gather(
    chroma: np.ndarray, cand: np.ndarray, n: int, ahead: bool, skip: int = 0
) -> np.ndarray:
    """Collect the n chroma frames right after (or before) every candidate.

    Example: candidate frame 10, n = 3, skip = 0 gives frames 10, 11, 12 for
    ahead=True and frames 9, 8, 7 for ahead=False (nearest frame first).

    Parameters
    ----------
    chroma : np.ndarray
        (frames, 12) from `_features`.
    cand : np.ndarray
        Candidate frame indices.
    n : int
        How many frames to collect per candidate.
    ahead : bool
        True = frames from the candidate onwards, False = frames before it.
    skip : int
        Leave out this many frames next to the point. Frames adjacent to an onset
        overlap the onset itself and mix the old and the new chord.

    Returns
    -------
    np.ndarray
        (len(cand), n, 12). Positions outside the file are zeros ("silence").
    """
    pad = np.pad(
        chroma, ((n + skip, n + skip), (0, 0))
    )  # zero rows so indices past the edges are valid
    offs = (
        skip + np.arange(n) if ahead else -1 - skip - np.arange(n)
    )  # frame offsets from the candidate

    # cand[:, None] + offs broadcasts to (len(cand), n); + n + skip compensates the padding at the front
    return pad[cand[:, None] + n + skip + offs]


def _context_sim(chroma: np.ndarray, cand: np.ndarray, ctx: int) -> np.ndarray:
    """Step 4a: how alike does the music around two candidates sound?

    For a pair (i, j) we compare the `ctx` frames *after* both points, and the `ctx`
    frames *before* both points, frame by frame (cosine similarity), with a weighted
    average that favours frames close to the point. The better of the two sides counts.

    Parameters
    ----------
    chroma : np.ndarray
        (frames, 12) from `_features`.
    cand : np.ndarray
        Candidate frame indices, length n.
    ctx : int
        Frames per side (about 4 s worth).

    Returns
    -------
    np.ndarray
        (n, n), roughly -1..1. 1 = identical notes around both points.
    """
    w = np.geomspace(
        1.0, 0.1, ctx
    )  # weights: 1.0 next to the point, fading to 0.1 far away
    n = len(cand)
    sims = []

    for ahead in (True, False):  # music after each point / music before each point
        win = _gather(chroma, cand, ctx, ahead)  # (n, ctx, 12)
        flat = win.reshape(n, -1)  # one long vector per candidate: ctx * 12 numbers
        # (weighted flat) @ flat.T gives for every pair the weighted sum over frames of the
        # frame-wise dot products (= cosine similarities); / w.sum() turns it into an average.
        sims.append((win * w[None, :, None]).reshape(n, -1) @ flat.T / w.sum())
    
    # max: near a file edge one side is missing (counts as zeros), the other can still match
    return np.maximum(*sims)


# ---------------------------------------------------------------- step 4b: transition terms


def _chord_templates() -> np.ndarray:
    """Chord "fingerprints" that chroma vectors are compared against.

    A triad is three notes: root, third (4 semitones up for major, 3 for minor) and
    fifth (7 semitones up). The template has a 1 on those three pitch classes.
    Dot product of a chroma vector with all 24 rows, then taking the best row, is a
    simple chord detector.

    Returns
    -------
    np.ndarray
        (24, 12), unit-length rows. Row r (0..11) = major triad with root r,
        row 12 + r = minor triad with root r. Pitch class 0 = A (so C = 3, G = 10).
    """
    t = np.zeros((24, 12))
    for r in range(12):
        t[r, [r, (r + 4) % 12, (r + 7) % 12]] = 1  # major: root, major 3rd, 5th
        t[12 + r, [r, (r + 3) % 12, (r + 7) % 12]] = 1  # minor: root, minor 3rd, 5th

    t -= t.mean(
        axis=1, keepdims=True
    )  # centred like the chroma, so both are comparable

    return t / np.linalg.norm(t, axis=1, keepdims=True)


def _chord_moves() -> np.ndarray:
    """Lookup table: how smoothly does one chord lead into another?

    Rated by the distance between the two roots in semitones, folded so that up and
    down count the same (0..6):
        0 same root (1.0; major <-> minor on the same root: 0.6)
        1 half step 0.3      2 whole step 0.5
        3, 4 thirds 0.7      5 fourth / fifth 0.9 (V -> I, IV -> I, the strongest motion)
        6 tritone 0.2 (the most tense jump)
    This is a rule of thumb from Western harmony and ignores direction.

    Returns
    -------
    np.ndarray
        (24, 24): [from_chord, to_chord] -> rating 0..1. Chord ids as in `_chord_templates`.
        Example: C major (3) -> G major (10) = 0.9.
    """
    root, minor = (
        np.arange(24) % 12,
        np.arange(24) // 12,
    )  # root note and major/minor flag per chord id

    d = (
        root[None, :] - root[:, None]
    ) % 12  # semitone distance from row chord to column chord
    ic = np.minimum(d, 12 - d)  # fold: 7 semitones up = 5 down, both are a "fifth"
    t = np.array([1.0, 0.3, 0.5, 0.7, 0.7, 0.9, 0.2])[ic]  # rating per folded distance

    return np.where(
        (ic == 0) & (minor[:, None] != minor[None, :]), 0.6, t
    )  # C -> Cm: so-so


TEMPLATES, CHORD_MOVES = _chord_templates(), _chord_moves()  # built once at import


def _edge_chroma(
    chroma: np.ndarray, cand: np.ndarray, k: int
) -> tuple[np.ndarray, np.ndarray]:
    """The notes right after, and right before, every candidate (used for chords and seam).

    Averages k frames on each side into one 12-number vector, so a single noisy frame
    cannot decide the chord.

    Parameters
    ----------
    chroma : np.ndarray
        (frames, 12) from `_features`.
    cand : np.ndarray
        Candidate frame indices, length n.
    k : int
        Frames to average per side (about 0.5 s).

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        (after, before), each (n, 12) unit length.
        after[i]  = notes playing after candidate i  (relevant if i is the loop *start*)
        before[j] = notes playing before candidate j (relevant if j is the loop *end*)
    """
    out = []
    # The flux peak lags the true onset, so frames right before a candidate still
    # contain the new note: start 6 frames back there (chord accuracy 0.4 -> 0.9 in tests).

    for ahead, skip in ((True, 0), (False, 6)):
        m = _gather(chroma, cand, k, ahead, skip).mean(axis=1)  # (n, 12)
        out.append(
            m / (np.linalg.norm(m, axis=1, keepdims=True) + 1e-9)
        )  # back to unit length
        
    return out[0], out[1]


def _beat_period(onset: np.ndarray, rate: int) -> float:
    """Estimate the beat period via autocorrelation of the onset curve.

    Autocorrelation = compare the curve with a shifted copy of itself. If the music
    has a beat, the copy matches best when shifted by exactly one beat (or a multiple).
    We look for the strongest match between 0.3 s and 1.0 s (200 .. 60 bpm).
    Can land on half or double the true tempo.

    Parameters
    ----------
    onset : np.ndarray
        Output of `_onset_env`.
    rate : int
        Sample rate in Hz.

    Returns
    -------
    float
        Beat period in samples, or 0.0 if no clear beat exists.
    """
    onset = onset - onset.mean()  # remove the constant part, keep only the rhythm

    # Autocorrelation via FFT (fast): power spectrum, then back. Zero-padding to 2x length
    # avoids the signal wrapping around. acf[lag] = similarity with a copy shifted by `lag` blocks.
    acf = np.fft.irfft(np.abs(np.fft.rfft(onset, 2 * len(onset))) ** 2)[: len(onset)]
    lo, hi = int(0.3 * rate / BLK), int(1.0 * rate / BLK)  # search range in blocks
    lag = lo + int(np.argmax(acf[lo:hi]))

    if (
        acf[lag] < 0.1 * acf[0]
    ):  # acf[0] = perfect self-match; a weak peak means no real beat
        return 0.0

    # Fit a parabola through the peak and its two neighbours: gives the lag in fractions
    # of a block (the plain argmax is only accurate to +-5.8 ms).
    a, b, c = acf[lag - 1], acf[lag], acf[lag + 1]

    return (
        lag + 0.5 * (a - c) / (a - 2 * b + c - 1e-12)
    ) * BLK  # 1e-12: avoid dividing by zero


def _bar_fit(gap: np.ndarray, bar: float) -> np.ndarray:
    """Is the loop a whole number of bars long?

    Example with a 2 s bar: an 8 s loop is 4.0 bars -> 1.0, a 7 s loop is 3.5 bars
    (ends mid-bar) -> 0.0, a 7.5 s loop is 3.75 bars -> 0.5.

    Parameters
    ----------
    gap : np.ndarray
        Loop lengths in samples (any shape), e.g. the (n, n) matrix of all pairs.
    bar : float
        Bar length in samples (beats_per_bar * beat period). 0 = unknown.

    Returns
    -------
    np.ndarray
        Same shape as `gap`: 1 = whole bars, 0 = exactly half a bar off.
        All ones if the bar length is unknown (no opinion, so the ranking is unchanged).
    """
    if bar <= 0:
        return np.ones(gap.shape)

    frac = gap / bar  # loop length in bars, e.g. 3.75

    return 1 - 2 * np.abs(
        frac - np.round(frac)
    )  # distance to the nearest whole bar, scaled to 0..1


# ---------------------------------------------------------------- step 5: refinement


def _refine(
    x: np.ndarray, start: int, end: int, win: int = N_FFT, radius: int = N_FFT // 2
) -> int:
    """Step 5: nudge `end` to the sample where the waveform lines up best with `start`.

    The analysis works on frames, so `end` is only right to within roughly one frame.
    Jumping with a misaligned waveform clicks. We take the audio after `start` as a
    template and slide it over the audio around `end`, using normalized
    cross-correlation: 1.0 = identical shape, regardless of loudness.

    The window is one whole frame (the onset that made this a candidate is inside, so
    it has a sharp shape to lock onto). The radius covers the up to ~1.5 hops the two
    candidate frames can be out of phase with each other.

    Parameters
    ----------
    x : np.ndarray
        Mono samples.
    start, end : int
        Loop points in samples, as found by the frame analysis.
    win : int
        Template length in samples.
    radius : int
        Search +-radius samples around `end`.

    Returns
    -------
    int
        Improved `end`. Unchanged if the search window would leave the file.
    """
    lo = end - radius
    if lo < 0 or end + radius + win > len(x) or start + win > len(x):
        return end  # too close to the file edge, keep the frame estimate

    ref, seg = (
        x[start : start + win],
        x[lo : end + radius + win],
    )  # template, and the region to search

    corr = np.correlate(seg, ref, "valid")  # dot product of the template at every shift

    # Normalization: energy of the window under each shift = difference of cumulative
    # sums of squares (float64: float32 sums lose precision).
    cum = np.cumsum(np.r_[0.0, seg.astype(np.float64) ** 2])
    energy = cum[win:] - cum[:-win]
    ncc = corr / np.sqrt(
        energy * (ref.astype(np.float64) ** 2).sum() + 1e-12
    )  # 1e-12: silence guard

    return lo + int(np.argmax(ncc))  # best shift -> sample position


# ---------------------------------------------------------------- public entry point


def find_loops(
    x: np.ndarray,
    rate: int,
    min_len_s: float = 5.0,
    top: int = 3,
    context_length: float = 4.0,
    loudness_weight: float = 0.05,
    length_weight: float = 0.02,
    bar_weight: float = 0.03,
    chord_weight: float = 0.03,
    seam_weight: float = 0.05,
    beats_per_bar: int = 4,
) -> list[LoopPair]:
    """Best loop (start, end) pairs of a mono float signal, best first.

    The score of a pair (start i, end j) is the sum of

        similarity(i, j)                                  how alike the music around both points is
      - loudness_weight * tanh(|dB_i - dB_j| / 6)         loudness mismatch (hint)
      + length_weight   * gap / len(x)                    longer loops preferred (tie-breaker)
      + bar_weight      * bar_fit(gap)                    whole number of bars
      + chord_weight    * chord_move(end -> start)        harmonic motion across the jump
      + seam_weight     * cos(notes before end, after start)

    Parameters
    ----------
    x : np.ndarray
        Mono samples (see `read_wav`). Tuned for 44.1 / 48 kHz.
    rate : int
        Sample rate in Hz.
    min_len_s : float
        Shortest loop to consider, in seconds.
    top : int
        Number of pairs to return (neighbours of the best pair may show up too).
    context_length : float
        Number of frames to analyze around candidate points, in seconds.
    loudness_weight : float
        Max score penalty for a loudness mismatch. A hint, never a veto:
        similar music with a different volume still wins if it matches better.
    length_weight : float
        Bonus for a loop spanning the whole track. Periodic music has many nearly
        equal pairs (1 bar, 2 bars, ...), this makes the longest one win.
    bar_weight, chord_weight, seam_weight : float
        Transition terms (step 4b), each worth at most this much score. 0 switches
        a term off and skips its computation. Raise them to favour smooth
        transitions over plain similarity, e.g. for tracks without a repeat.
        bar: whole number of bars. chord: harmonic motion across the jump.
        seam: notes before `end` flow into notes after `start`.
    beats_per_bar : int
        Meter for the bar term (4 for 4/4, 3 for waltz). Only used if bar_weight > 0.

    Returns
    -------
    list[LoopPair]
        Best first. Empty if the track is shorter than `min_len_s`.

    Example
    -------
    >>> x, rate = read_wav("bgm.wav")
    >>> best = find_loops(x, rate)[0]
    >>> start_s, dur_s = best.start / rate, (best.end - best.start) / rate
    """
    # --- 1-3. features per frame, then the frames worth trying as loop points
    chroma, flux, level = _features(x, rate)
    cand = _candidates(flux)  # n frame indices

    # --- 4a. similarity of the music around every pair: (n, n), row = start, col = end
    sim = _context_sim(chroma, cand, ctx=int(context_length * rate / HOP))  # ctx = frames in s

    # loudness at each candidate: moving average of the dB level over k frames (~1 s).
    # Padding with the edge values keeps the output as long as `level`.
    k = max(1, int(rate / HOP))
    smooth = np.convolve(
        np.pad(level, (k // 2, k - 1 - k // 2), "edge"), np.ones(k) / k, "valid"
    )
    lv = smooth[cand]

    # Positions in samples. Snapped onto the note itself, not the (earlier) frame start.
    onset = _onset_env(x)
    t = _snap_to_onset(onset, cand * HOP)
    gap = (
        t[None, :] - t[:, None]
    )  # (n, n): loop length if row i is the start and column j the end

    score = (
        sim
        # tanh saturates: a 6 dB mismatch costs ~76 % of loudness_weight, 20 dB barely more
        - loudness_weight * np.tanh(np.abs(lv[:, None] - lv[None, :]) / 6)
        + length_weight * gap / len(x)
    )

    # --- 4b. transition terms, each only computed if switched on
    if bar_weight:
        score += bar_weight * _bar_fit(gap, beats_per_bar * _beat_period(onset, rate))

    if chord_weight or seam_weight:
        after, before = _edge_chroma(
            chroma, cand, k=max(1, int(0.5 * rate / HOP))
        )  # ~0.5 s each side

        if seam_weight:
            # [i, j] = cosine(notes after start i, notes before end j)
            score += seam_weight * after @ before.T

        if chord_weight:
            from_chord = np.argmax(
                before @ TEMPLATES.T, axis=1
            )  # chord playing as we leave `end`
            to_chord = np.argmax(
                after @ TEMPLATES.T, axis=1
            )  # chord we land on at `start`
            # Broadcast to (n, n): [i, j] = rating of from_chord[j] -> to_chord[i]
            score += chord_weight * CHORD_MOVES[from_chord[None, :], to_chord[:, None]]

    score[
        gap < min_len_s * rate
    ] = -np.inf  # too short; also removes end <= start (negative gap)

    # --- pick the best cells, then 5. refine their `end`
    pairs = []
    best = np.argsort(score, axis=None)[::-1][:top]  # flat indices of the top scores

    for i, j in zip(*np.unravel_index(best, score.shape)):  # flat index -> (row, col)
        if np.isfinite(score[i, j]):  # skip -inf cells (fewer valid pairs than `top`)
            pairs.append(
                LoopPair(
                    int(t[i]), _refine(x, int(t[i]), int(t[j])), float(score[i, j])
                )
            )
    
    return pairs

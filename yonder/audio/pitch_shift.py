import numpy as np


class PitchShifter:
    """Streaming phase-vocoder pitch shifter.

    Shifts pitch by remapping frequency bins rather than resampling, so the output length always equals the input length. Phase and overlap-add state is retained between calls, giving glitch-free output across chunk boundaries and allowing the pitch to change on any frame.

    Parameters
    ----------
    channels : int
        Number of audio channels in each chunk.
    frame : int, default 2048
        FFT size. Also determines latency (about ``frame`` samples) and tone
        quality; larger is cleaner but adds delay.
    osamp : int, default 8
        Overlap factor, equal to ``frame / hop``. Higher values reduce
        artifacts at the cost of more FFTs per second.

    Attributes
    ----------
    pitch : float
        Frequency multiplier applied during processing. ``1.0`` is unison,
        ``2.0`` is one octave up. May be set directly at any time.
    hop : int
        Step between successive analysis frames, in samples.

    Notes
    -----
    Phase vocoders soften sharp transients and percussion slightly, and
    extreme ratios (beyond roughly +/-12 semitones) introduce audible
    artifacts. Output gain is normalized to unity at ``pitch == 1.0``.
    """

    def __init__(self, channels: int, fft_size: int = 2048, overlap: int = 8):
        self.pitch = 1.0
        self.hop = fft_size // overlap

        self._ch = channels
        self._fft_size = fft_size

        i = np.arange(fft_size)
        self._win = 0.5 - 0.5 * np.cos(2 * np.pi * i / fft_size)  # periodic hann
        self._synwin = self._win / (overlap * 0.375)  # overlap-add gain fix
        self._expct = 2 * np.pi * self.hop / fft_size  # phase advance / bin / hop
        self._bin_indices = np.arange(fft_size // 2 + 1)  # bin indices
        self._last_phase = np.zeros((self._bin_indices.size, channels))
        self._sum_phase = np.zeros((self._bin_indices.size, channels))
        self._in_buf = np.zeros((0, channels))
        self._accum = np.zeros((fft_size, channels))  # overlap-add buffer
        self._out = np.zeros((fft_size, channels))  # pre-buffered latency

    def set_semitones(self, semitones: float):
        """Set the shift in semitones.

        Parameters
        ----------
        semitones : float
            Shift amount; ``+12`` raises by one octave, ``-12`` lowers by one.
        """
        self.pitch = 2.0 ** (semitones / 12.0)

    def process(self, chunk: np.ndarray) -> np.ndarray:
        """Feed one chunk and return the same length of shifted audio.

        Parameters
        ----------
        chunk : numpy.ndarray
            Input audio shaped ``(n, channels)``. A 1-D array shaped ``(n,)`` is accepted and treated as a single channel. The number of samples ``n`` may vary between calls; internal buffering absorbs it.

        Returns
        -------
        numpy.ndarray
            Shifted audio shaped ``(n, channels)``, where ``n`` matches the input chunk length.

        Notes
        -----
        Output is delayed by roughly ``fft_size`` samples relative to the input; the first calls return mostly pre-buffered silence while the pipeline fills.
        """
        if chunk.ndim == 1:
            chunk = chunk[:, None]

        self._in_buf = np.concatenate([self._in_buf, chunk])
        while len(self._in_buf) >= self._fft_size:
            self._frame(self._in_buf[: self._fft_size] * self._win[:, None])
            self._in_buf = self._in_buf[self.hop :]  # slide by one hop

        m = len(chunk)
        if len(self._out) < m:  # guard against underflow
            self._out = np.concatenate(
                [self._out, np.zeros((m - len(self._out), self._ch))]
            )

        out, self._out = self._out[:m], self._out[m:]
        return out

    def _frame(self, frame: np.ndarray):
        """Process one windowed analysis frame and append a hop of output.

        Runs the three phase-vocoder stages: analysis estimates each bin's true frequency from its phase difference, processing remaps bins by the pitch ratio, and synthesis rebuilds phase and overlap-adds the result into the output buffer.

        Parameters
        ----------
        frame : numpy.ndarray
            One windowed analysis frame shaped ``(self.n, channels)``.

        Returns
        -------
        None
            Results are written to internal state; one ``hop`` of audio is appended to ``self.out``.
        """
        spec = np.fft.rfft(frame, axis=0)
        mag = np.abs(spec)
        phase = np.angle(spec)

        # analysis: true frequency of each bin, in bin units
        d = phase - self._last_phase - self._bin_indices[:, None] * self._expct
        self._last_phase = phase
        d -= 2 * np.pi * np.round(d / (2 * np.pi))  # wrap to (-pi, pi]
        freq = self._bin_indices[:, None] + d / self._expct

        # processing: remap bins by pitch ratio
        idx = np.floor(self._bin_indices * self.pitch).astype(int)
        ok = idx <= self._fft_size // 2
        syn_mag = np.zeros_like(mag)
        syn_freq = np.zeros_like(freq)
        np.add.at(syn_mag, idx[ok], mag[ok])  # pile up shifted magnitudes
        syn_freq[idx[ok]] = freq[ok] * self.pitch

        # synthesis: rebuild phase from shifted frequency
        self._sum_phase += syn_freq * self._expct
        self._sum_phase -= 2 * np.pi * np.round(self._sum_phase / (2 * np.pi))
        out_frame = np.fft.irfft(
            syn_mag * np.exp(1j * self._sum_phase), n=self._fft_size, axis=0
        )
        self._accum += out_frame * self._synwin[:, None]
        self._out = np.concatenate([self._out, self._accum[: self.hop]])  # emit one hop
        self._accum = np.concatenate(
            [self._accum[self.hop :], np.zeros((self.hop, self._ch))]
        )

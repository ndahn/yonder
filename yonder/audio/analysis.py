import pyo


class BarEqualizer:
    """
    Splits a signal into n log-spaced bands, tracks each band's amplitude.

    Remember Winamp?
    """

    def __init__(
        self,
        source: pyo.PyoObject,
        n_bands: int = 16,
        fmin: float = 20.0,
        fmax: float = 20000.0,
    ):
        self.freqs = self._log_bands(fmin, fmax, n_bands)
        self.filters = [pyo.ButBP(source, freq=f, q=1) for f in self.freqs]
        self.followers = [
            pyo.Follower2(bp, risetime=0.01, falltime=0.25) for bp in self.filters
        ]

    @staticmethod
    def _log_bands(fmin: float, fmax: float, n: int) -> list[float]:
        # log spacing so bars represent equal musical intervals, not equal hz
        ratio = (fmax / fmin) ** (1 / (n - 1))
        return [fmin * ratio**i for i in range(n)]

    def get_levels(self) -> list[float]:
        """Current amplitude per band, same order as self.freqs."""
        return [f.get() for f in self.followers]


class SpectrumAnalyzer:
    """Full-resolution fft magnitude spectrum."""

    def __init__(
        self, source: pyo.PyoObject, sr: float, size: int = 1024, overlaps: int = 4
    ):
        # Upper half of bins mirrors the lower half for real input
        self.n_bins = size // 2
        self.freqs = [i * sr / size for i in range(self.n_bins)]
        # wintype 2 = hanning window
        fft = pyo.FFT(source, size=size, overlaps=overlaps, wintype=2)
        self.magnitude = (fft["real"] * fft["real"] + fft["imag"] * fft["imag"]) ** 0.5

    def get_spectrum(self) -> list[float]:
        """Current magnitude per fft bin, same order as self.freqs."""
        return self.magnitude.get(all=True)[: self.n_bins]

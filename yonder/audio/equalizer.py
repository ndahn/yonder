import math
import pyo


class Equalizer(pyo.PyoObject):
    def __init__(
        self,
        input: pyo.PyoObject,
        preset: dict[int, float] = None,
        mul: float = 1,
        add: float = 0,
    ):
        pyo.PyoObject.__init__(self, mul, add)

        if preset is None:
            preset = {}

        # pow: (eq, ctrl)
        self._eq: dict[int, tuple[pyo.EQ, pyo.SigTo]] = {}

        sig = input
        for pow in range(5, 15):
            freq = 2**pow
            boost = preset.get(freq, 0.0)
            ctrl = pyo.SigTo(boost, time=0.05)
            sig = pyo.EQ(sig, freq, boost=ctrl)
            self._eq[pow] = (sig, ctrl)

        self._base_objs = self._eq[14][0].getBaseObjects()

    def set_preset(self, preset: dict[int, float] = None) -> None:
        for freq, boost in preset.items():
            self.set_boost(freq, boost)

    def set_boost(self, pow_or_freq: int, boost: float) -> None:
        if pow_or_freq not in self._eq:
            pow_or_freq = int(round(math.log2(pow_or_freq)))

        self._eq[pow_or_freq][1].value = boost

    def play(self, dur: float = 0, delay: float = 0) -> pyo.PyoObject:
        for eq in self._eq:
            eq.play(dur, delay)

        return pyo.PyoObject.play(self, dur, delay)

    def stop(self, wait: int = 0) -> pyo.PyoObject:
        for eq in self._eq:
            eq.stop(wait)

        return pyo.PyoObject.stop(self, wait)

    def out(
        self, chnl: int = 0, inc: int = 1, dur: int = 0, delay: int = 0
    ) -> pyo.PyoObject:
        self.play()
        return pyo.PyoObject.out(self, chnl, inc, dur, delay)

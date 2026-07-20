import math
import pyo


class EQPresets:
    flat = (0.0,) * 10
    acoustic = [5, 5, 4, 1, 2, 2, 3.5, 4, 3.5, 2]
    electronic = [4, 4, 1, 0, -2, 2, 1, 1.5, 4, 5]
    piano = [3, 2, 0, 2.5, 3, 1.5, 3.5, 4.5, 3, 4]
    pop = [-1.5, -1, 0, 2, 4, 4, 2.5, 0, -1, -1.5]
    rock = [5, 4, 3, 1.5, -0.5, -1, 0.5, 2.5, 3.5, 4.5]
    bass = [5.5, 4, 3.5, 2.5, 1.5, 0, 0, 0, 0, 0]
    


class Equalizer(pyo.PyoObject):
    def __init__(
        self,
        input: pyo.PyoObject,
        preset: list[float] = None,
        mul: float = 1,
        add: float = 0,
    ):
        pyo.PyoObject.__init__(self, mul, add)

        # keyed by exponent
        self._eq: dict[int, pyo.EQ] = {}
        self._ctrl: dict[int, pyo.SigTo] = {}

        sig = input
        for pow in range(5, 15):
            freq = 2**pow
            # Use a SigTo to avoid glitches
            ctrl = pyo.SigTo(0.0, time=0.05)
            sig = pyo.EQ(sig, freq, boost=ctrl)
            self._eq[pow] = sig
            self._ctrl[pow] = ctrl

        if preset:
            self.set_values(preset)

        self._base_objs = self._eq[14].getBaseObjects()

    def set_values(self, values: list[float] = None) -> None:
        if not values:
            values = [0.0] * 10

        if len(values) != 10:
            raise ValueError("Preset must be exactly 10 values")

        for idx, boost in enumerate(values.items()):
            self.set_boost(5 + idx, boost)

    def set_boost(self, pow_or_freq: int, boost: float) -> None:
        if pow_or_freq not in self._eq:
            pow_or_freq = int(round(math.log2(pow_or_freq)))

        self._ctrl[pow_or_freq].value = boost

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

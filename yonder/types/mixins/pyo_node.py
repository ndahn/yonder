import pyo

from yonder.audio import PlayContext


class PyoNode:
    def pyo(self, ctx: PlayContext) -> pyo.PyoObject:
        return pyo.Sig(0)
    
    def play(self, ctx: PlayContext) -> None:
        pass

    def stop(self, ctx: PlayContext, reset: bool = False) -> None:
        pass

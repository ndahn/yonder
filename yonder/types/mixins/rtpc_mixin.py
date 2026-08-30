from yonder.types.base_types import RTPC
from yonder.audio.audiomath import eval_curve


# NOTE: mixed class must expose an "rtpcs" member
class RtpcMixin:
    # Dummies, just for the type checker
    rtpcs: list[RTPC]

    def get_rtpc_value(self, param: int, x: float, default: float = 0.0) -> float:
        for rtpc in self.rtpcs:
            if rtpc.param_id == param:
                return eval(rtpc.graph_points, x, rtpc.curve_scaling)

        return default

    def get_rtpc_values(
        self, params: dict[int, float], default: float = 0.0
    ) -> dict[int, float]:
        ret = {}

        for rtpc in self.rtpcs:
            x = params.get(rtpc.param_id, default)
            y = eval_curve(rtpc.graph_points, x, rtpc.curve_scaling)
            ret[rtpc.param_id] = y

        return ret

import dearpygui.dearpygui as dpg

from yonder.enums import CurveInterpolation
from yonder.interpolation import interpolate


def draw_constant(
    p0: tuple,
    p1: tuple = None,
    *,
    distance: float = 10**9,
    color: tuple = (255, 255, 255, 255),
    thickness: int = 1,
    parent: str = 0,
    tag: str = 0,
    **kwargs,
):
    """Hold p0[1] across the segment, then step up to p1 at the boundary."""
    if p1:
        step = (p1[0], p0[1])  # flat until the next point, then jump
        return dpg.draw_polyline(
            [p0, step, p1], color=color, thickness=thickness,
            parent=parent, tag=tag, **kwargs,
        )

    end = (p0[0] + distance, p0[1])
    return dpg.draw_line(
        p0, end, color=color, thickness=thickness, parent=parent, tag=tag, **kwargs,
    )


def draw_curve(
    p0: tuple,
    p1: tuple = None,
    interp: CurveInterpolation = CurveInterpolation.Linear,
    *,
    color: tuple = (255, 255, 255, 255),
    thickness: int = 2,
    segments: int = 48,
    parent: str = 0,
    tag: str = 0,
    **kwargs,
):
    """Draw an interpolation curve by sampling the playback interpolator.

    Sampling interpolate() means the editor can never disagree with what is
    actually applied to the audio.
    """
    if p1 is None or interp == CurveInterpolation.Constant:
        return draw_constant(
            p0, p1, color=color, thickness=thickness, parent=parent, tag=tag, **kwargs,
        )

    dx = p1[0] - p0[0]
    dy = p1[1] - p0[1]

    # interpolate(.., 0, 1) returns the normalized shape f(t) in [0, 1]
    pts = []
    for i in range(segments + 1):
        t = i / segments
        f = interpolate(interp, t, 0.0, 1.0)
        pts.append((p0[0] + t * dx, p0[1] + f * dy))

    return dpg.draw_polyline(
        pts, color=color, thickness=thickness, parent=parent, tag=tag, **kwargs,
    )
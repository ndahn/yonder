import math
import dearpygui.dearpygui as dpg

from yonder.enums import CurveInterpolation


def draw_linear(
    p0: tuple[float, float],
    p1: tuple[float, float],
    *,
    color: tuple[int, int, int, int] = (255, 255, 255, 255),
    thickness: int = 1,
    parent: str = 0,
    tag: str = 0,
    **kwargs,
):
    """Straight line from (p0[0],p0[1]) to (p1[0],p1[1])."""
    return dpg.draw_line(
        p0, p1, color=color, thickness=thickness, parent=parent, tag=tag, **kwargs
    )


def draw_constant(
    p0: tuple[float, float],
    p1: tuple[float, float] = None,
    *,
    distance: float = 10**9,
    color: tuple[int, int, int, int] = (255, 255, 255, 255),
    thickness: int = 1,
    parent: str = 0,
    tag: str = 0,
    **kwargs,
):
    """Flat horizontal line at p0[1] from p0[0] to p1[0]."""
    if p1:
        pm = (p1[0], p0[1])
        return dpg.draw_polyline(
            [p0, pm, p1],
            color=color,
            thickness=thickness,
            parent=parent,
            tag=tag,
            **kwargs,
        )
    else:
        p1 = (p0[0] + distance, p0[1])
        return dpg.draw_line(
            p0,
            p1,
            color=color,
            thickness=thickness,
            parent=parent,
            tag=tag,
            **kwargs,
        )


def draw_log(
    p0: tuple[float, float],
    p1: tuple[float, float],
    strength,
    *,
    color: tuple[int, int, int, int] = (255, 255, 255, 255),
    thickness: int = 1,
    segments: int = 32,
    parent: str = 0,
    tag: str = 0,
    **kwargs,
):
    """
    Logarithmic ease-in: slow start, fast finish.

    cp1 is pulled far along the x-axis while staying at p0[1] — this stretches
    the horizontal motion early so y barely changes at first.
    cp2 sits at the endpoint, giving a clean arrival.

    strength [0,1]: 0 → nearly linear, 1 → very pronounced log bend.
    """
    dx = p1[0] - p0[0]
    cp1 = (p0[0] + dx * (1.0 - strength), p1[1])
    cp2 = p1
    return dpg.draw_bezier_cubic(
        p0,
        cp1,
        cp2,
        p1,
        color=color,
        thickness=thickness,
        parent=parent,
        segments=segments,
        tag=tag,
        **kwargs,
    )


def draw_exp(
    p0: tuple[float, float],
    p1: tuple[float, float],
    strength,
    *,
    color: tuple[int, int, int, int] = (255, 255, 255, 255),
    thickness: int = 1,
    segments: int = 32,
    parent: str = 0,
    tag: str = 0,
    **kwargs,
):
    """
    Exponential ease-out: fast start, slow finish.

    cp1 is placed close to p0[0] but already at p1[1] — the curve immediately
    shoots upward while x has barely advanced, giving the steep initial rise.
    cp2 sits at the endpoint, giving a clean arrival.

    strength [0,1]: 0 → nearly linear, 1 → very pronounced exp bend.
    """
    dx = p1[0] - p0[0]
    cp1 = (p0[0] + dx * strength, p0[1])
    cp2 = p1
    return dpg.draw_bezier_cubic(
        p0,
        cp1,
        cp2,
        p1,
        color=color,
        thickness=thickness,
        parent=parent,
        segments=segments,
        tag=tag,
        **kwargs,
    )


def draw_scurve(
    p0: tuple[float, float],
    p1: tuple[float, float],
    *,
    color: tuple[int, int, int, int] = (255, 255, 255, 255),
    thickness: int = 1,
    segments: int = 32,
    parent: str = 0,
    tag: str = 0,
    **kwargs,
):
    """
    Classic cubic S-curve (ease-in-out): slow start, fast middle, slow end.

    cp1 at (p0[0]+dx/3, p0[1]) -> horizontal exit (slow start).
    cp2 at (p1[0]-dx/3, p1[1]) -> horizontal entry (slow end).
    The middle third of the horizontal span is where the steep climb happens.
    """
    dx = p1[0] - p0[0]
    cp1 = (p0[0] + dx / 2.0, p0[1])
    cp2 = (p1[0] - dx / 2.0, p1[1])
    return dpg.draw_bezier_cubic(
        p0,
        cp1,
        cp2,
        p1,
        color=color,
        thickness=thickness,
        parent=parent,
        segments=segments,
        tag=tag,
        **kwargs,
    )


def draw_inv_scurve(
    p0: tuple[float, float],
    p1: tuple[float, float],
    *,
    color: tuple[int, int, int, int] = (255, 255, 255, 255),
    thickness: int = 1,
    segments: int = 32,
    parent: str = 0,
    tag: str = 0,
    **kwargs,
):
    """
    Inverted S-curve (ease-out-in): fast start, slow middle, fast end.

    cp1 at (p0[0]+dx*0.1, p1[1]) -> tangent shoots almost vertically at start (fast).
    cp2 at (p1[0]-dx*0.1, p0[1]) -> tangent arrives almost vertically at end (fast).
    The curve plateaus near the midpoint, producing the slow middle section.
    """
    dx = p1[0] - p0[0]
    cp1 = (p0[0] + dx * 0.33, p1[1])
    cp2 = (p1[0] - dx * 0.33, p0[1])
    return dpg.draw_bezier_cubic(
        p0,
        cp1,
        cp2,
        p1,
        color=color,
        thickness=thickness,
        parent=parent,
        segments=segments,
        tag=tag,
        **kwargs,
    )


def draw_sine(
    p0: tuple[float, float],
    p1: tuple[float, float],
    reciprocal: bool = False,
    *,
    color: tuple[int, int, int, int] = (255, 255, 255, 255),
    thickness: int = 1,
    segments: int = 32,
    parent: str = 0,
    tag: str = 0,
    **kwargs,
):
    """
    Sine arch: bows in the direction of travel between endpoints.
    For ascending segments (p1 above p0), bows upward.
    For descending segments (p1 below p0), bows downward.
    This matches Wwise's Sine interpolation behavior, which follows
    the shape of the first quarter of a sine wave between two points,
    always curving away from a straight line in the direction of travel.
    Uses a cubic Bézier whose control points are derived by matching the
    tangent of sin(π·t) at t=0 (slope = π), giving cp_offset = (π/3)·arch_h.
    arch_h is 35% of the horizontal span so the bow looks proportional at any size.
    """
    dx = p1[0] - p0[0]
    dy = p1[1] - p0[1]
    arch_h = dx * 0.35

    # Flip arch direction based on whether segment goes up or down.
    # In screen space, Y increases downward, so:
    #   - descending segment (dy > 0): bow downward → add cp_off
    #   - ascending segment  (dy < 0): bow upward   → subtract cp_off
    arch_sign = 1.0 if dy >= 0 else -1.0
    if reciprocal:
        arch_sign *= -1

    cp_off = arch_sign * (math.pi / 3.0) * arch_h
    cp1 = (p0[0] + dx / 3.0, p0[1] + dy / 3.0 - cp_off)
    cp2 = (p1[0] - dx / 3.0, p1[1] - dy / 3.0 - cp_off)

    return dpg.draw_bezier_cubic(
        (p0[0], p0[1]),
        cp1,
        cp2,
        (p1[0], p1[1]),
        color=color,
        thickness=thickness,
        parent=parent,
        segments=segments,
        tag=tag,
        **kwargs,
    )


_LOG_STRENGTH = {CurveInterpolation.Log1: 0.5, CurveInterpolation.Log3: 0.8}
_EXP_STRENGTH = {CurveInterpolation.Exp1: 0.5, CurveInterpolation.Exp3: 0.8}


def draw_curve(
    p0: tuple,
    p1: tuple | None = None,
    interp: CurveInterpolation = CurveInterpolation.Linear,
    *,
    color: tuple = (255, 255, 255, 255),
    thickness: int = 2,
    segments: int = 32,
    parent: str = 0,
    tag: str = 0,
    **kwargs,
):
    """
    Draw a named interpolation curve onto a DearPyGui draw-layer.

    Parameters
    ----------
    p0 : (float, float)
        Start point in screen/canvas coordinates (x, y).
    p1 : (float, float) | None
        End point. If None the curve is drawn as a flat constant line
        extending 100 px to the right of p1.
    interp : str
        One of the INTERP_TYPES strings (case-sensitive).
    color : (r, g, b, a)
        RGBA colour tuple, 0-255 each channel.
    thickness : float
        Line thickness in pixels.
    tag : str | int | None
        Optional DPG tag for the resulting item.

    Returns
    -------
    int | str
        The DPG item id/tag of the drawn primitive.
    """
    if p1 is None:
        return draw_constant(
            p0,
            distance=10**9,
            color=color,
            thickness=thickness,
            parent=parent,
            tag=tag,
            **kwargs,
        )

    if interp == CurveInterpolation.Linear:
        return draw_linear(
            p0, p1, color=color, thickness=thickness, parent=parent, tag=tag, **kwargs
        )

    if interp == CurveInterpolation.Constant:
        return draw_constant(
            p0,
            p1,
            color=color,
            thickness=thickness,
            parent=parent,
            tag=tag,
            **kwargs,
        )

    if interp in _LOG_STRENGTH:
        return draw_log(
            p0,
            p1,
            _LOG_STRENGTH[interp],
            color=color,
            thickness=thickness,
            parent=parent,
            segments=segments,
            tag=tag,
            **kwargs,
        )

    if interp in _EXP_STRENGTH:
        return draw_exp(
            p0,
            p1,
            _EXP_STRENGTH[interp],
            color=color,
            thickness=thickness,
            parent=parent,
            segments=segments,
            tag=tag,
            **kwargs,
        )

    if interp == CurveInterpolation.SCurve:
        return draw_scurve(
            p0,
            p1,
            color=color,
            thickness=thickness,
            parent=parent,
            segments=segments,
            tag=tag,
            **kwargs,
        )

    if interp == CurveInterpolation.InvSCurve:
        return draw_inv_scurve(
            p0,
            p1,
            color=color,
            thickness=thickness,
            parent=parent,
            segments=segments,
            tag=tag,
            **kwargs,
        )

    if interp == CurveInterpolation.Sine:
        return draw_sine(
            p0,
            p1,
            False,
            color=color,
            thickness=thickness,
            parent=parent,
            segments=segments,
            tag=tag,
            **kwargs,
        )

    if interp == CurveInterpolation.SineRecip:
        return draw_sine(
            p0,
            p1,
            True,
            color=color,
            thickness=thickness,
            parent=parent,
            segments=segments,
            tag=tag,
            **kwargs,
        )

    raise ValueError(f"Unknown interpolation type {interp}")


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    CANVAS_W, CANVAS_H = 900, 620
    COL_COUNT = 4
    PAD = 30
    CELL_W = (CANVAS_W - PAD) // COL_COUNT
    CELL_H = (CANVAS_H - PAD) // 3

    COLORS = {
        CurveInterpolation.Linear: (100, 200, 255, 255),
        CurveInterpolation.Log1: (255, 160, 60, 255),
        CurveInterpolation.Log3: (220, 80, 0, 255),
        CurveInterpolation.SCurve: (80, 220, 120, 255),
        CurveInterpolation.InvSCurve: (40, 180, 80, 255),
        CurveInterpolation.Exp1: (200, 100, 255, 255),
        CurveInterpolation.Exp3: (140, 20, 200, 255),
        CurveInterpolation.Sine: (255, 220, 60, 255),
        CurveInterpolation.SineRecip: (255, 220, 140, 255),
        CurveInterpolation.Constant: (180, 180, 180, 255),
    }

    dpg.create_context()
    dpg.create_viewport(
        title="draw_curve demo", width=CANVAS_W + 20, height=CANVAS_H + 60
    )

    with dpg.window(
        label="Interpolation Curves",
        width=CANVAS_W + 20,
        height=CANVAS_H + 50,
        no_resize=True,
    ):
        with dpg.drawlist(width=CANVAS_W, height=CANVAS_H) as dl:
            with dpg.draw_layer(parent=dl):
                for idx, curve_type in enumerate(CurveInterpolation):
                    col = idx % COL_COUNT
                    row = idx // COL_COUNT
                    ox = PAD + col * CELL_W
                    oy = PAD + row * CELL_H

                    dpg.draw_rectangle(
                        pmin=(ox, oy),
                        pmax=(ox + CELL_W - PAD, oy + CELL_H - PAD),
                        color=(60, 60, 70, 200),
                        fill=(40, 40, 50, 120),
                    )
                    dpg.draw_line(
                        (ox + 8, oy + CELL_H - PAD - 8),
                        (ox + CELL_W - PAD - 8, oy + CELL_H - PAD - 8),
                        color=(100, 100, 110, 80),
                        thickness=1,
                    )
                    dpg.draw_line(
                        (ox + 8, oy + 8),
                        (ox + 8, oy + CELL_H - PAD - 8),
                        color=(100, 100, 110, 80),
                        thickness=1,
                    )

                    # Sin uses start y = end y (it's an arch)
                    if curve_type == CurveInterpolation.Sine:
                        mid_y = (oy + 8 + oy + CELL_H - PAD - 8) / 2
                        p0 = (ox + 8, oy + CELL_H - PAD - 8)
                        p1 = (ox + CELL_W - PAD - 8, oy + CELL_H - PAD - 8)
                    else:
                        p0 = (ox + 8, oy + CELL_H - PAD - 8)
                        p1 = (ox + CELL_W - PAD - 8, oy + 8)

                    draw_curve(
                        p0, p1, interp=curve_type, color=COLORS[curve_type], thickness=2
                    )

                    dpg.draw_text(
                        (ox + 10, oy + CELL_H - PAD - 22),
                        curve_type.name,
                        color=(220, 220, 220, 220),
                        size=13,
                    )

    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()

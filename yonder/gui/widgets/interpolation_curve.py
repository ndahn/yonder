from typing import Any, Callable
from dearpygui import dearpygui as dpg
from copy import deepcopy

from yonder.enums import CurveInterpolation
from yonder.types.rewwise_base_types import RTPCGraphPoint
from yonder.gui import style
from yonder.gui.helpers import GraphCurve
from .draw_curve import draw_curve


interpolation_colors: dict[CurveInterpolation, style.Color] = {
    CurveInterpolation.Constant: style.light_grey,
    CurveInterpolation.Linear: style.white,
    CurveInterpolation.SCurve: style.light_green,
    CurveInterpolation.InvSCurve: style.green,
    CurveInterpolation.Log1: style.pink,
    CurveInterpolation.Log3: style.purple,
    CurveInterpolation.Exp1: style.light_blue,
    CurveInterpolation.Exp3: style.blue,
    CurveInterpolation.Sine: style.light_red,
    CurveInterpolation.SineRecip: style.red,
}


def add_interpolation_curve(
    initial_curve: GraphCurve,
    on_curve_changed: Callable[[str, GraphCurve, Any], None] = None,
    *,
    tag: str = None,
    user_data: Any = None,
) -> str:
    if not tag:
        tag = dpg.generate_uuid()

    curve: GraphCurve = deepcopy(initial_curve)
    dirty: bool = True
    drag_points: list[int] = []
    hovered: int = -1
    selected: int = 0

    def on_point_moved(sender: str, app_data: Any, point_idx: int) -> None:
        x, y = dpg.get_value(sender)
        p = curve[point_idx]
        p.x = x
        p.y = y

        dpg.configure_item(f"{tag}_series", x=list(curve.x), y=list(curve.y))
        on_point_selected(point_idx)

        if on_curve_changed:
            on_curve_changed(tag, curve, user_data)

    def on_interpolation_changed(sender: str, interp: str, cb_user_data: Any) -> None:
        nonlocal dirty

        if selected < 0:
            return

        dirty = True
        curve[selected].interpolation = CurveInterpolation[interp]
        if on_curve_changed:
            on_curve_changed(tag, curve, user_data)

    def on_point_value_changed(sender: str, value: float, field: str) -> None:
        nonlocal dirty

        if selected < 0:
            return

        if field == "x":
            curve[selected].from_ = value
        elif field == "y":
            curve[selected].to = value
        else:
            raise ValueError(f"Bug: unexpected field {field}")

        dirty = True
        if on_curve_changed:
            on_curve_changed(tag, curve, user_data)

    def on_add_point() -> None:
        nonlocal selected

        if selected < 0:
            selected = len(curve - 1)

        p0 = curve[selected].coords
        if selected < len(curve) - 1:
            p1 = curve[selected + 1].coords
        else:
            p1 = (p0[0] * 2, p0[1])

        x = (p0[0] + p1[0]) / 2
        y = (p1[0] + p1[1]) / 2
        curve.points.insert(selected + 1, RTPCGraphPoint(x, y, CurveInterpolation.Linear))

        if on_curve_changed:
            on_curve_changed(tag, curve, user_data)

        on_point_selected(selected + 1)
        regenerate()

    def on_remove_point() -> None:
        nonlocal selected

        if len(curve) <= 2:
            return

        curve.points.pop(selected)
        if on_curve_changed:
            on_curve_changed(tag, curve, user_data)

        on_point_selected(max(0, selected - 1))
        regenerate()

    def on_point_selected(idx: int) -> None:
        nonlocal selected

        p = curve[idx]
        selected = idx
        dpg.set_value(f"{tag}_point_label", f"p{idx}")
        dpg.set_value(f"{tag}_point_interpolation", p.interpolation)
        dpg.set_value(f"{tag}_point_x", p.x)
        dpg.set_value(f"{tag}_point_y", p.y)

    def render_curve(sender: str, series_data: list[dict], user_data: Any) -> None:
        nonlocal hovered, dirty

        # Save some cpu cycles when no updates are needed
        if not (
            dirty
            or dpg.is_mouse_button_down(dpg.mvMouseButton_Left)
            or dpg.is_item_hovered(dpg.get_item_parent(f"{tag}_canvas"))
        ):
            return

        dirty = False
        helper_data = series_data[0]
        transformed_x = series_data[1]
        transformed_y = series_data[2]

        hovered = -1
        mouse_x = helper_data["MouseX_PixelSpace"]
        mouse_y = helper_data["MouseY_PixelSpace"]

        dpg.delete_item(sender, children_only=True, slot=2)
        dpg.push_container_stack(sender)

        # Draw a constant line to the first point
        first = (transformed_x[0], transformed_y[0])
        draw_curve(
            (first[0] - 10**9, first[1]),
            first,
            CurveInterpolation.Linear,
            color=style.light_grey,
        )

        last = (transformed_x[-1], transformed_y[-1])
        draw_curve(last, None, CurveInterpolation.Constant, color=style.light_grey)

        for i, (x, y, interp) in enumerate(
            zip(transformed_x, transformed_y, curve.interp)
        ):
            color = interpolation_colors.get(interp, style.white)
            next_point = (
                (transformed_x[i + 1], transformed_y[i + 1])
                if i < len(transformed_x) - 1
                else None
            )

            # Interpolation curve
            draw_curve((x, y), next_point, interp, color=color)

            if hovered < 0 and x - 5 <= mouse_x <= x + 5 and y - 5 <= mouse_y <= y + 5:
                hovered = i

        dpg.pop_container_stack()

    def regenerate() -> None:
        nonlocal dirty

        dpg.delete_item(f"{tag}_yaxis", children_only=True, slot=1)
        for dp in drag_points:
            dpg.delete_item(dp)

        drag_points.clear()
        dirty = True

        dpg.add_custom_series(
            list(curve.x),
            list(curve.y),
            list(curve.interp),
            callback=render_curve,
            tooltip=True,
            parent=f"{tag}_yaxis",
            tag=f"{tag}_series",
        )

        for i, p in enumerate(curve):
            # Point marker
            color = interpolation_colors.get(p.interpolation, style.white)
            dp = dpg.add_drag_point(
                label=f"p{i} ({p.interpolation})",
                default_value=p.coords,
                color=color,
                thickness=3,
                callback=on_point_moved,
                parent=f"{tag}_canvas",
                user_data=i,
            )
            drag_points.append(dp)

    def on_mouse_click() -> None:
        if not dpg.does_item_exist(tag):
            # Assume this widget has been destroyed
            dpg.delete_item(handler_reg)
            return

        if not dpg.is_item_hovered(tag):
            return

        if hovered >= 0:
            on_point_selected(hovered)

    with dpg.group(tag=tag):
        with dpg.plot(width=-1, tag=f"{tag}_canvas"):
            dpg.add_plot_axis(
                dpg.mvXAxis,
                label="Input",
                tag=f"{tag}_xaxis",
            )
            dpg.add_plot_axis(
                dpg.mvYAxis,
                label="Output",
                tag=f"{tag}_yaxis",
            )

        with dpg.group(horizontal=True):
            dpg.add_text("p0", tag=f"{tag}_point_label")
            dpg.add_combo(
                [c.name for c in CurveInterpolation],
                default_value=curve[0].interpolation,
                width=100,
                callback=on_interpolation_changed,
                tag=f"{tag}_point_interpolation",
            )
            dpg.add_input_float(
                default_value=curve[0].from_,
                width=140,
                min_value=0.0,
                min_clamped=True,
                callback=on_point_value_changed,
                tag=f"{tag}_point_x",
                user_data="x",
            )
            dpg.add_input_float(
                default_value=curve[0].to,
                width=140,
                min_value=0.0,
                min_clamped=True,
                callback=on_point_value_changed,
                tag=f"{tag}_point_y",
                user_data="y",
            )
            dpg.add_text("|")
            dpg.add_button(
                label="Add",
                callback=on_add_point,
            )
            dpg.add_button(
                label="Remove",
                callback=on_remove_point,
            )

    with dpg.handler_registry() as handler_reg:
        dpg.add_mouse_click_handler(callback=on_mouse_click)

    regenerate()
    dpg.split_frame()
    dpg.fit_axis_data(f"{tag}_yaxis")

    return tag

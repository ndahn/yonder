from typing import Any, Callable
from copy import deepcopy
from dearpygui import dearpygui as dpg

from yonder.enums import CurveInterpolation
from yonder.types.base_types import RTPCGraphPoint
from yonder.gui import style
from yonder.gui.localization import µ
from yonder.gui.helpers import GraphCurve
from .draw_curve import draw_curve
from .dpg_item import DpgItem


# Module-level color map — shared across all instances
interpolation_colors: dict[CurveInterpolation, style.RGBA] = {
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


class add_interpolation_curve(DpgItem):
    """An interactive piecewise interpolation curve editor for Dear PyGui.

    Renders a plot with draggable control points and a custom series that
    draws each segment using its interpolation type. A toolbar below the plot
    lets the user select the active point's interpolation mode and edit its
    x/y values numerically. Points can be added (midpoint between selected and
    next) or removed (minimum 2 points enforced).

    The curve is deep-copied on construction; mutations are internal. The
    caller receives the live ``GraphCurve`` instance on each change.

    Parameters
    ----------
    initial_curve : GraphCurve
        Curve to deep-copy as the starting state.
    on_curve_changed : callable, optional
        Fired as ``on_curve_changed(tag, curve, user_data)`` on any edit.
    tag : int or str, optional
        Explicit tag; auto-generated if None.
    user_data : any
        Passed through to ``on_curve_changed``.
    """

    def __init__(
        self,
        initial_curve: GraphCurve,
        on_curve_changed: Callable[[str, GraphCurve, Any], None] = None,
        *,
        tag: int | str = None,
        user_data: Any = None,
    ) -> None:
        super().__init__(tag if tag else dpg.generate_uuid())

        self._curve: GraphCurve = deepcopy(initial_curve)
        self._on_curve_changed = on_curve_changed
        self._user_data = user_data

        # Render state
        self._dirty: bool = True
        self._first_draw: bool = True
        self._drag_points: list[int] = []
        self._hovered: int = -1
        self._selected: int = 0
        self._handler_reg: int | str = None

        self._build()

        with dpg.handler_registry() as reg:
            dpg.add_mouse_click_handler(callback=self._on_mouse_click)
        self._handler_reg = reg

        self.regenerate()
        dpg.split_frame()
        dpg.fit_axis_data(self._t("yaxis"))

    # === Build =========================================================

    def _build(self) -> None:
        p0 = self._curve[0]
        with dpg.group(tag=self._tag):
            with dpg.plot(width=-1, tag=self._t("canvas")):
                dpg.add_plot_axis(dpg.mvXAxis, label=µ("Input"), tag=self._t("xaxis"))
                dpg.add_plot_axis(dpg.mvYAxis, label=µ("Output"), tag=self._t("yaxis"))

            with dpg.group(horizontal=True):
                dpg.add_text("p0", tag=self._t("point_label"))
                dpg.add_combo(
                    sorted([c.name for c in CurveInterpolation]),
                    default_value=p0.interpolation.name,
                    width=100,
                    callback=self._on_interpolation_changed,
                    tag=self._t("point_interpolation"),
                )
                dpg.add_input_float(
                    default_value=p0.from_,
                    width=140,
                    min_value=0.0,
                    min_clamped=True,
                    callback=self._on_point_value_changed,
                    user_data="x",
                    tag=self._t("point_x"),
                )
                dpg.add_input_float(
                    default_value=p0.to,
                    width=140,
                    min_value=0.0,
                    min_clamped=True,
                    callback=self._on_point_value_changed,
                    user_data="y",
                    tag=self._t("point_y"),
                )
                dpg.add_text("|")
                dpg.add_button(
                    label=µ("Add", "button"), callback=self._on_add_point, tag=self._t("add")
                )
                dpg.add_button(
                    label=µ("Remove", "button"),
                    callback=self._on_remove_point,
                    tag=self._t("remove"),
                )

    # === DPG callbacks =================================================

    def _on_point_moved(self, sender: str, app_data: Any, point_idx: int) -> None:
        x, y = dpg.get_value(sender)
        p = self._curve[point_idx]
        p.from_ = x
        p.to = y

        dpg.configure_item(
            self._t("series"), x=list(self._curve.x), y=list(self._curve.y)
        )
        self.select_point(point_idx)

        if self._on_curve_changed:
            self._on_curve_changed(self._tag, self._curve, self._user_data)

    def _on_interpolation_changed(
        self, sender: str, interp: str, cb_user_data: Any
    ) -> None:
        if self._selected < 0:
            return

        self._dirty = True
        self._curve[self._selected].interpolation = CurveInterpolation[interp]
        if self._on_curve_changed:
            self._on_curve_changed(self._tag, self._curve, self._user_data)

    def _on_point_value_changed(self, sender: str, value: float, field: str) -> None:
        if self._selected < 0:
            return

        if field == "x":
            self._curve[self._selected].from_ = value
        elif field == "y":
            self._curve[self._selected].to = value
        else:
            raise ValueError(f"Bug: unexpected field {field}")

        self._dirty = True
        if self._on_curve_changed:
            self._on_curve_changed(self._tag, self._curve, self._user_data)

    def _on_add_point(self) -> None:
        if self._selected < 0:
            self._selected = len(self._curve) - 1

        p0 = self._curve[self._selected].coords
        if self._selected < len(self._curve) - 1:
            p1 = self._curve[self._selected + 1].coords
        else:
            p1 = (p0[0] * 2, p0[1])

        if p0 == p1:
            x, y = p0[0] + 1.0, p0[1]
        else:
            x = (p0[0] + p1[0]) / 2
            y = (p0[1] + p1[1]) / 2

        self._curve.points.insert(
            self._selected + 1,
            RTPCGraphPoint(x, y, CurveInterpolation.Linear),
        )

        if self._on_curve_changed:
            self._on_curve_changed(self._tag, self._curve, self._user_data)

        self.select_point(self._selected + 1)
        self.regenerate()

    def _on_remove_point(self) -> None:
        if len(self._curve) <= 2:
            return

        self._curve.points.pop(self._selected)
        if self._on_curve_changed:
            self._on_curve_changed(self._tag, self._curve, self._user_data)

        self.select_point(max(0, self._selected - 1))
        self.regenerate()

    def _on_mouse_click(self) -> None:
        if not dpg.does_item_exist(self._tag):
            dpg.delete_item(self._handler_reg)
            return

        if not dpg.is_item_hovered(self._tag):
            return

        if self._hovered >= 0:
            self.select_point(self._hovered)

    def _render_curve(self, sender: str, series_data: list, ud: Any) -> None:
        # NOTE this will crash if breakpoints are set anywhere in here!

        # Save some cpu cycles when no updates are needed
        if not self._first_draw and not (
            self._dirty
            or dpg.is_mouse_button_down(dpg.mvMouseButton_Left)
            or dpg.is_item_hovered(dpg.get_item_parent(self._t("canvas")))
        ):
            return

        self._first_draw = False
        self._dirty = False
        self._hovered = -1

        helper_data = series_data[0]
        transformed_x = series_data[1]
        transformed_y = series_data[2]
        mouse_x = helper_data["MouseX_PixelSpace"]
        mouse_y = helper_data["MouseY_PixelSpace"]

        dpg.delete_item(sender, children_only=True, slot=2)
        dpg.push_container_stack(sender)

        # Flat extension before the first point
        first = (transformed_x[0], transformed_y[0])
        draw_curve(
            (first[0] - 10**9, first[1]),
            first,
            CurveInterpolation.Linear,
            color=style.light_grey,
        )

        # Flat extension after the last point
        last = (transformed_x[-1], transformed_y[-1])
        draw_curve(last, None, CurveInterpolation.Constant, color=style.light_grey)

        for i, (x, y, interp) in enumerate(
            zip(transformed_x, transformed_y, self._curve.interp)
        ):
            color = interpolation_colors.get(interp, style.white)
            next_pt = (
                (transformed_x[i + 1], transformed_y[i + 1])
                if i < len(transformed_x) - 1
                else None
            )
            draw_curve((x, y), next_pt, interp, color=color)

            if (
                self._hovered < 0
                and x - 5 <= mouse_x <= x + 5
                and y - 5 <= mouse_y <= y + 5
            ):
                self._hovered = i

        dpg.pop_container_stack()

    # === Public ========================================================

    def select_point(self, idx: int) -> None:
        """Select a control point and update the toolbar widgets."""
        p = self._curve[idx]
        self._selected = idx
        dpg.set_value(self._t("point_label"), f"p{idx}")
        dpg.set_value(self._t("point_interpolation"), p.interpolation.name)
        dpg.set_value(self._t("point_x"), p.from_)
        dpg.set_value(self._t("point_y"), p.to)

    def regenerate(self) -> None:
        """Rebuild drag points and the custom series from the current curve."""
        dpg.delete_item(self._t("yaxis"), children_only=True, slot=1)
        for dp in self._drag_points:
            dpg.delete_item(dp)
        self._drag_points.clear()
        self._dirty = True

        dpg.add_custom_series(
            list(self._curve.x),
            list(self._curve.y),
            2,
            callback=self._render_curve,
            tooltip=True,
            parent=self._t("yaxis"),
            tag=self._t("series"),
        )

        for i, p in enumerate(self._curve):
            color = interpolation_colors.get(p.interpolation, style.white)
            dp = dpg.add_drag_point(
                label=f"p{i} ({p.interpolation})",
                default_value=p.coords,
                color=color,
                thickness=3,
                callback=self._on_point_moved,
                parent=self._t("canvas"),
                user_data=i,
            )
            self._drag_points.append(dp)

    @property
    def curve(self) -> GraphCurve:
        """Live curve instance (not a copy)."""
        return self._curve

    def destroy(self) -> None:
        """Delete DPG items owned by this widget."""
        if dpg.does_item_exist(self._tag):
            dpg.delete_item(self._tag)
        if self._handler_reg and dpg.does_item_exist(self._handler_reg):
            dpg.delete_item(self._handler_reg)

    def __del__(self) -> None:
        self.destroy()

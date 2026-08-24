from typing import Any, Callable
import math
from dearpygui import dearpygui as dpg

from yonder.types import Attenuation
from yonder.gui import style
from yonder.gui.localization import µ
from .dpg_draw import draw_circle_segment
from .dpg_item import DpgItem


class add_attenuation_plot(DpgItem):
    def __init__(
        self,
        attenuation: Attenuation,
        on_position_changed: Callable[[str, tuple[float, float], Any], None] = None,
        *,
        distance: float = 0.0,
        angle: float = 0.0,
        max_distance: float = 100.0,
        rotation_offset: float = 90.0,
        allow_position_change: bool = True,
        tag: str = None,
        user_data: Any = None,
    ) -> None:
        super().__init__(tag)
        self._user_data = user_data

        self._attenuation = attenuation
        self._on_position_changed = on_position_changed
        self._rotation_offset = rotation_offset
        self._allow_position_change = allow_position_change
        self._dirty: bool = True
        self._first_draw: bool = True

        self._distance = distance
        self._angle = angle
        self._max_distance = max_distance

        self._build()
        self.regenerate()
        dpg.split_frame()

    # === Build =========================================================

    def _build(self) -> None:
        with dpg.group(tag=self._tag):
            with dpg.plot(width=-1, tag=self._t("canvas")):
                dpg.add_plot_axis(dpg.mvXAxis, no_label=True, tag=self._t("xaxis"))
                dpg.add_plot_axis(dpg.mvYAxis, no_label=True, tag=self._t("yaxis"))

                dpg.add_custom_series(
                    [0.0, self._max_distance],
                    [0.0, self._max_distance],
                    2,
                    callback=self._render_background,
                    tag=self._t("background_series"),
                )

                dpg.add_drag_point(
                    color=style.red,
                    default_value=(0, 0),
                    callback=self._on_point_moved,
                    tag=self._t("drag_point"),
                )
                with dpg.group(parent=dpg.last_item()):
                    dpg.add_button(
                        label=µ("Reset"), callback=lambda s, a, u: self.reset()
                    )

            dpg.bind_item_theme(self._t("canvas"), style.themes.plot_fit_padding)
            dpg.add_text("", tag=self._t("info_text"))

    # === DPG callbacks =================================================

    def _on_point_moved(self, sender: str, app_data: Any, cb_user_data: Any) -> None:
        x, y = dpg.get_value(sender)
        x = max(-self._max_distance, min(self._max_distance, x))
        y = max(-self._max_distance, min(self._max_distance, y))
        dist = math.sqrt(x * x + y * y)
        phi = math.degrees(math.atan2(y, x))

        if self._on_position_changed:
            self._on_position_changed(self._tag, (dist, phi), self._user_data)

        dpg.set_value(sender, (x, y))

    def _render_background(self, sender: str, series_data: list, ud: Any) -> None:
        # Save some cpu cycles when no updates are needed
        if not (
            self._dirty or self._first_draw or dpg.is_item_visible(self._t("canvas"))
        ):
            return

        # Allow for a second render pass after startup to settle axis ranges
        if self._first_draw:
            self._first_draw = False
        else:
            self._dirty = False

        transformed_x = series_data[1]
        transformed_y = series_data[2]
        center = (transformed_x[0], transformed_y[0])
        radius = transformed_x[1]

        dpg.delete_item(sender, children_only=True, slot=2)
        dpg.push_container_stack(sender)

        dpg.draw_circle(center, radius, thickness=1)

        if self._attenuation.is_cone_enabled:
            cone = self._attenuation.cone_params
            offset = self._rotation_offset
            draw_circle_segment(
                center,
                radius,
                offset - cone.outside_degrees / 2,
                offset + cone.outside_degrees / 2,
                fill=(255, 255, 255, 96),
            )
            draw_circle_segment(
                center,
                radius,
                offset - cone.inside_degrees / 2,
                offset + cone.inside_degrees / 2,
                fill=(255, 255, 255, 96),
                thickness=2,
            )

        dpg.pop_container_stack()

    # === Public ========================================================

    def set_distance_angle(
        self, dist: float, angle: float, fire_callback: bool = True
    ) -> None:
        x = dist * math.cos(angle)
        y = dist * math.sin(angle)
        dpg.set_value(self._t("drag_point"), (x, y))

        if fire_callback and self._on_position_changed:
            self._on_position_changed(self.tag, (dist, angle), self._user_data)

    def reset(self, fire_callback: bool = True) -> None:
        self.set_distance_angle(0, 0, fire_callback)

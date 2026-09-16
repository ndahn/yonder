from typing import Any, Callable
from dearpygui import dearpygui as dpg

from yonder.enums import PropID, Units
from yonder.gui.localization import µ
from yonder.gui import style
from yonder.gui.icons import Icons
from yonder.gui.helpers import center_window
from .dpg_item import DpgItem
from .select_node import add_select_node


class add_properties_table(DpgItem):
    """An editable key-value table for ``PropID`` properties.

    Each row has a combo to select the property type and a float input for
    its value. Adding a row picks the first unused ``PropID``; the type combo
    only shows props not already in use. The passed-in ``properties`` dict is
    mutated in place; callbacks receive a shallow copy.

    Parameters
    ----------
    properties : dict of PropID to float
        Initial properties; mutated directly by the widget.
    on_value_changed : callable
        Fired as ``on_value_changed(tag, props_copy, user_data)`` on any edit.
    label : str, optional
        Text label rendered above the table.
    tag : int or str
        Explicit tag; auto-generated if 0 or None.
    user_data : any
        Passed through to ``on_value_changed``.
    """

    def __init__(
        self,
        properties: dict[PropID, Any],
        on_values_changed: Callable[[str, dict[PropID, Any], Any], None],
        *,
        prop_ranges_enabled: bool = False,
        prop_ranges: dict[PropID, tuple[float, float]] = None,
        on_prop_ranges_changed: Callable[
            [str, dict[PropID, tuple[float, float]], Any], None
        ] = None,
        label: str = "Properties",
        tag: str | int = 0,
        user_data: Any = None,
    ) -> None:
        super().__init__(tag)

        self._properties = properties
        self._prop_ranges_enabled = prop_ranges_enabled
        self._on_values_changed = on_values_changed
        self._prop_ranges = prop_ranges or {}
        self._on_prop_ranges_changed = on_prop_ranges_changed
        self._user_data = user_data

        self._build(label)
        self.refresh()

    # === Build =========================================================

    def _build(self, label: str) -> None:
        if label:
            dpg.add_text(label)

        with dpg.table(
            header_row=False,
            policy=dpg.mvTable_SizingFixedFit,
            borders_outerH=True,
            borders_outerV=True,
            tag=self._tag,
        ):
            dpg.add_table_column(
                label=µ("Property"), width_stretch=True, init_width_or_weight=100
            )
            dpg.add_table_column(
                label=µ("Value"), width_stretch=True, init_width_or_weight=100
            )
            dpg.add_table_column(label="", width_fixed=True)

    # === Internal ======================================================

    def _get_available_props(self, exclude: PropID = None) -> list[PropID]:
        used = set(self._properties.keys())
        if exclude:
            used.discard(exclude)
        return [k for k in PropID if k not in used]

    def _get_prop_range(self, prop: PropID) -> tuple[float, float, str, float]:
        unit = prop.unit

        if unit == Units.Count:
            return (0, 100, "%.0f", 0.1)

        if unit == Units.Ratio:
            return (0, 1, "%.3f", 0.02)

        if unit == Units.Percent:
            return (0, 100, "%.3f", 0.1)

        if unit == Units.ID:
            return (0, 10e10 - 1, "%.0f", 0.02)

        if unit == Units.dB:
            return (-96, 96, "%0.3f", 0.02)

        if unit == Units.Hz:
            return (-48000, 48000, "%.1f", 1)

        if unit == Units.Cents:
            return (-1200, 1200, "%.1f", 1)

        if unit == Units.Seconds:
            return (0, 100, "%.3f", 0.02)

        if unit == Units.Milliseconds:
            return (0, 10000, "%.0f", 1)

        if unit == Units.Meters:
            return (-100, 100, "%.3f", 0.1)

        if unit == Units.Degrees:
            return (0, 360, "%.3f", 0.2)

        return (-1000, 1000, "%.3f", 1)

    def _sync_combos(self) -> None:
        for idx, prop in enumerate(self._properties):
            dpg.configure_item(
                self._t(f"combo_{idx}"),
                items=sorted(p.name for p in self._get_available_props(exclude=prop)),
            )

    def _add_row(self, idx: int, prop: PropID, val: float) -> None:
        with dpg.table_row(parent=self._tag):
            dpg.add_combo(
                items=sorted(p.name for p in self._get_available_props(exclude=prop)),
                default_value=prop.name,
                width=-1,
                callback=self._on_prop_type_changed,
                user_data=idx,
                tag=self._t(f"combo_{idx}"),
            )

            vmin, vmax, fmt, rate = self._get_prop_range(prop)
            dpg.add_drag_float(
                default_value=val,
                width=-1,
                callback=self._on_prop_value_changed,
                min_value=vmin,
                max_value=vmax,
                format=fmt,
                speed=rate,
                user_data=idx,
                tag=self._t(f"value_{idx}"),
            )

            with dpg.group(horizontal=True, horizontal_spacing=3):
                if self._prop_ranges_enabled:
                    tint = style.yellow if prop in self._prop_ranges else style.white
                    dpg.add_image_button(
                        Icons.keyframe,
                        callback=self._edit_prop_range,
                        tint_color=tint,
                        tag=self._t(f"range_{idx}"),
                        user_data=idx,
                    )

                dpg.add_image_button(
                    Icons.trash,
                    callback=self._on_remove_clicked,
                    user_data=idx,
                    tag=self._t(f"remove_{idx}"),
                )

    def _add_footer(self) -> None:
        with dpg.table_row(parent=self._tag):
            dpg.add_button(label=µ("+ Add Property"), callback=self._on_add_clicked)

    # === DPG callbacks =================================================

    def _on_prop_type_changed(self, sender: str, new_key: str, idx: int) -> None:
        new_prop = PropID[new_key]
        props_list = list(self._properties.items())
        old_prop, val = props_list[idx]

        # Rebuild the dict to preserve insertion order
        self._properties.clear()
        for i, (p, v) in enumerate(props_list):
            self._properties[new_prop if i == idx else p] = v

        # Update value widget: reset to 0 only if the type actually changed
        if old_prop != new_prop:
            vmin, vmax, fmt, rate = self._get_prop_range(new_prop)
            dpg.configure_item(
                self._t(f"value_{idx}"),
                default_value=0.0,
                min_value=vmin,
                max_value=vmax,
                speed=rate,
                format=fmt,
            )
            self._properties[new_prop] = 0.0

        self._sync_combos()
        if self._on_values_changed:
            self._on_values_changed(self._tag, dict(self._properties), self._user_data)
        
        # Remove prop range if set
        self._prop_ranges.pop(old_prop, None)
        if self._prop_ranges_enabled:
            dpg.configure_item(self._t(f"range_{idx}"), tint_color=style.white)

        if self._on_prop_ranges_changed:
            self._on_prop_ranges_changed(self.tag, dict(self._prop_ranges), self._user_data)

    def _on_prop_value_changed(self, sender: str, new_val: float, idx: int) -> None:
        prop = list(self._properties.keys())[idx]
        self._properties[prop] = new_val

        if self._on_values_changed:
            self._on_values_changed(self._tag, dict(self._properties), self._user_data)

    def _edit_prop_range(self, sender: str, app_data: Any, idx: int) -> None:
        prop = list(self._properties.keys())[idx]
        tag = f"prop_range_dialog_{prop}"

        if dpg.does_item_exist(tag):
            dpg.focus_item(tag)
            return

        initial_range = self._prop_ranges.get(prop, (0.0, 0.0))
        vmin, vmax, fmt, rate = self._get_prop_range(prop)

        def on_change() -> None:
            enabled = dpg.get_value(self._t(f"range_{prop}_enable"))
            rmin = dpg.get_value(self._t(f"range_{prop}_min"))
            rmax = dpg.get_value(self._t(f"range_{prop}_max"))

            if enabled:
                self._prop_ranges[prop] = (rmin, rmax)
                dpg.configure_item(self._t(f"range_{idx}"), tint_color=style.yellow)
            else:
                self._prop_ranges.pop(prop, None)
                dpg.configure_item(self._t(f"range_{idx}"), tint_color=style.white)

            if self._on_prop_ranges_changed:
                self._on_prop_ranges_changed(
                    self.tag, self._prop_ranges, self._user_data
                )

        with dpg.window(
            autosize=True,
            label=prop.name,
            on_close=lambda: dpg.delete_item(tag),
            tag=tag,
        ):
            dpg.add_checkbox(
                label=µ("Random range"),
                default_value=(prop in self._prop_ranges),
                callback=on_change,
                tag=self._t(f"range_{prop}_enable"),
            )
            dpg.add_drag_float(
                label=µ("min"),
                default_value=initial_range[0],
                min_value=vmin,
                max_value=vmax,
                format=fmt,
                speed=rate,
                callback=on_change,
                tag=self._t(f"range_{prop}_min"),
            )
            dpg.add_drag_float(
                label=µ("max"),
                default_value=initial_range[1],
                min_value=vmin,
                max_value=vmax,
                format=fmt,
                speed=rate,
                callback=on_change,
                tag=self._t(f"range_{prop}_max"),
            )

        center_window(tag, xratio=0.2, yratio=0.2)

    def _on_add_clicked(self) -> None:
        available = self._get_available_props()
        if not available:
            return
        self._properties[available[0]] = 0.0
        self.refresh()
        if self._on_values_changed:
            self._on_values_changed(self._tag, dict(self._properties), self._user_data)

    def _on_remove_clicked(self, sender: str, app_data: Any, idx: int) -> None:
        prop = list(self._properties.keys())[idx]
        self._properties.pop(prop)
        self.refresh()
        if self._on_values_changed:
            self._on_values_changed(self._tag, dict(self._properties), self._user_data)

    # === Public ========================================================

    def refresh(self) -> None:
        dpg.delete_item(self._tag, children_only=True, slot=1)
        for idx, (prop, val) in enumerate(self._properties.items()):
            self._add_row(idx, prop, val)
        self._add_footer()

    @property
    def properties(self) -> dict[PropID, float]:
        return dict(self._properties)

    @properties.setter
    def properties(self, value: dict[PropID, float]) -> None:
        self._properties = dict(value)
        self.refresh()

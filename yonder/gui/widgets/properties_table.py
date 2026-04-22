from typing import Any, Callable
from dearpygui import dearpygui as dpg

from yonder.enums import PropID
from yonder.gui.localization import µ
from .dpg_item import DpgItem


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
        on_value_changed: Callable[[str, dict[PropID, Any], Any], None],
        *,
        label: str = "Properties",
        tag: str | int = 0,
        user_data: Any = None,
    ) -> None:
        super().__init__(tag)

        self._properties = properties
        self._on_value_changed = on_value_changed
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

    def _combo_tag(self, idx: int) -> str:
        return self._t(f"combo_{idx}")

    def _value_tag(self, idx: int) -> str:
        return self._t(f"value_{idx}")

    def _remove_tag(self, idx: int) -> str:
        return self._t(f"remove_{idx}")

    def _get_available_props(self, exclude: PropID = None) -> list[PropID]:
        used = set(self._properties.keys())
        if exclude:
            used.discard(exclude)
        return [k for k in PropID if k not in used]

    def _sync_combos(self) -> None:
        for idx, prop in enumerate(self._properties):
            dpg.configure_item(
                self._combo_tag(idx),
                items=[p.name for p in self._get_available_props(exclude=prop)],
            )

    def _add_row(self, idx: int, prop: PropID, val: float) -> None:
        with dpg.table_row(parent=self._tag):
            dpg.add_combo(
                items=[p.name for p in self._get_available_props(exclude=prop)],
                default_value=prop.name,
                width=-1,
                callback=self._on_prop_type_changed,
                user_data=idx,
                tag=self._combo_tag(idx),
            )
            dpg.add_input_double(
                default_value=val,
                width=-1,
                callback=self._on_prop_value_changed,
                user_data=idx,
                tag=self._value_tag(idx),
            )
            dpg.add_button(
                label="x",
                callback=self._on_remove_clicked,
                user_data=idx,
                tag=self._remove_tag(idx),
            )

    def _add_footer(self) -> None:
        with dpg.table_row(parent=self._tag):
            dpg.add_button(label=µ("+ Add Property"), callback=self._on_add_clicked)

    # === DPG callbacks =================================================

    def _on_prop_type_changed(self, sender: str, new_key: str, idx: int) -> None:
        new_prop = PropID[new_key]
        props_list = list(self._properties.items())
        old_prop, val = props_list[idx]

        # Rebuild the dict preserving insertion order
        self._properties.clear()
        for i, (p, v) in enumerate(props_list):
            self._properties[new_prop if i == idx else p] = v

        # Update value widget: reset to 0 only if the type actually changed
        if old_prop != new_prop:
            dpg.set_value(self._value_tag(idx), 0.0)
            self._properties[new_prop] = 0.0

        self._sync_combos()
        self._on_value_changed(self._tag, dict(self._properties), self._user_data)

    def _on_prop_value_changed(self, sender: str, new_val: float, idx: int) -> None:
        prop = list(self._properties.keys())[idx]
        self._properties[prop] = new_val
        self._on_value_changed(self._tag, dict(self._properties), self._user_data)

    def _on_add_clicked(self) -> None:
        available = self._get_available_props()
        if not available:
            return
        self._properties[available[0]] = 0.0
        self.refresh()
        self._on_value_changed(self._tag, dict(self._properties), self._user_data)

    def _on_remove_clicked(self, sender: str, app_data: Any, idx: int) -> None:
        prop = list(self._properties.keys())[idx]
        self._properties.pop(prop)
        self.refresh()
        self._on_value_changed(self._tag, dict(self._properties), self._user_data)

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
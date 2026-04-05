from typing import Any, Callable
from dearpygui import dearpygui as dpg

from yonder.enums import PropID


def add_properties_table(
    properties: dict[PropID, Any],
    on_value_changed: Callable[[str, dict[str, Any], Any], None],
    *,
    tag: str | int = 0,
    user_data: Any = None,
) -> None:
    if tag in (None, 0, ""):
        tag = dpg.generate_uuid()

    def get_available_keys(exclude: PropID = None) -> list[str]:
        used = set(properties.keys())
        if exclude:
            used.discard(exclude)

        return [k.name for k in PropID if k not in used]

    def refresh_table() -> None:
        dpg.delete_item(tag, children_only=True, slot=1)
        for prop, val in properties.items():
            add_row(prop, val)

        add_footer()

    def on_prop_type_changed(sender: int, new_key: str) -> None:
        row = dpg.get_item_parent(sender)
        siblings = dpg.get_item_children(row, slot=1)
        value_widget = siblings[1]
        old_prop = next(k for k, combo in row_widgets.items() if combo[0] == sender)
        properties.pop(old_prop)

        new_prop = PropID[new_key]
        properties[new_prop] = 0.0
        row_widgets[new_prop] = row_widgets.pop(old_prop)
        dpg.configure_item(value_widget, default_value=0.0)
        sync_combos()

        on_value_changed(tag, dict(properties), user_data)

    def on_prop_value_changed(sender: int, new_val: float) -> None:
        for key, (_, value_id, _) in row_widgets.items():
            if value_id == sender:
                properties[key] = new_val
                break

        on_value_changed(tag, dict(properties), user_data)

    def on_add_clicked() -> None:
        available = get_available_keys()
        if not available:
            return

        new_key = available[0]
        properties[new_key] = 0.0
        refresh_table()
        on_value_changed(tag, dict(properties), user_data)

    def on_remove_clicked(sender: int) -> None:
        key = next(k for k, ids in row_widgets.items() if ids[2] == sender)
        properties.pop(key)
        refresh_table()
        on_value_changed(tag, dict(properties), user_data)

    def sync_combos() -> None:
        for key, (combo_id, _, __) in row_widgets.items():
            dpg.configure_item(combo_id, items=get_available_keys(exclude=key))

    def add_row(prop: PropID, val: float) -> None:
        with dpg.table_row(parent=tag):
            combo_id = dpg.add_combo(
                items=get_available_keys(exclude=prop),
                default_value=prop.name,
                width=-1,
                callback=on_prop_type_changed,
            )
            value_id = dpg.add_input_double(
                default_value=val,
                width=-1,
                callback=on_prop_value_changed,
            )
            remove_id = dpg.add_button(label="-", callback=on_remove_clicked)
            row_widgets[PropID[prop]] = (combo_id, value_id, remove_id)

    def add_footer() -> None:
        with dpg.table_row(parent=tag):
            dpg.add_button(label="+ Add Property", callback=on_add_clicked)

    row_widgets: dict[PropID, tuple[int, int, int]] = {}

    # The actual widgets
    dpg.add_text("Properties")

    with dpg.table(
        header_row=False,
        policy=dpg.mvTable_SizingFixedFit,
        borders_outerH=True,
        borders_outerV=True,
        tag=tag,
    ):
        dpg.add_table_column(
            label="Property", width_stretch=True, init_width_or_weight=100
        )
        dpg.add_table_column(
            label="Value", width_stretch=True, init_width_or_weight=100
        )
        dpg.add_table_column(label="", width_fixed=True)
        for prop, val in properties.items():
            add_row(prop, val)
        add_footer()

from typing import TypeVar, Type, Callable, Any
from enum import IntEnum
from dearpygui import dearpygui as dpg


_T = TypeVar("_T", bound=IntEnum)


def add_incomplete_int_enum(
    enum: Type[_T],
    default_value: _T,
    unknown_label: str,
    on_value_changed: Callable[[str, int, Any], None],
    *,
    label: str = None,
    sort: bool = True,
    tag: str = 0,
    user_data: Any = None,
) -> str:
    if not tag:
        tag = dpg.generate_uuid()

    def on_combo_changed(sender: str, choice: str, cb_user_data: Any) -> None:
        val = enum[choice]
        dpg.set_value(f"{tag}_value", val.value)
        on_value_changed(tag, val.value, user_data)

    def on_value_changed(sender: str, value: int, cb_user_data: Any) -> None:
        try:
            choice = enum(value).name
        except KeyError:
            choice = unknown_label
        
        dpg.set_value(f"{tag}_combo", choice)
        on_value_changed(tag, value, user_data)

    choices = [e.name for e in enum]
    if sort:
        choices.sort()

    with dpg.group(horizontal=True, tag=tag):
        dpg.add_combo(
            choices,
            default_value=default_value.name,
            callback=on_combo_changed,
            tag=f"{tag}_combo",
            width=150,
        )
        dpg.add_input_int(
            default_value=default_value.value,
            label=label,
            min_value=min(e.value for e in enum),
            max_value=max(e.value for e in enum),
            callback=on_value_changed,
            tag=f"{tag}_value",
        )

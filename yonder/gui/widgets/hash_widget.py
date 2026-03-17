from typing import Any, Callable
from dearpygui import dearpygui as dpg

from yonder.hash import calc_hash, lookup_name


def add_hash_widget(
    default_value: int = 0,
    on_hash_changed: Callable[[str, tuple[int, str], Any], None] = None,
    *,
    initial_string: str = None,
    horizontal: bool = True,
    allow_edit_hash: bool = True,
    allow_edit_name: bool = True,
    string_label: str = "String",
    hash_label: str = "Hash",
    width: int = -1,
    tag: str = 0,
    user_data: Any = None,
) -> str:
    if not tag:
        tag = dpg.generate_uuid()

    def on_hash_update(sender: str, new_value: str, cb_user_data: Any) -> None:
        if not new_value:
            return

        label = lookup_name(int(new_value), None)
        dpg.set_value(f"{tag}_string", label or "<?>")
        
        if on_hash_changed:
            on_hash_changed(tag, (int(new_value), label), user_data)

    def on_string_update(sender: str, label: str, cb_user_data: Any) -> None:
        h = calc_hash(label)
        dpg.set_value(f"{tag}_hash", h)

        if on_hash_changed:
            on_hash_changed(tag, (h, label), user_data)


    if horizontal:
        if width not in (0, -1):
            string_w = abs(width) / 2
            hash_w = width / 2
        else:
            string_w = 100
            hash_w = -1

        with dpg.group(horizontal=True, tag=tag):
            dpg.add_input_text(
                default_value=str(default_value),
                decimal=True,
                readonly=not allow_edit_hash,
                enabled=allow_edit_hash,
                width=string_w,
                callback=on_hash_update,
                tag=f"{tag}_hash",
            )
            dpg.add_input_text(
                default_value=lookup_name(default_value, initial_string),
                label=hash_label or "",
                readonly=not allow_edit_name,
                enabled=allow_edit_name,
                width=hash_w,
                callback=on_string_update,
                tag=f"{tag}_string",
            )
    else:
        with dpg.group(tag=tag):
            dpg.add_input_text(
                default_value=lookup_name(default_value, initial_string),
                label=string_label or "",
                readonly=not allow_edit_name,
                enabled=allow_edit_name,
                width=width,
                callback=on_string_update,
                tag=f"{tag}_string",
            )
            dpg.add_input_text(
                default_value=str(default_value),
                decimal=True,
                label=hash_label or "",
                readonly=not allow_edit_hash,
                enabled=allow_edit_hash,
                width=width,
                callback=on_hash_update,
                tag=f"{tag}_hash",
            )

    return tag

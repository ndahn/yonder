from typing import Any, Callable, Literal, get_origin, get_args
from enum import Enum, IntFlag
from pathlib import Path
from dearpygui import dearpygui as dpg

from yonder.gui.helpers import shorten_path
from yonder.gui.dialogs.file_dialog import (
    save_file_dialog,
    open_file_dialog,
    choose_folder,
)
from .flags_widget import add_flag_checkboxes


def is_simple_type(value_type: type) -> bool:
    if value_type is None:
        return False

    simple_types = (int, float, bool, str, Path, Enum, IntFlag, Literal)
    if value_type in simple_types:
        return True

    type_origin = get_origin(value_type) or value_type
    if type_origin in simple_types:
        return True

    origin_args = get_args(value_type)
    # Could support tuples too, but they are not editable and don't appear in json, so...
    if type_origin is list and origin_args in simple_types:
        return True

    return False


def add_generic_widget(
    value_type: type,
    label: str,
    callback: Callable[[str, Any, Any], None] = None,
    *,
    default: Any = None,
    choices: list[str | tuple[str | Any]] = None,
    readonly: bool = False,
    flags_as_int: bool = False,
    accept_on_enter: bool = False,
    file_mode: Literal["open", "save", "folder"] = "open",
    filetypes: dict[str, str] = None,
    not_supported_ok: bool = False,
    parent: str = 0,
    tag: str = 0,
    user_data: Any = None,
    **kwargs,
) -> str:
    if tag in (None, 0, ""):
        tag = dpg.generate_uuid()

    if isinstance(value_type, type) and issubclass(value_type, IntFlag):
        if flags_as_int:
            value_type = int
        else:
            # We have specific support for flags already
            return add_flag_checkboxes(
                value_type,
                callback,
                readonly=readonly,
                base_tag=tag,
                parent=parent,
                active_flags=default if default is not None else 0,
                user_data=user_data,
            )

    # Support enums by extracting their choices
    if isinstance(value_type, type) and issubclass(value_type, Enum):
        choices = [(v.name, v.value) for v in value_type]
        if default is not None and not isinstance(default, str):
            default = value_type(default).name

    # If choices is provided we treat this as a Literal
    if choices:
        orig_callback = callback
        items = [x[0] if isinstance(x, tuple) else x for x in choices]

        def new_callback(sender: str, data: str, cb_user_data: Any):
            # Find the selected item in the original choices list
            index = items.index(data)
            selected = choices[index]

            # If a tuple was provided the first element is only a label,
            # the actual value is in the second element
            if isinstance(selected, tuple):
                selected = selected[1]

            if orig_callback:
                orig_callback(sender, selected, user_data)

        value_type = Literal[tuple(items)]
        callback = new_callback

    # The simple types
    type_origin = get_origin(value_type)
    origin_args = get_args(value_type)

    if type_origin == Literal:
        choices = origin_args
        items = [str(c) for c in choices]

        if default in choices:
            default = items[choices.index(default)]

        dpg.add_combo(
            items,
            label=label,
            default_value=default if default is not None else "",
            enabled=not readonly,
            callback=callback,
            parent=parent,
            tag=tag,
            **kwargs,
            user_data=user_data,
        )
    elif value_type is int:
        dpg.add_input_int(
            label=label,
            default_value=int(default) if default is not None else 0,
            readonly=readonly,
            enabled=not readonly,
            callback=callback,
            on_enter=accept_on_enter,
            parent=parent,
            tag=tag,
            user_data=user_data,
            **kwargs,
        )
    elif value_type is float:
        dpg.add_input_float(
            label=label,
            default_value=float(default) if default is not None else 0.0,
            readonly=readonly,
            enabled=not readonly,
            callback=callback,
            on_enter=accept_on_enter,
            parent=parent,
            tag=tag,
            user_data=user_data,
            **kwargs,
        )
    elif value_type is bool:
        dpg.add_checkbox(
            label=label,
            default_value=bool(default) if default is not None else False,
            enabled=not readonly,
            callback=callback,
            parent=parent,
            tag=tag,
            user_data=user_data,
            **kwargs,
        )
    elif not type_origin and value_type in (type(None), str):
        dpg.add_input_text(
            label=label,
            default_value=str(default) if default is not None else "",
            readonly=readonly,
            enabled=not readonly,
            callback=callback,
            on_enter=accept_on_enter,
            parent=parent,
            tag=tag,
            user_data=user_data,
            **kwargs,
        )
    elif value_type is Path:
        if default:
            default = str(default)

        def select_file() -> None:
            if file_mode == "open":
                ret = open_file_dialog(
                    title=label,
                    default_file=default,
                    filetypes=filetypes,
                )
            elif file_mode == "save":
                ret = save_file_dialog(
                    title=label,
                    default_file=default,
                    filetypes=filetypes,
                )
            elif file_mode == "folder":
                ret = choose_folder(title=label)
            else:
                raise ValueError(f"Invalid file mode {file_mode}")

            if ret:
                dpg.set_value(tag, shorten_path(ret))
                if callback:
                    callback(tag, Path(ret), user_data)

        with dpg.group(horizontal=True, parent=parent):

            def cb(sender: str, new_path: str, user_data):
                if callback:
                    callback(sender, Path(new_path), user_data)

            dpg.add_input_text(
                default_value=shorten_path(default) if default else "",
                decimal=True,
                readonly=readonly,
                enabled=not readonly,
                callback=cb,
                user_data=user_data,
                tag=tag,
            )
            dpg.add_button(
                # arrow=True,
                # direction=dpg.mvDir_Right,
                label="Browse",
                callback=select_file,
            )
            dpg.add_text(label)
    elif type_origin is list and origin_args in (int, float, bool, str, Path):
        from .editable_table import add_widget_table

        def cb(sender: str, changes: tuple[int, Any, list], user_data):
            if callback:
                callback(sender, changes[2], user_data)

        def add_list_item(done: Callable[[Any], None]) -> Any:
            done(origin_args())

        def create_list_item_row(item: Any, idx: int) -> None:
            add_generic_widget(
                origin_args,
                f"{label}:{idx}",
                None,
                file_mode=file_mode,
                filetypes=filetypes,
            )

        add_widget_table(
            default or [],
            create_list_item_row,
            label=label,
            new_item=add_list_item,
            on_add=cb,
            on_remove=cb,
            user_data=user_data,
            parent=parent,
            tag=tag,
        )
    else:
        if not_supported_ok:
            return None
        raise ValueError(f"Could not handle type {value_type} for {label}")

    return tag

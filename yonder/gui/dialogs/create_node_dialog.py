from typing import Any, Callable
from dearpygui import dearpygui as dpg

from yonder import Soundbank, HIRCNode
from yonder.util import get_function_spec, logger
from yonder.gui import style
from yonder.gui.widgets import add_generic_widget


def create_node_dialog(
    bnk: Soundbank,
    callback: Callable[[HIRCNode], None],
    *,
    title: str = "Create Node",
    tag: str = None,
) -> str:
    if not tag:
        tag = dpg.generate_uuid()
    elif dpg.does_item_exist(tag):
        dpg.delete_item(tag)

    nid = bnk.new_id()
    node_types = {t.__name__: t for t in HIRCNode.__subclasses__()}
    selected_type = next(t for t in node_types.keys())
    node_args = {}

    def set_arg(sender: str, app_data: Any, key: str) -> None:
        node_args[key] = app_data

    def on_type_selected(sender: str, type_name: str, user_data: Any):
        nonlocal selected_type
        if type_name == selected_type:
            return

        selected_type = type_name
        type_class = node_types[type_name]
        spec = get_function_spec(type_class.new, None)
        node_args.clear()

        dpg.delete_item(f"{tag}_node_args", children_only=True, slot=1)

        for name, arg in spec.items():
            if name in ("nid", "parent"):
                continue

            node_args[name] = arg.default
            add_generic_widget(
                arg.type,
                name,
                set_arg,
                default=arg.default,
                user_data=name,
                parent=f"{tag}_node_args",
                tag=f"{tag}_arg_{name}",
            )

    def on_okay() -> None:
        node_args["nid"] = nid
        type_class = node_types[selected_type]
        node = type_class.new(**node_args)
        logger.info(f"Created new node {node}")

        callback(node)
        dpg.delete_item(window)

    with dpg.window(
        label=title,
        width=400,
        height=400,
        autosize=True,
        no_saved_settings=True,
        tag=tag,
        on_close=lambda: dpg.delete_item(window),
    ) as window:
        dpg.add_combo(
            [t for t in node_types.keys()],
            default_value=selected_type,
            callback=on_type_selected,
            width=300,
            tag=f"{tag}_node_type",
        )

        dpg.add_input_text(
            label="id",
            readonly=True,
            enabled=False,
            default_value=str(nid),
            tag=f"{tag}_node_id",
        )

        with dpg.child_window(auto_resize_y=True, tag=f"{tag}_node_args"):
            pass

        dpg.add_separator()
        dpg.add_text(show=False, tag=f"{tag}_notification", color=style.red)

        with dpg.group(horizontal=True):
            dpg.add_button(label="Make!", callback=on_okay, tag=f"{tag}_button_okay")

    on_type_selected(f"{tag}_node_type", selected_type, None)
    return tag

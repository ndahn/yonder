from typing import Any, Callable, Type, Iterable
from dearpygui import dearpygui as dpg

from yonder import HIRCNode
from yonder.gui.dialogs.select_nodes_dialog import select_nodes_dialog


def add_node_widget(
    get_items: Callable[[str], Iterable[HIRCNode]],
    label: str,
    callback: Callable[[str, HIRCNode | list[HIRCNode], Any], None],
    *,
    get_node_details: Callable[[HIRCNode], list[str]] = None,
    multiple: bool = False,
    default: HIRCNode = None,
    node_type: Type[HIRCNode] = None,
    readonly: bool = False,
    parent: str = 0,
    tag: str = 0,
    user_data: Any = None,
) -> str:
    if not tag:
        tag = dpg.generate_uuid()

    if isinstance(default, HIRCNode):
        default = default.id

    if default is None:
        default = "0"

    default = str(default)

    def get_nodes(filt: str) -> Iterable[HIRCNode]:
        for node in get_items(filt):
            if not node_type or isinstance(node, node_type):
                yield node

    def on_node_selected(sender: str, nodes: list[HIRCNode], cb_user_data: Any) -> None:
        dpg.set_value(tag, str(nodes[0].id))
        callback(tag, nodes[0], user_data)

    def select_node() -> None:
        select_nodes_dialog(
            get_nodes,
            on_node_selected,
            get_node_details=get_node_details,
            multiple=multiple,
            user_data=user_data,
        )

    with dpg.group(horizontal=True, parent=parent):
        dpg.add_input_text(
            default_value=default,
            decimal=True,
            readonly=readonly,
            enabled=not readonly,
            callback=lambda s, a, u: callback(tag, int(a), u),
            user_data=user_data,
            tag=tag,
        )
        dpg.add_button(
            arrow=True,
            direction=dpg.mvDir_Right,
            callback=select_node,
        )
        dpg.add_text(label)

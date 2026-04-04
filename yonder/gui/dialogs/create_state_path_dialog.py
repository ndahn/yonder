from typing import Any, Callable, Iterable
from dearpygui import dearpygui as dpg

from yonder import Soundbank, Node
from yonder.types import MusicSwitchContainer
from yonder.hash import lookup_name, calc_hash
from yonder.gui import style
from yonder.gui.widgets import add_node_widget


def create_state_path_dialog(
    bnk: Soundbank,
    node: MusicSwitchContainer,
    callback: Callable[[str, list[str] | list[int], int], None],
    *,
    state_path: list[str] = None,
    hide_node_id: bool = False,
    node_id: int = None,
    raw: bool = False,
    title: str = "New State Path",
    tag: str = None,
) -> str:
    if not tag:
        tag = dpg.generate_uuid()
    elif dpg.does_item_exist(tag):
        dpg.delete_item(tag)

    if state_path and len(state_path) != len(node.arguments):
        raise ValueError(
            "State path must have the same length as MusicSwitchContainer arguments"
        )

    leaf_node_id: int = 0

    def on_node_selected(sender: str, leaf_node: int | Node, user_data: Any) -> None:
        nonlocal leaf_node_id
        if isinstance(leaf_node, Node):
            leaf_node = leaf_node.id
        leaf_node_id = leaf_node

    def get_nodes(filt: str) -> Iterable[Node]:
        yield from bnk.query(filt)

    def show_message(msg: str = None, color: tuple[int, int, int, int] = style.red) -> None:
        if not msg:
            dpg.hide_item(f"{tag}_notification")
            return

        dpg.configure_item(
            f"{tag}_notification",
            default_value=msg,
            color=color,
            show=True,
        )

    def on_okay() -> None:
        if not hide_node_id and leaf_node_id <= 0:
            show_message("Leaf node ID not set")
            return

        keys: list[str] = []
        for arg in node.arguments:
            key: str = dpg.get_value(f"{tag}_arg_{arg}")
            if not key:
                show_message("Keys must not be empty")
                return

            keys.append(key)

        if raw:
            keys = MusicSwitchContainer.parse_state_path(keys)

        callback(tag, keys, leaf_node_id)
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
        # For these decision trees all branches have the same length,
        # which makes it so much easier for us!
        for i, arg in enumerate(node.arguments):
            name = lookup_name(arg, f"#{arg}")
            default_val = state_path[i] if state_path else "*"
            dpg.add_input_text(
                label=name,
                default_value=default_val,
                tag=f"{tag}_arg_{arg}",
            )

        dpg.add_spacer(height=3)
        if not hide_node_id:
            add_node_widget(
                get_nodes,
                "Node",
                on_node_selected,
                default=node_id if node_id else 0,
            )

        dpg.add_separator()
        dpg.add_text(show=False, tag=f"{tag}_notification", color=style.red)

        with dpg.group(horizontal=True):
            dpg.add_button(label="Okay", callback=on_okay, tag=f"{tag}_button_okay")
            dpg.add_button(
                label="Cancel",
                callback=lambda: dpg.delete_item(window),
            )


def parse_state_path(state_path: list[str]) -> list[int]:
    keys = []
    for val in state_path:
        if val == "*":
            keys.append(0)
        elif val.startswith("#"):
            try:
                keys.append(int(val[1:]))
            except ValueError:
                raise ValueError(f"{val}: value is not a valid hash")
        else:
            keys.append(calc_hash(val))

    return keys

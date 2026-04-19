from typing import Any, Callable, Iterable
from dearpygui import dearpygui as dpg

from yonder import Soundbank, HIRCNode
from yonder.util import parse_state_path
from yonder.types.music_switch_container import MusicSwitchContainer
from yonder.hash import lookup_name
from yonder.gui import style
from yonder.gui.localization import µ
from yonder.gui.widgets import DpgItem, add_node_reference


class edit_state_path_dialog(DpgItem):
    """A dialog for entering a state path into a ``MusicSwitchContainer``.

    Renders one input field per container argument, pre-filled from
    ``state_path`` if provided. Optionally shows a node reference picker for
    the target leaf node. On confirm, parses keys (optionally converting to
    raw integer hashes) and calls ``callback``.

    Parameters
    ----------
    bnk : Soundbank
        Used to query available leaf nodes.
    node : MusicSwitchContainer
        Container whose arguments define the path fields.
    callback : callable
        Called as ``callback(tag, keys, leaf_node_id)`` on confirm.
    state_path : list of str, optional
        Pre-filled values; must match ``len(node.arguments)`` if given.
    hide_node_id : bool
        Omit the leaf node reference picker when True.
    node_id : int, optional
        Pre-selected leaf node ID.
    raw : bool
        Parse key strings to integer hashes before passing to ``callback``.
    title : str
        Window title bar label.
    tag : int or str, optional
        Explicit tag; auto-generated if None. Existing item is deleted first.
    """

    def __init__(
        self,
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
    ) -> None:
        if tag and dpg.does_item_exist(tag):
            dpg.delete_item(tag)

        super().__init__(tag)

        if state_path and len(state_path) != len(node.arguments):
            raise ValueError(
                "State path must have the same length as MusicSwitchContainer arguments"
            )

        self._bnk = bnk
        self._node = node
        self._callback = callback
        self._state_path = state_path
        self._hide_node_id = hide_node_id
        self._raw = raw
        self._leaf_node_id: int = node_id or 0
        self._window: str = None

        self._build(title, state_path, hide_node_id, node_id)

    # === Build =========================================================

    def _build(
        self,
        title: str,
        state_path: list[str],
        hide_node_id: bool,
        node_id: int,
    ) -> None:
        with dpg.window(
            label=title,
            width=400,
            height=400,
            autosize=True,
            no_saved_settings=True,
            tag=self._tag,
            on_close=lambda: dpg.delete_item(self._window),
        ) as self._window:
            # For decision trees all branches have the same length
            for i, arg in enumerate(self._node.arguments):
                name = lookup_name(arg.group_id, f"#{arg.group_id}")
                dpg.add_input_text(
                    label=name,
                    default_value=state_path[i] if state_path else "*",
                    tag=self._t(f"arg_{arg.group_id}"),
                )

            dpg.add_spacer(height=3)
            if not hide_node_id:
                add_node_reference(
                    self._get_nodes,
                    "Node",
                    self._on_node_selected,
                    default=node_id or 0,
                )

            dpg.add_separator()
            dpg.add_text(show=False, tag=self._t("notification"), color=style.red)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label=µ("Okay", "button"),
                    callback=self._on_okay,
                    tag=self._t("button_okay"),
                )
                dpg.add_button(
                    label=µ("Cancel", "button"),
                    callback=lambda: dpg.delete_item(self._window),
                )

    # === DPG callbacks =================================================

    def _get_nodes(self, filt: str) -> Iterable[HIRCNode]:
        yield from self._bnk.query(filt)

    def _on_node_selected(
        self, sender: str, leaf_node: int | HIRCNode, ud: Any
    ) -> None:
        if isinstance(leaf_node, HIRCNode):
            leaf_node = leaf_node.id
        self._leaf_node_id = leaf_node

    def _on_okay(self) -> None:
        if not self._hide_node_id and self._leaf_node_id <= 0:
            self.show_message(µ("Leaf node ID not set", "msg"))
            return

        keys: list[str] = []
        for arg in self._node.arguments:
            key = dpg.get_value(self._t(f"arg_{arg.group_id}"))
            if not key:
                self.show_message(µ("Keys must not be empty", "msg"))
                return
            keys.append(key)

        if self._raw:
            keys = parse_state_path(keys)

        self.show_message()
        self._callback(self._tag, keys, self._leaf_node_id)
        dpg.delete_item(self._window)

    # === Public ========================================================

    def show_message(self, msg: str = None, color: style.RGBA = style.red) -> None:
        """Show or hide the notification label. Pass ``msg=None`` to hide."""
        if not msg:
            dpg.hide_item(self._t("notification"))
            return

        dpg.configure_item(
            self._t("notification"),
            default_value=msg,
            color=color,
            show=True,
        )

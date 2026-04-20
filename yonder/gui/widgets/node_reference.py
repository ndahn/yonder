from __future__ import annotations
from typing import Any, Callable, Type, Iterable, TYPE_CHECKING
from dearpygui import dearpygui as dpg

from yonder import HIRCNode
from yonder.hash import lookup_name
from yonder.gui.localization import µ
from yonder.gui.dialogs.select_nodes_dialog import select_nodes_dialog
from .dpg_item import DpgItem

if TYPE_CHECKING:
    from yonder.types import Soundbank, ActorMixer, MusicSwitchContainer


class ActorMixerDetailProvider:
    def __init__(self, bnk: Soundbank):
        self.bnk = bnk

    def __call__(self, am: ActorMixer) -> list[str]:
        events = set()
        for child_id in am.children:
            child = self.bnk.get(child_id)
            if child:
                for evt, _ in self.bnk.find_event_subgraphs_for(child):
                    name = evt.get_wwise_name(f"#{evt.id}")
                    events.add(name)

        used_by = sorted(events)[:10]
        if len(events) > 10:
            used_by.append("...")
        
        return [µ("Used by:")] + used_by


def get_details_musicswitchcontainer(msc: MusicSwitchContainer) -> list[str]:
    return [µ("States:")] + [lookup_name(s.group_id, f"#{s.group_id}") for s in msc.arguments]


def get_details_generic(node: HIRCNode) -> list[str]:
    details = [node.get_name(f"#{node.id}")]
    
    if hasattr(node, "children"):
        details.append(µ("Children: {num}").format(num=len(node.children)))

    if hasattr(node, "properties") and node.properties:
        details.append(µ("Properties") + ":")
        for prop in node.properties:
            details.append(f" {prop}")

    if hasattr(node, "rtpcs") and node.rtpcs:
        details.append("RTPCs:")
        for rtpc in node.rtpcs:
            details.append(f" {rtpc}")

    return details


class add_node_reference(DpgItem):
    def __init__(
        self,
        get_items: Callable[[str], Iterable[HIRCNode]],
        label: str,
        callback: Callable[[str, HIRCNode | list[HIRCNode], Any], None],
        *,
        get_node_details: Callable[[HIRCNode], list[str]] = None,
        multiple: bool = False,
        default: HIRCNode = None,
        node_type: Type[HIRCNode] = None,
        node_filter: Callable[[HIRCNode], bool] = None,
        readonly: bool = True,
        parent: str = 0,
        tag: str = 0,
        user_data: Any = None,
    ) -> str:
        super().__init__(tag)

        self._get_items = get_items
        self._node_filter = node_filter
        self._callback = callback
        self._user_data = user_data
        self._multiple = multiple
        self._readonly = readonly
        self._node_type = node_type
        self._get_node_details = get_node_details

        if isinstance(default, HIRCNode):
            default = default.id

        if default is None:
            default = "0"

        default = str(default)

        self._build(label, default, readonly, parent)

    # === Build =================

    def _build(self, label: str, default: HIRCNode, readonly: bool, parent: str):
        with dpg.group(horizontal=True, parent=parent):
            dpg.add_input_text(
                default_value=default,
                decimal=True,
                readonly=readonly,
                enabled=not readonly,
                callback=self._on_node_edit,
                user_data=self._user_data,
                tag=self.tag,
            )
            dpg.add_button(
                arrow=True,
                direction=dpg.mvDir_Right,
                callback=self._select_node,
            )
            dpg.add_text(label)

    def _get_nodes(self, filt: str) -> Iterable[HIRCNode]:
        for node in self._get_items(filt):
            if self._node_type and not isinstance(node, self._node_type):
                continue

            if self._node_filter and not self._node_filter(node):
                continue

            yield node

    def _on_node_edit(self, sender: str, name: str, user_data: Any) -> None:
        if self._callback:
            self._callback(self.tag, name, user_data)

    def _on_node_selected(self, sender: str, node: HIRCNode, user_data: Any) -> None:
        dpg.set_value(self.tag, str(node.id))
        if self._callback:
            self._callback(self.tag, node, user_data)

    def _select_node(
        self,
    ) -> None:
        select_nodes_dialog(
            self._get_nodes,
            self._on_node_selected,
            get_node_details=self._get_node_details,
            multiple=self._multiple,
            user_data=self._user_data,
        )

    # === Public accessors =================

    @property
    def selected_node(self) -> int:
        val = dpg.get_value(self.tag)
        try:
            return int(val)
        except Exception:
            return None

    @selected_node.setter
    def selected_node(self, node: int | HIRCNode) -> None:
        if isinstance(node, HIRCNode):
            node = node.id

        if node is not None:
            node = int(node)

        dpg.set_value(self.tag, node)

from __future__ import annotations
from typing import Any, Callable, Type, Iterable, TYPE_CHECKING
from dearpygui import dearpygui as dpg

from yonder import HIRCNode
from yonder.hash import lookup_name
from yonder.gui.localization import µ
from yonder.gui.dialogs.select_nodes_dialog import select_nodes_dialog
from .dpg_item import DpgItem

if TYPE_CHECKING:
    from yonder.types import Soundbank, ActorMixer, Event, MusicSwitchContainer


class ActorMixerDetailProvider:
    def __init__(self, bnk: Soundbank):
        self.bnk = bnk
        self._cache: dict[int, list[int]] = {}

        for amx in bnk.query("type=ActorMixer"):
            self._load_details(amx)

    def _load_details(self, amx: ActorMixer) -> None:
        todo: list[HIRCNode] = [amx]
        dependents = set()

        while todo:
            node = todo.pop()
            if not hasattr(node, "children"):
                continue

            for child_id in node.children:
                child = self.bnk.get(child_id)
                if not child:
                    continue

                if isinstance(child, ActorMixer):
                    dependents.add(child_id)
                else:
                    dependents.update(
                        evt.id for evt, _ in self.bnk.find_event_subgraphs_for(child)
                    )

        ret = sorted(dependents)
        self._cache[node.id] = ret
        return ret

    def __call__(self, amx: ActorMixer) -> list[str]:
        dependents = self._cache.get(amx.id)
        if dependents is None:
            dependents = self._load_details(amx)

        used_by = []
        for n in dependents[:10]:
            node = self.bnk[n]
            if isinstance(node, Event):
                used_by.append("Event " + self.bnk[n].get_wwise_name(f"#{n}"))
            else:
                used_by.append(node.get_name(f"{node.type_name} #{node.id}"))

        if len(dependents) > 10:
            used_by.append("...")

        return [µ("Used by:")] + used_by


def get_details_musicswitchcontainer(msc: MusicSwitchContainer) -> list[str]:
    return [µ("States:")] + [
        lookup_name(s.group_id, f"#{s.group_id}") for s in msc.arguments
    ]


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


class add_select_node(DpgItem):
    def __init__(
        self,
        get_items: Callable[[str], Iterable[HIRCNode]],
        label: str,
        callback: Callable[[str, HIRCNode | list[HIRCNode], Any], None],
        *,
        get_node_details: Callable[[HIRCNode], list[str]] = None,
        jump_to: Callable[[str, HIRCNode, Any], None] = None,
        multiple: bool = False,
        default: HIRCNode = None,
        node_type: Type[HIRCNode] = None,
        node_filter: Callable[[HIRCNode], bool] = None,
        readonly: bool = True,
        textbox_width: int = 0,
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
        self._jump_to = jump_to

        if isinstance(default, HIRCNode):
            default = default.id

        if default is None:
            default = "0"

        default = str(default)

        self._build(label, default, readonly, textbox_width, parent)

    # === Build =================

    def _build(
        self,
        label: str,
        default: HIRCNode,
        readonly: bool,
        textbox_width: int,
        parent: str,
    ):
        with dpg.group(horizontal=True, parent=parent):
            dpg.add_input_text(
                default_value=default,
                decimal=True,
                readonly=readonly,
                enabled=not readonly,
                width=textbox_width,
                callback=self._on_node_edit,
                user_data=self._user_data,
                tag=self.tag,
            )

            if self._jump_to:
                with dpg.popup(dpg.last_item(), min_size=(100, 20)):
                    dpg.add_menu_item(
                        label=µ("Jump To"),
                        callback=lambda s, a, u: self._jump_to(
                            self.tag, dpg.get_value(self.tag), self._user_data
                        ),
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

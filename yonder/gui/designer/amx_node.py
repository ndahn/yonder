from typing import ClassVar, Any
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.gui.designer.graph_designer_node import GraphDesignerNode
from yonder.gui.localization import μ
from yonder.types import HIRCNode, ActorMixer
from yonder.gui.widgets import add_select_actormixer


class AMXNode(GraphDesignerNode):
    """A predefined ActorMixer that will mix different audio pieces."""

    node_type: ClassVar[type[HIRCNode]] = ActorMixer
    label: ClassVar[str] = "ActorMixer"
    show_name_field: ClassVar[bool] = False
    inputs: ClassVar[tuple[str, ...]] = ()
    outputs: ClassVar[tuple[str, ...]] = ("Child",)

    def __init__(
        self,
        bnk: Soundbank,
        nid: str | int = 0,
    ):
        super().__init__(bnk, nid)
        self._bnk = bnk
        self._amx_selector: add_select_actormixer = None

    def build_body(self) -> None:
        self._amx_selector = add_select_actormixer(
            self._bnk,
            textbox_width=self.body_width,
            tag=self._wtag("amx_selector"),
        )
        dpg.add_checkbox(label=µ("Custom"), callback=self._toggle_custom, tag=self._wtag("custom"))

    @property
    def is_custom(self) -> bool:
        return dpg.get_value(self._wtag("custom"))

    def _toggle_custom(self, sender: str, custom: bool, user_data: Any) -> None:
        if custom:
            dpg.hide_item(self._wtag("amx_selector"))
            dpg.show_item(self._wtag("name"))
            self.sync_terminals(["Parent"], True)
            self.sync_terminals(["Child", "Bus", "Aux 1"], False)
            dpg.move_item_up(self.get_input_terminal("Parent"))
        else:
            dpg.show_item(self._wtag("amx_selector"))
            dpg.hide_item(self._wtag("name"))
            self.sync_terminals([], True)
            self.sync_terminals(["Child"], False)

    def on_connections_changed(self, inputs: set[str], outputs: set[str]) -> None:
        if not self.is_custom:
            return

        # Add up to 4 aux slots
        items = [o for o in self.get_terminals(False) if o.startswith("Aux")]
        last_used = max(
            (i for i, label in enumerate(items) if label in outputs), default=-1
        )
        wanted = min(4, last_used + 2)

        for label in items[wanted:]:
            self.remove_terminal(label, False)

        for i in range(len(items), wanted):
            self.add_terminal(f"Aux {i}", False)

    def link_valid(
        self,
        source: GraphDesignerNode,
        output: str,
        target: GraphDesignerNode,
        input: str,
    ) -> bool:
        if source is self:
            if output == "Child":
                return input in ("Playback", "Parent")

        return super().link_valid(source, output, target, input)

    def validate(
        self, bnk: Soundbank, input_map: dict[str, int], output_map: dict[str, int]
    ) -> str:
        if not self._amx_selector.selected_node:
            return µ("No ActorMixer selected")

        if "Child" not in output_map:
            return µ("Child not connected")

        return super().validate(bnk, input_map, output_map)

    def make_node(
        self, bnk: Soundbank, input_map: dict[str, int], output_map: dict[str, int]
    ) -> ActorMixer:
        if not self.is_custom:
            return self._amx_selector.selected_node

        parent = input_map.get("Playback", 0)
        child = output_map.get("Child", 0)
        bus = output_map.get("Bus", 0)
        # TODO
        aux = [output_map[key] for key in sorted(output_map) if key.startswith("Aux")]

        ret = ActorMixer.new(
            self.nid,
            bus,
            parent=parent,
            props=self.properties,
        )
        ret.attach(child)

        return ret

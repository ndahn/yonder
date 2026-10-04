from typing import Any, ClassVar, Callable
from dearpygui import dearpygui as dpg

from yonder import Soundbank, calc_hash
from yonder.types import HIRCNode, LayerContainer
from yonder.gui.designer.graph_designer_nodes import GraphDesignerNode
from yonder.gui.localization import μ


NO_LAYER = "None"


class LCNode(GraphDesignerNode):
    """A LayerContainer, playing one of its children based on a game sync."""

    node_type: ClassVar[type[HIRCNode]] = LayerContainer
    label: ClassVar[str] = "LayerContainer"
    inputs: ClassVar[tuple[str, ...]] = ("Playback", "Event")
    outputs: ClassVar[tuple[str, ...]] = ("Item0",)

    def __init__(self, nid: str | int = 0):
        super().__init__(nid)

        self.layer_assignments: dict[str, str] = {}
        self._layer_widgets: dict[str, str] = {}

    def build_body(self) -> None:
        # TODO layer configs
        pass

    def add_terminal(
        self,
        label: str,
        is_input: bool,
        *,
        before: str = None,
        widget: Callable[[], None] = None,
    ) -> str:
        if label.startswith("Item"):
            widget = self._make_item_terminal

        super().add_terminal(label, is_input, before=before, widget=widget)

    def remove_terminal(self, label: str, is_input: bool) -> None:
        self._layer_widgets.pop(label, None)
        super().remove_terminal(label, is_input)

    def on_connections_changed(self, inputs: set[str], outputs: set[str]) -> None:
        # Always keep exactly one free item slot at the bottom
        items = [o for o in self.get_terminals(False) if o.startswith("Item")]
        last_used = max(
            (i for i, label in enumerate(items) if label in outputs), default=-1
        )
        wanted = last_used + 2

        for label in items[wanted:]:
            self.remove_terminal(label, False)

        for i in range(len(items), wanted):
            self.add_terminal(f"Item{i}", False)

    def link_valid(
        self,
        source: GraphDesignerNode,
        output: str,
        target: GraphDesignerNode,
        input: str,
    ) -> bool:
        if source is self:
            return output.startswith("Item") and input == "Playback"

        return super().link_valid(source, output, target, input)

    def make_node(
        self, bnk: Soundbank, input_map: dict[str, int], output_map: dict[str, int]
    ) -> LayerContainer:
        parent = input_map.get("Playback", 0)

        lc = LayerContainer.new(
            self.node_id(),
            props=self.properties,
            parent=parent,
        )

        for terminal, layer in sorted(set(self.layer_assignments.items())):
            child = output_map.get(terminal)
            if child:
                layer_id = calc_hash(layer) if layer != NO_LAYER else None
                lc.attach(child, layer_id)

        return lc

    # === Helpers =======================================================

    def get_layer_items(self) -> list[str]:
        layers = set(self.layer_assignments.values())
        layers.discard(NO_LAYER)

        highest = max(
            (int(layer.split(" ")[-1]) for layer in layers),
            default=-1,
        )

        # Find the first unused layer and add it as well
        for i in range(highest + 2):
            if f"Layer {i}" not in layers:
                layers.add(f"Layer {i}")
                break

        return [NO_LAYER] + sorted(layers)

    def _make_item_terminal(self, label: str, is_input: bool) -> None:
        layers = self.get_layer_items()
        widget = dpg.add_combo(
            layers,
            default_value=layers[0],
            callback=self._on_layer_changed,
            width=self.body_width,
            user_data=label,
        )
        self._layer_widgets[label] = widget
        self.layer_assignments[label] = layers[0]

    # === DPG callbacks =================================================

    def _on_layer_changed(self, sender: str, layer: str, terminal: str) -> None:
        self.layer_assignments[terminal] = layer

        layers = self.get_layer_items()
        for widget in self._layer_widgets.values():
            dpg.configure_item(widget, items=layers)

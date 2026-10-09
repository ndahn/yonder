from typing import ClassVar, Any
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.util import logger
from yonder.gui.designer.graph_designer_node import GraphDesignerNode, can_reference
from yonder.gui import style, μ, Icons
from yonder.types import HIRCNode
from yonder.gui.widgets import add_select_node


class ReferenceNode(GraphDesignerNode):
    """A reference to or from another node."""

    node_type: ClassVar[type[HIRCNode]] = HIRCNode
    label: ClassVar[str] = "Reference"
    color: ClassVar[style.RGBA] = style.RGBA(64, 92, 250)
    icon: ClassVar[str] = Icons.object
    show_name_field: ClassVar[bool] = False
    inputs: ClassVar[tuple[str, ...]] = ("Parent",)
    outputs: ClassVar[tuple[str, ...]] = ()

    def __init__(
        self,
        bnk: Soundbank,
        nid: str | int = 0,
    ):
        super().__init__(bnk, nid)
        self._bnk = bnk
        self._node_selector: add_select_node = None

    def build_body(self) -> None:
        self._node_selector = add_select_node(
            self._bnk,
            textbox_width=self.body_width,
            tag=self._wtag("node_selector"),
        )
        dpg.add_radio_button(
            ["Target", "Source"],
            default_value="Target",
            callback=self._on_mode_changed,
        )
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text(
                µ(
                    "Warning: most nodes can only have one parent - this can change the structure of existing nodes."
                ),
                wrap=240,
                color=style.yellow,
            )

    def _on_mode_changed(self, sender: str, mode: str, user_data: Any) -> None:
        if mode == "Source":
            self.remove_terminal("Parent", True)
            self.add_terminal("Child", False)
        else:
            self.add_terminal("Parent", True)
            self.remove_terminal("Child", False)

    def link_valid(
        self,
        source: GraphDesignerNode,
        output: str,
        target: GraphDesignerNode,
        input: str,
    ) -> bool:
        node = self._node_selector.selected_node
        if not node:
            logger.warning("Select a target node first")
            return False

        # Verify this node can be referenced by its parent
        if isinstance(node, HIRCNode):
            if source is self:
                return can_reference(type(node), target.node_type)
            if target is self:
                return can_reference(source.node_type, type(node))

        return super().link_valid(source, output, target, input)

    def validate(
        self, bnk: Soundbank, input_map: dict[str, int], output_map: dict[str, int]
    ) -> str:
        node = self._node_selector.selected_node
        if not node:
            return µ("No node selected")

        return super().validate(bnk, input_map, output_map)

    def make_node(
        self, bnk: Soundbank, input_map: dict[str, int], output_map: dict[str, int]
    ) -> HIRCNode:
        return self._node_selector.selected_node

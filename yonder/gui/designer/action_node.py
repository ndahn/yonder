from typing import Any, ClassVar
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.enums import ActionType
from yonder.gui.designer.graph_designer_nodes import GraphDesignerNode, can_reference
from yonder.gui.localization import μ
from yonder.types import HIRCNode, Action


class ActionNode(GraphDesignerNode):
    """An Action that starts, stops, or otherwise modifies playback of a hierarchy."""

    node_type: ClassVar[type[HIRCNode]] = Action
    label: ClassVar[str] = "Action"
    inputs: ClassVar[tuple[str, ...]] = ("Event",)
    outputs: ClassVar[tuple[str, ...]] = ("Target",)

    def __init__(
        self,
        nid: str | int = 0,
        *,
        action_type: ActionType = ActionType.Play,
    ):
        super().__init__(nid)

        self.action_type = action_type
        self.is_bus = False

    def build_body(self) -> None:
        dpg.add_combo(
            [t.name for t in Action.supported_types()],
            default_value=self.action_type.name,
            width=self.body_width,
            callback=self._on_action_type_changed,
            tag=self._wtag("action_type"),
        )
        dpg.add_checkbox(
            label=µ("is bus"),
            default_value=False,
            callback=self._on_is_bus_changed,
            tag=self._wtag("is_bus"),
        )

    def link_valid(
        self,
        source: GraphDesignerNode,
        output: str,
        target: GraphDesignerNode,
        input: str,
    ) -> bool:
        if source is self:
            return output == "Target" and input == "Playback"

        return super().link_valid(source, output, target, input)

    def validate(self, bnk: Soundbank) -> str:
        if self.action_type not in Action.supported_types():
            return µ("{action} cannot be created yet", "msg").format(
                action=self.action_type.name
            )

        return super().validate(bnk)

    def make_node(
        self, bnk: Soundbank, input_map: dict[str, int], output_map: dict[str, int]
    ) -> Action:
        target = output_map.get("Target", 0)

        if self.action_type == ActionType.Play:
            # The only param that can't be defaulted sensibly
            return Action.new_play(
                self.nid, target, bank_id=bnk.bank_id, props=self.properties
            )

        return Action.new(
            self.nid, self.action_type, target, props=self.properties, is_bus=self.is_bus
        )

    # === DPG callbacks =================================================

    def _on_action_type_changed(self, sender: str, action_type: str, user_data: Any) -> None:
        self.action_type = ActionType[action_type]
        is_play = (self.action_type == ActionType.Play)
        dpg.configure_item(self._wtag("is_bus"), enabled=not is_play)

    def _on_is_bus_changed(self, sender: str, is_bus: bool, user_data: Any) -> None:
        self.is_bus = is_bus
from yonder import Soundbank
from yonder.enums import ActionType
from yonder.gui.designer.graph_designer_nodes import GraphDesignerNode, can_reference
from yonder.gui.localization import μ
from yonder.types import HIRCNode, Action, Event


from dearpygui import dearpygui as dpg


from typing import Any, ClassVar


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

    def build_body(self) -> None:
        dpg.add_combo(
            [a.name for a in ActionType],
            default_value=self.action_type.name,
            width=self.body_width,
            callback=self._on_action_type_changed,
            tag=self._wtag("action_type"),
        )

    def link_valid(
        self,
        source: GraphDesignerNode,
        output: str,
        target: GraphDesignerNode,
        input: str,
    ) -> bool:
        return can_reference(source.node_type, target.node_type)

    def make_node(self, bnk: Soundbank) -> Action:
        # TODO handle different action types
        print("##### WARNING not handling action type yet!!!")
        ret = Action.new_play_action(self.nid, 0)
        ret.properties = [(p, v) for p, v in self.properties.items()]
        return ret

    # === DPG callbacks =================================================

    def _on_action_type_changed(self, sender: str, action_type: str, user_data: Any) -> None:
        self.action_type = ActionType[action_type]

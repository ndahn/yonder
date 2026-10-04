from yonder import Soundbank
from yonder.enums import ActionType
from yonder.gui.designer.graph_designer_nodes import GraphDesignerNode, can_reference
from yonder.gui.localization import μ
from yonder.types import HIRCNode, Action, Event


from dearpygui import dearpygui as dpg


from typing import Any, ClassVar


class EventNode(GraphDesignerNode):
    """An Event that will trigger playback of a node. When built this creates both a Play and a StopEO action."""

    node_type: ClassVar[type[HIRCNode]] = Event
    label: ClassVar[str] = "Event"
    show_name_field: ClassVar[bool] = True
    inputs: ClassVar[tuple[str, ...]] = ()
    outputs: ClassVar[tuple[str, ...]] = ("Play/Stop", "Extra0")

    def __init__(
        self,
        nid: str | int = 0,
        *,
        name: str = "c100200300",
    ):
        super().__init__(nid)
        self.name = name

        self.extra_actions: list[str] = []
        self._play: Action = None
        self._stop: Action = None

    def build_body(self) -> None:
        pass

    def on_connections_changed(self, inputs: set[str], outputs: set[str]) -> None:
        # Always keep exactly one free extra slot at the bottom
        items = [o for o in self.get_terminals(False) if o.startswith("Extra")]
        last_used = max(
            (i for i, label in enumerate(items) if label in outputs), default=-1
        )
        wanted = last_used + 2

        for label in items[wanted:]:
            self.remove_terminal(label, False)

        for i in range(len(items), wanted):
            self.add_terminal(f"Extra{i}", False)

    def link_valid(
        self,
        source: GraphDesignerNode,
        output: str,
        target: GraphDesignerNode,
        input: str,
    ) -> bool:
        if source is self and input == "Event":
            if output == "Play/Stop":
                return hasattr(target.node_type, "parent")
            elif output.startswith("Extra"):
                return target.node_type is Action

        return False

    def make_node(self, bnk: Soundbank) -> tuple[Event, Action, Action]:
        self._play = Action.new_play_action(bnk.new_id(), 0, bank_id=bnk.bank_id)
        self._stop = Action.new_stop_action(bnk.new_id(), 0)
        evt = Event.new(self.nid, [self._play.id, self._stop.id])
        return evt

    def connect(
        self,
        bnk: Soundbank,
        my_node: HIRCNode,
        output: str,
        other: GraphDesignerNode,
        other_node: HIRCNode,
        input: str,
    ) -> None:
        self._play.external_id = other_node.id
        self._stop.external_id = other_node.id

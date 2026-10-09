from typing import ClassVar
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.gui.designer.graph_designer_node import GraphDesignerNode
from yonder.gui.localization import μ
from yonder.types import HIRCNode, Action, Event


class EventNode(GraphDesignerNode):
    """An Event that will trigger playback of a node. When built this creates both a Play and a StopEO action."""

    node_type: ClassVar[type[HIRCNode]] = Event
    label: ClassVar[str] = "Event"
    show_name_field: ClassVar[bool] = True
    inputs: ClassVar[tuple[str, ...]] = ()
    outputs: ClassVar[tuple[str, ...]] = ("Play/Stop", "Extra0")

    def __init__(
        self,
        bnk: Soundbank,
        nid: str | int = 0,
        *,
        name: str = "c100200300",
    ):
        super().__init__(bnk, nid)
        self.name = name

        self.extra_actions: list[str] = []
        self._play: Action = None
        self._stop: Action = None

    def build_body(self) -> None:
        pass

    def on_connections_changed(
        self,
        inputs: dict[str, GraphDesignerNode],
        outputs: dict[str, GraphDesignerNode],
    ) -> None:
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
        if source is self:
            if input != "Event":
                return False
            if output == "Play/Stop":
                return hasattr(target.node_type, "parent")
            elif output.startswith("Extra"):
                return target.node_type is Action

        return super().link_valid(source, output, target, input)

    def validate(
        self, bnk: Soundbank, input_map: dict[str, int], output_map: dict[str, int]
    ) -> str:
        if "Play/Stop" not in input_map:
            return µ("Play/Stop not connected")

        return super().validate(bnk, input_map, output_map)

    def make_node(
        self, bnk: Soundbank, input_map: dict[str, int], output_map: dict[str, int]
    ) -> tuple[Event, Action, Action]:
        target = output_map.get("Play/Stop", 0)
        extras = [
            aid
            for terminal, aid in sorted(output_map.items())
            if terminal.startswith("Extra") and aid > 0
        ]

        play = Action.new_play(bnk.new_id(), target, bank_id=bnk.bank_id)
        stop = Action.new_stop(bnk.new_id(), target)
        evt = Event.new(self.nid, [self._play.id, self._stop.id] + extras)

        return (evt, play, stop)

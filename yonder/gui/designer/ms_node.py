from typing import Any, ClassVar, Callable
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.types import HIRCNode, MusicSegment, MusicTrack
from yonder.enums import MarkerId
from yonder.gui.designer.graph_designer_nodes import GraphDesignerNode
from yonder.gui.localization import μ
from yonder.gui.widgets import add_marker_editor


class MSNode(GraphDesignerNode):
    """A MusicSegment, playing one or more music tracks."""

    node_type: ClassVar[type[HIRCNode]] = MusicSegment
    label: ClassVar[str] = "MusicSegment"
    inputs: ClassVar[tuple[str, ...]] = ("Playback", "Event")
    outputs: ClassVar[tuple[str, ...]] = ("Track 0",)

    def __init__(self, nid: str | int = 0, *, switch_group: str | int = None):
        super().__init__(nid)

        self.duration = 0.0
        self._segment = MusicSegment.new(nid)

    def build_body(self) -> None:
        dpg.add_text("0.0s total", tag=self._wtag("duration"))

        # TODO button to open track arranger

        with dpg.tree_node(label=µ("Markers"), span_text_width=True):
            add_marker_editor(self._segment, None, compact=True)

    def on_connections_changed(
        self,
        inputs: dict[str, GraphDesignerNode],
        outputs: dict[str, GraphDesignerNode],
    ) -> None:
        # Always keep exactly one free item slot at the bottom
        items = [o for o in self.get_terminals(False) if o.startswith("Track")]
        last_used = max(
            (i for i, label in enumerate(items) if label in outputs), default=-1
        )
        wanted = last_used + 2

        for label in items[wanted:]:
            self.remove_terminal(label, False)

        for i in range(len(items), wanted):
            self.add_terminal(f"Track {i}", False)

        # Update duration
        dur = 0.0
        for node in outputs.values():
            if node.node_type == MusicTrack:
                dur += node.duration

        self.duration = dur
        dpg.set_value(self._wtag("duration"), f"{dur:.1d}s total")

    def link_valid(
        self,
        source: GraphDesignerNode,
        output: str,
        target: GraphDesignerNode,
        input: str,
    ) -> bool:
        if source is self:
            return (
                output.startswith("Track")
                and target.node_type is MusicTrack
                and input == "Playback"
            )

        return super().link_valid(source, output, target, input)

    def make_node(
        self, bnk: Soundbank, input_map: dict[str, int], output_map: dict[str, int]
    ) -> MusicSegment:
        parent = input_map.get("Playback", 0)
        markers = {m.id: m.position for m in self._segment.markers}

        return MusicSegment.new(
            self.node_id(),
            markers=markers,
            props=self.properties,
            parent=parent,
        )

    # === DPG callbacks =================================================

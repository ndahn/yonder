from typing import Any, ClassVar
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.enums import PlaybackMode, RandomMode
from yonder.gui.designer.graph_designer_node import GraphDesignerNode, can_reference
from yonder.gui.localization import μ
from yonder.types import HIRCNode, RandomSequenceContainer


class RSCNode(GraphDesignerNode):
    """A RandomSequenceContainer, playing one or all of its children."""

    node_type: ClassVar[type[HIRCNode]] = RandomSequenceContainer
    label: ClassVar[str] = "RandomSequenceContainer"
    inputs: ClassVar[tuple[str, ...]] = ("Playback", "Event")
    outputs: ClassVar[tuple[str, ...]] = ("Item 0",)

    def __init__(
        self,
        bnk: Soundbank,
        nid: str | int = 0,
        *,
        mode: PlaybackMode = PlaybackMode.Random,
        random_mode: RandomMode = RandomMode.Standard,
        loop_count: int = 1,
    ):
        super().__init__(bnk, nid)

        self.mode = mode
        self.random_mode = random_mode
        self.loop_count = loop_count

    def build_body(self) -> None:
        dpg.add_combo(
            [p.name for p in PlaybackMode],
            default_value=self.mode.name,
            width=self.body_width,
            callback=self._on_mode_changed,
            tag=self._wtag("mode"),
        )
        dpg.add_combo(
            [r.name for r in RandomMode],
            default_value=self.random_mode.name,
            width=self.body_width,
            callback=self._on_random_mode_changed,
            tag=self._wtag("random_mode"),
        )
        dpg.add_input_int(
            label=µ("Loops"),
            default_value=self.loop_count,
            min_value=0,
            min_clamped=True,
            width=self.body_width - 50,
            callback=self._on_loop_count_changed,
            tag=self._wtag("loop_count"),
        )
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text(µ("0 means infinite", "tips"))

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
            self.add_terminal(f"Item {i}", False)

    def link_valid(
        self,
        source: GraphDesignerNode,
        output: str,
        target: GraphDesignerNode,
        input: str,
    ) -> bool:
        if source is self:
            return output.startswith("Item") and input == "Playback"

        # Either a parent container plays us, or an action targets us
        return can_reference(source.node_type, target.node_type)

    def validate(
        self, bnk: Soundbank, input_map: dict[str, int], output_map: dict[str, int]
    ) -> str:
        if "Playback" not in input_map:
            return µ("Playback not connected")
        
        return super().validate(bnk, input_map, output_map)

    def make_node(
        self, bnk: Soundbank, input_map: dict[str, int], output_map: dict[str, int]
    ) -> RandomSequenceContainer:
        parent = input_map.get("Playback", 0)
        children = []

        for terminal in self.get_terminals(False):
            child = output_map.get(terminal)
            if child:
                children.append(child)

        return RandomSequenceContainer.new(
            self.node_id(),
            nodes=children,
            playback_mode=self.mode,
            random_mode=self.random_mode,
            loop_count=self.loop_count,
            props=self.properties,
            parent=parent,
        )

    # === DPG callbacks =================================================

    def _on_mode_changed(self, sender: str, mode: str, user_data: Any) -> None:
        self.mode = PlaybackMode[mode]

    def _on_random_mode_changed(self, sender: str, mode: str, user_data: Any) -> None:
        self.random_mode = RandomMode[mode]

    def _on_loop_count_changed(self, sender: str, count: int, user_data: Any) -> None:
        self.loop_count = count

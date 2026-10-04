from typing import Any, ClassVar, Callable
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.types import HIRCNode, SwitchContainer
from yonder.enums import PlaybackMode, RandomMode
from yonder.game import get_selected_game
from yonder.gui.designer.graph_designer_nodes import GraphDesignerNode, can_reference
from yonder.gui.localization import μ
from yonder.gui.widgets import add_state_value_input


class SCNode(GraphDesignerNode):
    """A SwitchContainer, playing one of its children based on a game sync."""

    node_type: ClassVar[type[HIRCNode]] = SwitchContainer
    label: ClassVar[str] = "SwitchContainer"
    inputs: ClassVar[tuple[str, ...]] = ("Playback", "Event")
    outputs: ClassVar[tuple[str, ...]] = ("Switch0",)

    def __init__(
        self,
        nid: str | int = 0,
        *,
        switch_group: str | int = None
    ):
        super().__init__(nid)

        self.switch_group = switch_group
        self._items: dict[str, str] = {}

    def build_body(self) -> None:
        game = get_selected_game()
        
        add_state_value_input(
            game.game_syncs.states,
            self._on_switch_group_changed,
            tag=self._wtag("switch_group")
        )

    def add_terminal(
        self,
        label: str,
        is_input: bool,
        *,
        before: str = None,
        widget: Callable[[], None] = None,
    ) -> str:
        if label.startswith("Switch"):
            widget = self._make_switch_terminal

        super().add_terminal(label, is_input, before=before, widget=widget)

    def on_connections_changed(self, inputs: set[str], outputs: set[str]) -> None:
        # Always keep exactly one free item slot at the bottom
        items = [o for o in self.get_terminals(False) if o.startswith("Switch")]
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

        # Either a parent container plays us, or an action targets us
        return can_reference(source.node_type, target.node_type)

    def make_node(self, bnk: Soundbank) -> SwitchContainer:
        return SwitchContainer.new(
            self.node_id(),
            playback_mode=self.mode,
            random_mode=self.random_mode,
            loop_count=self.loop_count,
            props=self.properties,
        )

    # === DPG callbacks =================================================

    def _on_switch_group_changed(self, sender: str, switch_group: str, user_data: Any) -> None:
        self.switch_group = switch_group

    def _make_switch_terminal(self, label: str, is_input: bool) -> None:
        game = get_selected_game()

        add_state_value_input(
            game.game_syncs.states.get(self.switch_group, None),
            self._on_switch_changed,
            user_data=(label, is_input),
        )

    def _on_switch_changed(self, sender: str, switch: str, user_data: Any) -> None:
        pass

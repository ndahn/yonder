from typing import Any, ClassVar, Callable
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.types import HIRCNode, SwitchContainer
from yonder.game import get_selected_game
from yonder.gui.designer.graph_designer_nodes import GraphDesignerNode
from yonder.gui.localization import μ
from yonder.gui.widgets import add_state_value_input


class SCNode(GraphDesignerNode):
    """A SwitchContainer, playing one of its children based on a game sync."""

    node_type: ClassVar[type[HIRCNode]] = SwitchContainer
    label: ClassVar[str] = "SwitchContainer"
    inputs: ClassVar[tuple[str, ...]] = ("Playback", "Event")
    outputs: ClassVar[tuple[str, ...]] = ("Switch0",)

    def __init__(self, nid: str | int = 0, *, switch_group: str | int = None):
        super().__init__(nid)

        self.switch_group = switch_group
        self.switches: dict[str, str] = {}  # terminal to switch state
        self._game = get_selected_game()
        self._switch_group_widget: add_state_value_input = None
        self._switch_widgets: dict[str, add_state_value_input] = {}

    def build_body(self) -> None:
        self._switch_group_widget = add_state_value_input(
            self._game.game_syncs.states,
            self._on_switch_group_changed,
            tag=self._wtag("switch_group"),
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
            widget = self._make_item_terminal

        super().add_terminal(label, is_input, before=before, widget=widget)

    def remove_terminal(self, label: str, is_input: bool) -> None:
        self._switch_widgets.pop(label, None)
        super().remove_terminal(label, is_input)

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
            self.add_terminal(f"Switch{i}", False)

    def link_valid(
        self,
        source: GraphDesignerNode,
        output: str,
        target: GraphDesignerNode,
        input: str,
    ) -> bool:
        if source is self:
            return output.startswith("Switch") and input == "Playback"

        return super().link_valid(source, output, target, input)

    def validate(self, bnk: Soundbank) -> str:
        if not self.switch_group:
            return µ("Switch group not set")

        for val in self.switches.values():
            if not val:
                return µ("Terminal switch not set")

        return super().validate(bnk)

    def make_node(
        self, bnk: Soundbank, input_map: dict[str, int], output_map: dict[str, int]
    ) -> SwitchContainer:
        parent = input_map.get("Playback", 0)
        switch_map = {}

        for terminal, state in sorted(self.switches.items()):
            child = output_map.get(terminal)
            if child:
                switch_map[state] = child

        return SwitchContainer.new(
            self.node_id(),
            switch_group=self.switch_group,
            switch_states=switch_map,
            props=self.properties,
            parent=parent,
        )

    # === Helpers =======================================================

    def get_free_states(self, exclude: str | list[str] = None) -> list[str]:
        if not exclude:
            exclude = []
        elif isinstance(exclude, str):
            exclude = [exclude]

        used = set(self.switches.values())
        used.update(exclude)

        states = set(self._game.game_syncs.states.get(self.switch_group, []))
        return sorted(states.difference(used))

    def update_combo_items(self) -> None:
        for widget in self._switch_widgets.values():
            widget.items = self.get_free_states(exclude=widget.string_value)

    def _make_item_terminal(self, label: str, is_input: bool) -> None:
        widget = add_state_value_input(
            self.get_free_states(),
            self._on_switch_changed,
            user_data=(label, is_input),
        )
        self._switch_widgets[label] = widget
        self.switches[label] = None

    # === DPG callbacks =================================================

    def _on_switch_group_changed(
        self, sender: str, switch_group: str, user_data: Any
    ) -> None:
        self.switch_group = switch_group
        self.update_combo_items()

    def _on_switch_changed(self, sender: str, switch: str, user_data: Any) -> None:
        self.switches = {
            terminal: dpg.get_value(self._switch_widgets[terminal])
            for terminal in self._outputs
            if terminal.startswith("Switch")
        }
        self.update_combo_items()

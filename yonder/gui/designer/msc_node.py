from typing import Any, ClassVar
from copy import deepcopy
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.types import HIRCNode, MusicSwitchContainer
from yonder.types.base_types import DecisionTreeNode, GameSync
from yonder.gui.localization import μ
from yonder.gui.designer.graph_designer_nodes import GraphDesignerNode, can_reference
from yonder.gui.widgets import add_decision_tree_editor


class MSCNode(GraphDesignerNode):
    """A MusicSwitchContainer, playing one of its children based on a decision tree."""

    node_type: ClassVar[type[HIRCNode]] = MusicSwitchContainer
    label: ClassVar[str] = "MusicSwitchContainer"
    inputs: ClassVar[tuple[str, ...]] = ("Playback", "Event")
    # One output per leaf of the decision tree, see _sync_terminals()
    outputs: ClassVar[tuple[str, ...]] = ()

    def __init__(self, nid: str | int = 0):
        super().__init__(nid)

        # The container doubles as the working copy of the decision tree. Only the
        # tree and its arguments are used, the real node is built in make_node().
        self.tree: MusicSwitchContainer = MusicSwitchContainer(self.nid)
        self._tree_editor: add_decision_tree_editor = None

    def build(self, parent: str | int, pos: tuple[float, float] = None) -> None:
        super().build(parent, pos)
        self._sync_terminals()

    def build_body(self) -> None:
        with dpg.tree_node(label=µ("Decision Tree"), span_text_width=True):
            self._tree_editor = add_decision_tree_editor(
                self.tree,
                self._on_tree_changed,
                compact=True,
            )

    def link_valid(
        self,
        source: GraphDesignerNode,
        output: str,
        target: GraphDesignerNode,
        input: str,
    ) -> bool:
        if source is self:
            return output.startswith("Switch") and input == "Playback"

        # Either a parent container plays us, or an action targets us
        return can_reference(source.node_type, target.node_type)

    def validate(self, bnk: Soundbank) -> str:
        if not self.tree.arguments:
            return µ("Decision tree has no decisions")

        branches = list(self._tree_editor.branches())
        if not branches:
            return µ("Decision tree has no branches")

        for path, _ in branches:
            if 999999 in path:
                return µ("Decision tree branch value not set")

        return super().validate(bnk)

    def make_node(
        self, bnk: Soundbank, input_map: dict[str, int], output_map: dict[str, int]
    ) -> MusicSwitchContainer:
        parent = input_map.get("Playback", 0)

        # Resolve the leaves against the nodes connected to our terminals
        for _, branch in self._tree_editor.branches():
            label = self._tree_editor.get_branch_label(branch)
            branch.node_id = output_map.get(label, 0)

        # The tree is already exactly what the user built, so take it as is instead
        # of replaying it branch by branch
        node = MusicSwitchContainer.new(
            self.node_id(), [], props=self.properties, parent=parent
        )
        node.arguments = [GameSync(a.group_id) for a in self.tree.arguments]
        node.group_types = list(self.tree.group_types)
        node.tree_depth = len(node.arguments)
        node.tree_mode = self.tree.tree_mode
        node.tree = deepcopy(self.tree.tree)
        self._prune_tree(node, node.tree, 0)

        for child_id in node.get_flat_tree(string_keys=False).values():
            if child_id > 0:
                node.children.add(child_id)

        return node

    # === Helpers =======================================================

    def _sync_terminals(self) -> None:
        """One output terminal per leaf of the decision tree."""
        labels = [
            self._tree_editor.get_branch_label(branch)
            for _, branch in self._tree_editor.branches()
        ]

        for label in list(self._outputs):
            if label not in labels:
                self.remove_terminal(label, False)

        for label in labels:
            self.add_terminal(label, False)

    @staticmethod
    def _prune_tree(
        node: MusicSwitchContainer, branch: DecisionTreeNode, depth: int
    ) -> bool:
        """Drop branches that don't lead anywhere, i.e. whose terminal is unused."""
        if depth == len(node.arguments):
            return branch.node_id > 0

        branch.children = [
            c for c in branch.children if MSCNode._prune_tree(node, c, depth + 1)
        ]
        branch.child_count = len(branch.children)
        return bool(branch.children)

    # === DPG callbacks =================================================

    def _on_tree_changed(
        self, sender: str, tree: MusicSwitchContainer, user_data: Any
    ) -> None:
        self.tree = tree
        self._sync_terminals()

from __future__ import annotations
from typing import Any, Callable, Iterator, TYPE_CHECKING
from dearpygui import dearpygui as dpg

from yonder.hash import Hash, lookup_name
from yonder.enums import DecisionTreeMode, GroupType
from yonder.util import logger
from yonder.game import get_selected_game
from yonder.types.base_types import DecisionTreeNode
from yonder.gui.localization import µ
from .dpg_item import DpgItem
from .hash_widget import add_hash_widget
from .state_value_input import add_state_value_input

if TYPE_CHECKING:
    from yonder import Soundbank
    from yonder.types.mixins import DecisionTreeMixin


class add_decision_tree_editor(DpgItem):
    """Editor for the decision tree of a MusicSwitchContainer or DialogueEvent.

    The tree is rendered as nested dpg tree nodes, one per decision, labelled
    ``<argument> = <value>``. Right clicking a row opens a context menu to
    change its value, to add or delete branches and to insert or remove whole
    decision levels. Leaves are filled by `leaf_widget`, which defaults to the
    branch's stable label - the editor doesn't know how a leaf's target node is
    picked, that's up to whoever embeds it.

    The editor mutates `owner` in place and reports every change through
    `on_value_changed`. Structural changes are applied to the live widgets by
    regenerating, so embedders don't have to rebuild anything themselves.

    Parameters
    ----------
    owner : DecisionTreeMixin
        The node owning the tree, i.e. its `tree`, `arguments`, `group_types`
        and `tree_mode`. Edited in place.
    on_value_changed : callable
        Called as ``on_value_changed(tag, owner, user_data)`` after any change.
    bnk : Soundbank, optional
        Enables picking a target node when adding a branch. Without it a new
        branch is created unassigned.
    label : str, optional
        Label of the tree section, defaults to "Decision Tree".
    leaf_widget : callable, optional
        Called as ``leaf_widget(branch, label)`` to fill a leaf row.
    on_branch_removed : callable, optional
        Called as ``on_branch_removed(tag, branch, user_data)`` with the subtree
        that was just removed, e.g. to collect the nodes it orphaned.
    show_tree_mode : bool
        Whether to show the combo for the tree's match mode.
    compact : bool
        Drop the surrounding tree section and stretch the widgets, for use
        inside narrow parents such as graph designer nodes.
    tag : int or str
        Explicit tag; auto-generated if 0.
    user_data : any
        Passed through to the callbacks.
    """

    def __init__(
        self,
        owner: DecisionTreeMixin,
        on_value_changed: Callable[[str, DecisionTreeMixin, Any], None],
        *,
        bnk: Soundbank = None,
        label: str = None,
        leaf_widget: Callable[[DecisionTreeNode, str], None] = None,
        on_branch_removed: Callable[[str, DecisionTreeNode, Any], None] = None,
        show_tree_mode: bool = True,
        compact: bool = False,
        tag: str | int = 0,
        user_data: Any = None,
    ) -> None:
        super().__init__(tag)

        self.owner = owner
        self._bnk = bnk
        self._on_value_changed = on_value_changed
        self._leaf_widget = leaf_widget
        self._on_branch_removed = on_branch_removed
        self._user_data = user_data

        # Registries for the per row context menu, recreated on every regenerate
        self._registries: list[str] = []
        self._branch_label_indices: dict[int, int] = {}

        self._build(label, show_tree_mode, compact)

    def destroy(self) -> None:
        self._clear_rows()

        for suffix in ("tree_mode", "tree", "button_add_branch", "button_add_decision"):
            self._delete_item(self._t(suffix))

    # === Build =========================================================

    def _build(self, label: str, show_tree_mode: bool, compact: bool) -> None:
        with dpg.group(tag=self.tag):
            if show_tree_mode:
                dpg.add_combo(
                    [m.name for m in DecisionTreeMode],
                    default_value=self.owner.tree_mode.name,
                    width=-1 if compact else 0,
                    callback=self._on_tree_mode_changed,
                    tag=self._t("tree_mode"),
                )
                with dpg.tooltip(dpg.last_item()):
                    dpg.add_text(µ("How closely a state path has to match"))

            if compact:
                # The embedding node provides the heading
                dpg.add_group(tag=self._t("tree"))
            else:
                dpg.add_tree_node(
                    label=label or µ("Decision Tree"),
                    default_open=True,
                    span_full_width=True,
                    tag=self._t("tree"),
                )

            dpg.add_spacer(height=3)
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label=µ("+ Branch", "button"),
                    callback=self._on_add_branch_dialog,
                    tag=self._t("button_add_branch"),
                )
                dpg.add_button(
                    label=µ("+ Decision", "button"),
                    callback=self._on_append_decision,
                    tag=self._t("button_add_decision"),
                )

        self.regenerate()

    def regenerate(self) -> None:
        """Rebuild the rows from the owner's tree."""
        self._clear_rows()
        self._prune_branch_labels()

        dpg.configure_item(
            self._t("button_add_branch"), enabled=bool(self.owner.arguments)
        )

        if not self.owner.arguments:
            dpg.add_text(
                µ("No decisions yet"), parent=self._t("tree"), color=(150, 150, 150)
            )
            return

        for child in sorted(self.owner.tree.children, key=self._sort_key):
            self._delve(child, 0, parent=self._t("tree"))

    def _clear_rows(self) -> None:
        if dpg.does_item_exist(self._t("tree")):
            dpg.delete_item(self._t("tree"), children_only=True)

        for registry in self._registries:
            if dpg.does_item_exist(registry):
                dpg.delete_item(registry)

        self._registries.clear()

    def _delve(
        self, branch: DecisionTreeNode, level: int, parent: str | int = 0
    ) -> None:
        # Nested rows land inside the row we are currently building
        with dpg.tree_node(span_full_width=True, parent=parent) as row:
            if level == len(self.owner.arguments) - 1:
                label = self.get_branch_label(branch)
                if self._leaf_widget:
                    self._leaf_widget(branch, label)
                else:
                    dpg.add_text(label)
            else:
                for child in sorted(branch.children, key=self._sort_key):
                    self._delve(child, level + 1)

        self._bind_context_menu(row, branch, level)
        self._update_row_label(row, branch, level)

    def _bind_context_menu(
        self, row: str | int, branch: DecisionTreeNode, level: int
    ) -> None:
        registry = dpg.add_item_handler_registry()
        self._registries.append(registry)

        dpg.add_item_clicked_handler(
            dpg.mvMouseButton_Right,
            callback=self._open_context_menu,
            user_data=(row, branch, level),
            parent=registry,
        )
        dpg.bind_item_handler_registry(row, registry)

    # === Labels ========================================================

    @staticmethod
    def _sort_key(branch: DecisionTreeNode) -> str:
        return branch.name

    def _argument_name(self, level: int) -> str:
        arg = self.owner.arguments[level].group_id
        return lookup_name(arg, f"#{arg}")

    @staticmethod
    def get_value_name(branch: DecisionTreeNode) -> str:
        """The branch's key as text, with the wildcard key spelled out."""
        if branch.key == 0:
            return "*"

        return lookup_name(branch.key, f"#{branch.key}")

    def _update_row_label(
        self, row: str | int, branch: DecisionTreeNode, level: int
    ) -> None:
        label = f"{self._argument_name(level)} = {self.get_value_name(branch)}"
        dpg.set_item_label(row, label)

    def get_branch_label(self, branch: DecisionTreeNode) -> str:
        """A user friendly label for a leaf, stable across tree edits.

        Embedders use this to tie a branch to something outside the tree, e.g.
        a terminal of a graph designer node, which must not shift around when
        other branches are added or removed.
        """
        key = id(branch)
        index = self._branch_label_indices.get(key)

        if index is None:
            used = set(self._branch_label_indices.values())
            for index in range(len(used) + 1):
                if index not in used:
                    break

            self._branch_label_indices[key] = index

        return f"Switch {index:01d}"

    def _prune_branch_labels(self) -> None:
        # Labels are keyed by identity, so entries of dropped branches have to go
        # before their ids can be handed out to new objects
        alive = {id(b) for _, b in self.branches()}
        self._branch_label_indices = {
            k: v for k, v in self._branch_label_indices.items() if k in alive
        }

    # === Public ========================================================

    def path_to(self, target: DecisionTreeNode) -> tuple[int, ...]:
        """The state path leading to a branch, or () if it is not in the tree.

        Looked up rather than remembered, so it can't go stale when the user
        changes a key somewhere above it.
        """

        def delve(node: DecisionTreeNode, path: tuple) -> tuple:
            for child in node.children:
                child_path = path + (child.key,)
                if child is target:
                    return child_path

                found = delve(child, child_path)
                if found:
                    return found

            return None

        return delve(self.owner.tree, ()) or ()

    def branches(self) -> Iterator[tuple[tuple[int, ...], DecisionTreeNode]]:
        """The leaves of the tree as ``(state path, branch)``, in display order."""
        depth = len(self.owner.arguments)
        if not depth:
            return

        todo = [((), b) for b in sorted(self.owner.tree.children, key=self._sort_key)]
        while todo:
            path, branch = todo.pop(0)
            path = path + (branch.key,)

            if len(path) == depth:
                yield (path, branch)
            else:
                todo = [
                    (path, c) for c in sorted(branch.children, key=self._sort_key)
                ] + todo

    def notify_changed(self) -> None:
        if self._on_value_changed:
            self._on_value_changed(self.tag, self.owner, self._user_data)

    # === DPG callbacks =================================================

    def _on_tree_mode_changed(self, sender: str, mode: str, ud: Any) -> None:
        self.owner.tree_mode = DecisionTreeMode[mode]
        self.notify_changed()

    def _on_key_changed(
        self,
        sender: str,
        info: tuple[Hash, str],
        branch: tuple[str, DecisionTreeNode, int],
    ) -> None:
        row, tree_node, level = branch
        new_key = info[0]

        for sibling in self.owner.get_tree_nodes_at_depth(level):
            if sibling is not tree_node and sibling.key == new_key:
                logger.error(f"A node with key {info} already exists in level {level}")
                return

        tree_node.key = new_key
        self._update_row_label(row, tree_node, level)
        self.notify_changed()

    def _on_add_branch(
        self, sender: str, app_data: Any, info: tuple[DecisionTreeNode, int]
    ) -> None:
        branch, level = info

        # Fill up whatever depth is still missing below the clicked row. The key
        # is a placeholder the user is expected to change via the context menu,
        # 0 would silently create a second wildcard next to an existing one.
        for _ in range(len(self.owner.arguments) - level - 1):
            child = DecisionTreeNode(999999)
            branch.children.append(child)
            branch.child_count += 1
            branch = child

        self.regenerate()
        self.notify_changed()

    def _on_delete_branch(
        self, sender: str, app_data: Any, info: tuple[DecisionTreeNode, int]
    ) -> None:
        branch, _ = info
        path = self.path_to(branch)
        if not path:
            logger.error(f"Branch {branch.name} is not part of the tree")
            return

        self.owner.remove_branch(list(path))
        logger.info(f"Removed branch {branch.name}")

        self.regenerate()
        self.notify_changed()

        # Last, the embedder may rebuild everything around us from here
        if self._on_branch_removed:
            self._on_branch_removed(self.tag, branch, self._user_data)

    def _on_insert_decision(
        self, sender: str, app_data: Any, info: tuple[DecisionTreeNode, int]
    ) -> None:
        _, level = info
        self._pick_argument(lambda arg: self._insert_decision(level + 1, arg))

    def _on_remove_decision(
        self, sender: str, app_data: Any, info: tuple[DecisionTreeNode, int]
    ) -> None:
        branch, level = info
        self.owner.remove_argument(self.owner.arguments[level].group_id, branch.key)
        self.regenerate()
        self.notify_changed()

    def _on_append_decision(self) -> None:
        self._pick_argument(
            lambda arg: self._insert_decision(len(self.owner.arguments), arg)
        )

    def _insert_decision(self, pos: int, arg: Hash) -> None:
        try:
            self.owner.insert_argument(pos, arg, GroupType.State)
        except ValueError as e:
            logger.error(str(e))
            return

        self.regenerate()
        self.notify_changed()

    def _on_add_branch_dialog(self) -> None:
        from yonder.gui.dialogs.edit_state_path_dialog import edit_state_path_dialog

        edit_state_path_dialog(
            self._bnk,
            self.owner.arguments,
            self._on_state_path_created,
            hide_node_id=self._bnk is None,
            raw=True,
        )

    def _on_state_path_created(
        self, sender: str, state_path: list[int], node_id: int
    ) -> None:
        try:
            self.owner.add_branch(state_path, node_id)
        except ValueError as e:
            logger.error(str(e))
            return

        self.regenerate()
        self.notify_changed()

    def _pick_argument(self, done: Callable[[Hash], None]) -> None:
        """Small popup to choose the game sync group a decision level reacts to."""
        game = get_selected_game()
        groups = sorted(game.game_syncs.states) if game else []

        def on_okay() -> None:
            arg = widget.value
            dpg.delete_item(window)
            if arg:
                done(arg)

        with dpg.window(
            label=µ("Pick Decision"),
            modal=True,
            autosize=True,
            no_saved_settings=True,
            pos=dpg.get_mouse_pos(local=False),
            on_close=lambda: dpg.delete_item(window),
        ) as window:
            dpg.add_text(µ("State group"))
            widget = add_state_value_input(groups, None, raw=True)
            dpg.add_spacer(height=3)
            dpg.add_button(label=µ("Okay", "button"), callback=on_okay)

    def _open_context_menu(
        self,
        sender: str,
        app_data: Any,
        info: tuple[str, DecisionTreeNode, int],
    ) -> None:
        row, branch, level = info

        with dpg.window(
            popup=True,
            min_size=(100, 50),
            pos=dpg.get_mouse_pos(local=False),
            no_saved_settings=True,
            on_close=lambda: dpg.delete_item(context_menu),
        ) as context_menu:
            dpg.add_text(self._argument_name(level))
            add_hash_widget(
                branch.key,
                self._on_key_changed,
                horizontal=False,
                initial_string=self.get_value_name(branch),
                string_label=µ("Value"),
                width=100,
                user_data=(row, branch, level),
            )
            dpg.add_separator()

            # TODO add options to merge with/split from branch
            dpg.add_menu_item(
                label=µ("Create branch"),
                callback=self._on_add_branch,
                user_data=(branch, level),
            )
            dpg.add_menu_item(
                label=µ("Delete branch"),
                callback=self._on_delete_branch,
                user_data=(branch, level),
            )
            dpg.add_menu_item(
                label=µ("Insert decision level"),
                callback=self._on_insert_decision,
                user_data=(branch, level),
            )
            dpg.add_menu_item(
                label=µ("Remove decision level"),
                callback=self._on_remove_decision,
                user_data=(branch, level),
            )

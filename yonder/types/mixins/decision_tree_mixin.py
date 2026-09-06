from __future__ import annotations
from typing import TYPE_CHECKING

from yonder.hash import Hash, calc_hash, lookup_name
from yonder.enums import GroupType
from yonder.util import get_key_hash, parse_state_path
from yonder.types.base_types import (
    GameSync,
    Children,
    DecisionTreeNode,
)

if TYPE_CHECKING:
    from yonder.types.hirc_node import HIRCNode


class DecisionTreeMixin:
    # Dummies, just for the type checker
    tree: DecisionTreeNode
    tree_size: int
    tree_depth: int
    arguments: list[GameSync]
    group_types: list[GroupType]
    children: Children

    
    def get_tree_size(self) -> int:
        num_tree_nodes = 1
        todo = [self.tree]
        while todo:
            item = todo.pop()
            num_tree_nodes += len(item.children)
            todo.extend(item.children)

    def get_used_state_values(self) -> dict[int, list[int]]:
        ret = {}
        todo = [(c, 0) for c in self.tree.children]

        while todo:
            branch, depth = todo.pop()
            ret.setdefault(self.arguments[depth].group_id, []).append(branch.key)

        return ret

    def get_argument_pos(self, arg: Hash) -> int:
        if isinstance(arg, str):
            arg = calc_hash(arg)

        for i, x in enumerate(self.arguments):
            if x.group_id == arg:
                return i

        return -1

    def has_argument(self, argument: Hash) -> None:
        return self.get_argument_pos(argument) >= 0

    def insert_argument(
        self,
        pos: int,
        argument: Hash,
        group_type: GroupType,
    ) -> None:
        group_id = calc_hash(argument) if isinstance(argument, str) else argument

        if self.has_argument(group_id):
            raise ValueError(f"Argument {argument} is already part of this tree")

        if pos < 0:
            pos = len(self.arguments) + pos

        # Insert into the tree
        def delve(node: DecisionTreeNode, level: int) -> None:
            if level == pos:
                new_node = DecisionTreeNode(
                    0,
                    children=node.children,
                    child_count=len(node.children),
                )
                node.children = [new_node]
                node.child_count = 1
            elif level < pos:
                for child in node.children:
                    delve(child, level + 1)

        delve(self.tree, 0)

        self.arguments.insert(pos, GameSync(group_id))
        self.group_types.insert(pos, group_type)
        self.tree_depth = len(self.arguments)

    def remove_argument(self, argument: Hash, branch_to_keep: Hash = "*") -> None:
        pos = self.get_argument_pos(argument)
        if pos < 0:
            raise ValueError(f"Argument {argument} is not part of this tree")

        # Remove the decision level from the tree
        keep = get_key_hash(branch_to_keep)

        def delve(node: DecisionTreeNode, level: int) -> None:
            if level == pos:
                node.children = [c for c in node.children if c.key == keep]
                node.child_count = len(node.children)
            elif level < pos:
                for child in node.children:
                    delve(child, level + 1)

        delve(self.tree, 0)

        self.arguments.pop(pos)
        self.group_types.pop(pos)
        self.tree_depth = len(self.arguments)

    def does_branch_exist(self, path: list[Hash]) -> bool:
        if len(path) != len(self.arguments):
            return False

        path: list[int] = parse_state_path(path)
        parent = self.tree

        for key in path:
            for child in parent.children:
                if child.key == key:
                    parent = child
                    break
            else:
                return False

        return True

    def add_branch(self, path: list[Hash], node_id: int | HIRCNode) -> None:
        from yonder.types.hirc_node import HIRCNode

        if len(path) != len(self.arguments):
            raise ValueError("Path length must be equal to number of tree arguments")

        path: list[int] = parse_state_path(path)
        parent = self.tree
        offset = 0

        for i, key in enumerate(path):
            for child in parent.children:
                if child.key == key:
                    # Continue searching the child
                    parent = child
                    break
            else:
                # No matching child, we found our parent
                offset = i
                break
        else:
            # For every key we found a matching child, so this path already exists
            raise ValueError(f"State path already exists: {path}")

        for key in path[offset:]:
            branch = DecisionTreeNode(key, 0)
            parent.children.append(branch)
            parent.child_count += 1
            parent = branch

        # Set the node ID on the leaf child
        if isinstance(node_id, HIRCNode):
            node_id = node_id.id

        node_id = int(node_id)
        branch.node_id = node_id
        if node_id > 0:
            self.children.add(node_id)

    def remove_branch(self, path_to_branch: list[Hash]) -> None:
        parent = self.tree
        for key in path_to_branch[:-1]:
            for child in parent.children:
                if child.key == key:
                    parent = child
                    break
            else:
                raise ValueError(f"Could not resolve branch path {path_to_branch}")

        # TODO doesn't work if it's not a complete path (e.g. only up to level 3/5)
        branch = next(c for c in parent.children if c.key == path_to_branch[-1])
        parent.children.remove(branch)
        return branch

    def select_child(self, values: list[int | str]) -> DecisionTreeNode:
        if len(values) != len(self.arguments):
            raise ValueError(
                f"Args must match tree depth (expected {len(self.arguments)}, got {len(values)})"
            )

        node = self.tree

        for idx, val in enumerate(values):
            wildcard: DecisionTreeNode = None
            val = calc_hash(val)

            for child in node.children:
                if child.key == 0:
                    wildcard = child

                if child.key == val:
                    node = child
                    break
            else:
                if not wildcard:
                    arg_name = lookup_name(
                        self.arguments[idx].group_id, f"#{self.arguments[idx].group_id}"
                    )
                    val_name = lookup_name(val, f"#{val}")
                    raise ValueError(
                        f"Decision tree has no node at level {idx} ({arg_name}) to match {val} ({val_name})"
                    )

                # No matching child, use the wildcard node
                node = wildcard

        return node

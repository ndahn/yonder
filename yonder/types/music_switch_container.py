from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar
from random import randint

from yonder.hash import calc_hash, Hash
from yonder.enums import GroupType, DecisionTreeMode, PropID
from yonder.util import logger, get_key_hash, parse_state_path
from .hirc_node import HIRCNode
from .base_types import (
    MusicTransNodeParams,
    GameSync,
    DecisionTreeNode,
    PropBundle,
    Children,
    RTPC,
    StateChunk,
)
from .mixins import PropertyMixin


@dataclass(repr=False, eq=False)
class MusicSwitchContainer(PropertyMixin, HIRCNode):
    body_type: ClassVar[int] = 12
    music_trans_node_params: MusicTransNodeParams = field(
        default_factory=MusicTransNodeParams
    )
    continue_playback: int = 1
    tree_depth: int = 0
    arguments: list[GameSync] = field(default_factory=list)
    group_types: list[GroupType] = field(default_factory=list)
    tree_size: int = 0
    tree_mode: DecisionTreeMode = DecisionTreeMode.BestMatch
    tree: DecisionTreeNode = field(default_factory=lambda: DecisionTreeNode(0, 0))

    @classmethod
    def new(
        cls,
        nid: Hash,
        arguments: list[tuple[Hash, GroupType]],
        branches: list[tuple[list[Hash], int]] = None,
        props: dict[PropID, float] = None,
        parent: int | HIRCNode = 0,
    ) -> MusicSwitchContainer:
        obj = cls(nid)

        for arg, group_type in arguments:
            obj.insert_argument(arg, group_type)

        if branches:
            for state_values, node_id in branches:
                obj.add_branch(state_values, node_id)

        if props:
            for prop, val in props.items():
                obj.set_property(prop, val)

        obj.parent = parent
        return obj

    @property
    def parent(self) -> int:
        return self.music_trans_node_params.music_node_params.node_base_params.direct_parent_id

    @parent.setter
    def parent(self, new_parent: int | HIRCNode) -> None:
        if isinstance(new_parent, HIRCNode):
            new_parent = new_parent.id
        self.music_trans_node_params.music_node_params.node_base_params.direct_parent_id = new_parent

    @property
    def children(self) -> Children:
        return self.music_trans_node_params.music_node_params.children

    @property
    def properties(self) -> list[PropBundle]:
        return self.music_trans_node_params.music_node_params.node_base_params.node_initial_params.prop_initial_values

    @property
    def rtpcs(self) -> list[RTPC]:
        return self.music_trans_node_params.music_node_params.node_base_params.initial_rtpc.rtpcs

    @property
    def states(self) -> StateChunk:
        return self.music_trans_node_params.music_node_params.node_base_params.state_chunk

    def attach(self, other: int | HIRCNode) -> None:
        if isinstance(other, HIRCNode):
            if other.parent not in (0, self.id):
                logger.warning(
                    f"{other} is already parented to {other.parent} and will be detached"
                )
            other.parent = self.id
            other = other.id

        state_path = [0] * len(self.arguments)
        state_path[0] = randint(0, 10**9)
        self.add_branch(state_path, int(other))

        logger.warning(
            f"Attached node with state path {state_path}, don't forget to change it as needed!"
        )

    def detach(self, other: int | HIRCNode) -> None:
        if isinstance(other, HIRCNode):
            other = other.id

        def delve(node: DecisionTreeNode):
            if node.node_id == other:
                node.node_id = 0

            for child in node.children:
                delve(child)

        if other in self.children:
            self.children.remove(other)
            delve(self.tree)

    def get_tree_size(self) -> int:
        num_tree_nodes = 1
        todo = [self.tree]
        while todo:
            item = todo.pop()
            num_tree_nodes += len(item.children)
            todo.extend(item.children)

    def has_argument(self, argument: Hash) -> None:
        return self.get_argument_pos(argument) >= 0

    def insert_argument(
        self, pos: int, argument: Hash, group_type: GroupType,
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

    def add_branch(self, path: list[Hash], node_id: int) -> None:
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
            raise ValueError(f"Path already exists: {path}")

        for key in path[offset:]:
            branch = DecisionTreeNode(key, 0)
            parent.children.append(branch)
            parent.child_count += 1
            parent = branch

        # Set the node ID on the leaf child
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

        branch = next(c for c in parent.children if c.key == path_to_branch[-1])
        parent.children.remove(branch)
        return branch

    def validate(self) -> None:
        if len(self.group_types) != len(self.arguments):
            raise ValueError(
                f"Found mismatch between group_types and arguments in {self}"
            )

        def delve(branch: DecisionTreeNode, path: list) -> None:
            if len(path) == len(self.arguments) and branch.children:
                raise ValueError(
                    f"Branch {path} of {self} is deeper than number of arguments ({len(self.arguments)})"
                )

            if len(path) != len(self.arguments) and not branch.children:
                raise ValueError(
                    f"Branch {path} of {self} does not reach the required depth ({len(self.arguments)})"
                )

            branch.children.sort(key=lambda c: c.key)
            for child in branch.children:
                delve(child, path + [branch.key])

        delve(self.tree, [])

    def get_references(self, true_children_only: bool = True) -> list[tuple[str, int]]:
        ret = super().get_references()

        if true_children_only:
            # Some vanilla soundbanks have leftover transition rules that will result
            # in misleading warnings and mess up our gui's tree structure
            ret = [
                (p, i)
                for p, i in ret
                if "transition_rule" not in p or i in self.children
            ]

        return ret

    # TODO transition rule helper

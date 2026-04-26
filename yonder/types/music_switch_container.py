from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar
from random import randint

from yonder.hash import calc_hash, Hash
from yonder.enums import GroupType, DecisionTreeMode, PropID
from yonder.util import logger, parse_state_path
from .hirc_node import HIRCNode
from .base_types import (
    MusicTransNodeParams,
    GameSync,
    DecisionTreeNode,
    PropBundle,
    Children,
    RTPC,
)
from .mixins import PropertyMixin


@dataclass(repr=False)
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
            obj.add_argument(arg, group_type)

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

    def add_argument(self, argument: Hash, group_type: GroupType) -> None:
        if argument in self.arguments:
            raise ValueError(f"Argument {argument} already exists")

        group_id = calc_hash(argument) if isinstance(argument, str) else argument
        self.arguments.append(GameSync(group_id))
        self.group_types.append(group_type)
        self.tree_depth = len(self.arguments)
        # TODO we should extend the tree if it's more than just the root

    def add_branch(self, path: list[Hash], node_id: int) -> None:
        if len(path) != len(self.arguments):
            raise ValueError("Path length must be equal to number of tree arguments")

        path: list[int] = parse_state_path(path)
        parent = self.tree
        offset = None

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
        branch.node_id = node_id
        if node_id > 0:
            self.children.add(node_id)

    def validate(self) -> None:
        if len(self.group_types) != len(self.arguments):
            raise ValueError(f"Found mismatch between group_types and arguments in {self}")

        def delve(branch: DecisionTreeNode, path: list) -> None:
            if len(path) == len(self.arguments) and branch.children:
                raise ValueError(f"Branch {path} of {self} is deeper than number of arguments ({len(self.arguments)})")

            if len(path) != len(self.arguments) and not branch.children:
                raise ValueError(f"Branch {path} of {self} does not reach the required depth ({len(self.arguments)})")

            branch.children.sort(key=lambda c: c.key)
            for child in branch.children:
                delve(child, path + [branch.key])

        delve(self.tree, [])

    # TODO transition rule helper

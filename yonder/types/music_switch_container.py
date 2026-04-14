from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar

from yonder.hash import calc_hash
from .hirc_node import HIRCNode
from .base_types import (
    MusicTransNodeParams,
    GameSync,
    DecisionTreeNode,
    PropBundle,
    Children,
    RTPC,
)
from yonder.enums import GroupType, DecisionTreeMode, PropID
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
        nid: int | str,
        arguments: list[tuple[int | str, GroupType]],
        branches: list[tuple[list[int | str], int]] = None,
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

    @staticmethod
    def parse_state_path(state_path: list[str]) -> list[int]:
        keys = []
        for val in state_path:
            if isinstance(val, int):
                keys.append(val)
            elif val == "*":
                keys.append(0)
            elif val.startswith("#"):
                try:
                    keys.append(int(val[1:]))
                except ValueError:
                    raise ValueError(f"{val}: value is not a valid hash")
            else:
                keys.append(calc_hash(val))

        return keys

    def get_tree_size(self) -> int:
        num_tree_nodes = 1
        todo = [self.tree]
        while todo:
            item = todo.pop()
            num_tree_nodes += len(item.children)
            todo.extend(item.children)

    def add_argument(self, argument: int | str, group_type: GroupType) -> None:
        if argument in self.arguments:
            raise ValueError(f"Argument {argument} already exists")

        group_id = calc_hash(argument) if isinstance(argument, str) else argument
        self.arguments.append(GameSync(group_id))
        self.group_types.append(group_type)
        self.tree_depth = len(self.arguments)
        # TODO we should extend the tree if it's more than just the root

    def add_branch(self, path: list[int | str], node_id: int) -> None:
        if len(path) != len(self.arguments):
            raise ValueError("Path length must be equal to number of tree arguments")

        path: list[int] = MusicSwitchContainer.parse_state_path(path)
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
        branch.node_id = node_id
        if node_id > 0:
            self.children.add(node_id)

    def validate(self) -> None:
        if len(self.group_types) != len(self.arguments):
            raise ValueError("Found mismatch between group_types and arguments")

        # TODO verify all branches have the correct depth

    # TODO transition rule helper

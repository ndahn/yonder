from dataclasses import dataclass, field
from typing import ClassVar

from yonder.hash import calc_hash
from .structure import _HIRCNodeBody
from .rewwise_base_types import (
    MusicNodeParams,
    MusicTransNodeParams,
    GameSync,
    DecisionTreeNode,
    PropBundle,
    Children,
)
from .rewwise_enums import GroupType, DecisionTreeMode
from .mixins import PropertyMixin, ContainerMixin


@dataclass
class MusicSwitchContainer(PropertyMixin, ContainerMixin, _HIRCNodeBody):
    body_type: ClassVar[int] = 12
    music_node_params: MusicNodeParams = field(default_factory=MusicNodeParams)
    music_trans_node_params: MusicTransNodeParams = field(
        default_factory=MusicTransNodeParams
    )
    continue_playback: int = 0
    tree_depth: int = 0
    arguments: list[GameSync] = field(default_factory=list)
    group_types: list[GroupType] = field(default_factory=list)
    tree_size: int = 0
    tree_mode: DecisionTreeMode = DecisionTreeMode.BestMatch
    tree: DecisionTreeNode = field(default_factory=lambda: DecisionTreeNode(0, 0))

    @property
    def parent(self) -> int:
        return self.music_node_params.node_base_params.direct_parent_id

    @parent.setter
    def parent(self, new_parent: int) -> None:
        self.music_node_params.node_base_params.direct_parent_id = new_parent

    @property
    def children(self) -> Children:
        return self.music_node_params.children

    @property
    def properties(self) -> list[PropBundle]:
        return self.music_node_params.node_base_params.node_initial_params.prop_initial_values

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

    def add_argument(self, argument: GameSync, group_type: GroupType) -> None:
        if argument in self.arguments:
            raise ValueError(f"Argument {argument} already exists")

        self.arguments.append(argument)
        self.group_types.append(group_type)
        self.tree_depth = len(self.arguments)
        # TODO tree needs to be extended

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
            # TODO children mixin
            self.add_child(node_id)

    # TODO transition rule helper
    # TODO expose children
    # TODO get_references

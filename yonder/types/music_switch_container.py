from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar
from random import randint
import pyo

from yonder.hash import Hash
from yonder.enums import GroupType, DecisionTreeMode, PropID
from yonder.util import logger
from yonder.audio import PlayContext, PlaybackState
from .hirc_node import HIRCNode
from .base_types import (
    MusicTransNodeParams,
    MusicTransitionRule,
    GameSync,
    DecisionTreeNode,
    PropBundle,
    Children,
    RTPC,
    StateChunk,
)
from .mixins import PropertyMixin, RtpcMixin, StateMixin, DecisionTreeMixin


@dataclass(repr=False, eq=False)
class MusicSwitchContainer(DecisionTreeMixin, StateMixin, RtpcMixin, PropertyMixin, HIRCNode):
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
            obj.insert_argument(-1, arg, group_type)

        if branches:
            for state_values, node_id in branches:
                obj.add_branch(state_values, node_id)

        if props:
            for prop, val in props.items():
                obj.set_property(prop, val)

        obj.parent = parent
        return obj

    @property
    def wwise_link(self) -> str:
        return "https://ndahn.github.io/yonder/wwise/music/#music-switch-container"

    @property
    def transition_rules(self) -> list[MusicTransitionRule]:
        return self.music_trans_node_params.transition_rules

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
        return (
            self.music_trans_node_params.music_node_params.node_base_params.state_chunk
        )

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

    def validate(self) -> None:
        if len(self.group_types) != len(self.arguments):
            raise ValueError(
                f"{self}: found mismatch between group_types and arguments"
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

    def _build_pyo(self, my_pyo: PlaybackState) -> pyo.InputFader:
        fader = pyo.InputFader(pyo.Sig(0))
        my_pyo.cache["fader"] = fader
        return pyo.Sig(fader)

    def play(self, ctx: PlayContext) -> None:
        if not self.children:
            return

        my_pyo = self.pyo(ctx)
        if my_pyo.playing:
            return

        self.update_playback(ctx)
        my_pyo.play()

    def update_playback(self, ctx: PlayContext) -> None:
        my_pyo = self.pyo(ctx)
        ctx = my_pyo.ctx
        fader: pyo.InputFader = my_pyo.cache["fader"]

        values = [ctx.states.get(arg.group_id, 0) for arg in self.arguments]
        selected = self.select_child(values)
        node = ctx.bank.get(selected.node_id) if selected else None
        prev_node = ctx.bank.get(my_pyo.cache.get("prev_node", -1))

        if node == prev_node:
            super().update_playback(ctx)
            return

        rule = self.music_trans_node_params.get_transition_rule(prev_node, node)
        xfade = (
            max(
                rule.source_transition_rule.transition_time,
                rule.destination_transition_rule.transition_time,
                50,
            )
            / 1000
        )

        if node:
            node.play(ctx)
            fader.setInput(node.pyo(ctx).output, xfade)
        else:
            fader.setInput(pyo.Sig(0), xfade)

        # Wait for the fader to finish
        if prev_node:
            prev_node.release_pyo(ctx, xfade + 0.1)

        my_pyo.cache["prev_node"] = node.id if node else -1

        super().update_playback(ctx)

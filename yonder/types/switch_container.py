from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar
import pyo

from yonder.hash import Hash, calc_hash
from yonder.enums import PropID
from yonder.util import logger
from yonder.audio import PlayContext
from .hirc_node import HIRCNode, PyoState
from .base_types import (
    NodeBaseParams,
    Children,
    PropBundle,
    SwitchPackage,
    SwitchNodeParams,
    RTPC,
    StateChunk,
)
from .mixins import PropertyMixin, RtpcMixin, StateMixin


@dataclass(repr=False, eq=False)
class SwitchContainer(StateMixin, RtpcMixin, PropertyMixin, HIRCNode):
    body_type: ClassVar[int] = 6
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    group_type: int = 0
    group_id: int = 0
    default_switch: int = 0
    continuous_validation: int = 0
    children: Children = field(default_factory=Children)
    switch_group_count: int = 0
    switch_groups: list[SwitchPackage] = field(default_factory=list)
    switch_param_count: int = 0
    switch_params: list[SwitchNodeParams] = field(default_factory=list)

    @classmethod
    def new(
        cls,
        nid: Hash,
        switch_group: str | int,
        switch_states: dict[str | int, int | HIRCNode | list[int | HIRCNode]],
        default_state: str | int = None,
        props: dict[PropID, float] = None,
        xfade: float | tuple[float, float] = 1.0,
        parent: int | HIRCNode = 0,
    ) -> SwitchContainer:
        obj = cls(nid)
        obj.group_id = calc_hash(switch_group)
        obj.default_switch = calc_hash(default_state or 0)
        first_node = None

        for state, nodes in switch_states.items():
            state = calc_hash(state)

            if isinstance(nodes, (int, HIRCNode)):
                nodes = [nodes]

            if not first_node and nodes:
                first_node = nodes[0]

            node_ids = [n.id if isinstance(n, HIRCNode) else n for n in nodes]
            obj.switch_groups.append(SwitchPackage(state, node_ids))

        if isinstance(xfade, float):
            xfade = (xfade, xfade)

        obj.switch_params.append(
            SwitchNodeParams(
                first_node,  # Seems like the first one serves as the default?
                fade_out_time=int(xfade[0] / 1000),
                fade_in_time=int(xfade[1] / 1000),
            )
        )

        if props:
            for prop, val in props.items():
                obj.set_property(prop, val)

        obj.parent = parent
        return obj

    @property
    def parent(self) -> int:
        return self.node_base_params.direct_parent_id

    @parent.setter
    def parent(self, new_parent: int | HIRCNode) -> None:
        if isinstance(new_parent, HIRCNode):
            new_parent = new_parent.id
        self.node_base_params.direct_parent_id = new_parent

    @property
    def properties(self) -> list[PropBundle]:
        return self.node_base_params.node_initial_params.prop_initial_values

    @property
    def rtpcs(self) -> list[RTPC]:
        return self.node_base_params.initial_rtpc.rtpcs

    @property
    def states(self) -> StateChunk:
        return self.node_base_params.state_chunk

    def get_nodes_for_switch(self, switch_state: str | int) -> list[int]:
        switch_state = calc_hash(switch_state)

        for group in self.switch_groups:
            if group.switch_id == switch_state:
                return group.nodes

        return []

    def attach(self, other: int | HIRCNode, switch: str | int = None) -> None:
        if isinstance(other, HIRCNode):
            if other.parent not in (0, self.id):
                logger.warning(
                    f"{other} is already parented to {other.parent} and will be detached"
                )
            other.parent = self.id
            other = other.id

        if switch is None:
            switch = self.default_switch

        switch = calc_hash(switch)
        for group in self.switch_groups:
            if group.switch_id == switch:
                if other not in group.nodes:
                    group.nodes.append(other)

                break
        else:
            self.switch_groups.append(SwitchPackage(switch, 1, [other]))

        self.children.add(other)

    def detach(self, other: int | HIRCNode) -> None:
        if isinstance(other, HIRCNode):
            other = other.id

        for group in self.switch_groups:
            if other in group.nodes:
                group.nodes.remove(other)

        if other in self.children:
            self.children.remove(other)

    def _build_pyo(self, my_pyo: PyoState) -> pyo.PyoObject:
        return pyo.InputFader(pyo.Sig(0))

    def play(self, ctx: PlayContext) -> None:
        if not self.switch_groups:
            return

        switch_state = ctx.states.get(self.group_id, self.default_switch)
        node_ids = self.get_nodes_for_switch(switch_state)

        # Play the nodes first, then update this container
        for nid in node_ids:
            n = ctx.bank.get(nid)
            if n:
                n.play(ctx)

        self.update_playback(ctx)

    def update_playback(self, ctx: PlayContext) -> None:
        my_pyo = self.pyo(ctx)
        ctx = my_pyo.ctx
        fader: pyo.InputFader = my_pyo.pyo_playback

        switch_state = ctx.states.get(self.group_id, self.default_switch)

        # Make sure the nodes can update their state even if we have nothing to do
        node_ids = self.get_nodes_for_switch(switch_state)
        nodes: list[HIRCNode] = []
        for nid in node_ids:
            n = ctx.bank.get(nid)
            if n:
                n.update_playback(ctx)
                nodes.append(n)

        active_state = my_pyo.cache.get("active_switch")
        if switch_state == active_state:
            # Switch already active, nothing to do
            return

        # Setup the new input signal source
        if not nodes:
            input_sig = pyo.Sig(0)
        elif len(nodes) == 1:
            input_sig = nodes[0].pyo(ctx)[1]
        else:
            input_sig = pyo.Mixer(outs=1, chnls=1)
            for n in nodes:
                input_sig.addInput(n.id, n.pyo(ctx)[1])
                input_sig.setAmp(n.id, 1)
        
        # Per-node fading seems excessive for yonder, and fromsoft rarely uses it anyways
        xfade = 50
        for nid in node_ids:
            for params in self.switch_params:
                if nid == params.node_id:
                    xfade = max((params.fade_out_time, params.fade_in_time, xfade))

        fader.setInput(input_sig, xfade / 1000)

        # Cleanup old inputs
        # TODO might have to wait for the fade to finish
        if active_state is not None:
            old_ids = self.get_nodes_for_switch(active_state)
            for oid in old_ids:
                if oid not in node_ids:
                    n = ctx.bank.get(oid)
                    if n:
                        n.reset_pyo(ctx)

        my_pyo.cache["active_state"] = switch_state

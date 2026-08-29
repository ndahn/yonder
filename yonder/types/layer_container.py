from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar
import pyo

from yonder.hash import Hash
from yonder.enums import PropID, RtpcType
from yonder.util import logger
from yonder.audio import PlayContext
from yonder.audio.audiomath import eval_curve
from .hirc_node import HIRCNode, PyoState
from .base_types import (
    NodeBaseParams,
    Children,
    Layer,
    AssociatedChildData,
    PropBundle,
    RTPC,
    StateChunk,
    RTPCGraphPoint,
)
from .mixins import PropertyMixin, RtpcMixin, StateMixin


@dataclass(repr=False, eq=False)
class LayerContainer(StateMixin, RtpcMixin, PropertyMixin, HIRCNode):
    """Manages transitions between crossfade groups (layers), where each node in a group will get their own fade curve driven by a single RTPC."""

    body_type: ClassVar[int] = 9
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    children: Children = field(default_factory=Children)
    layer_count: int = 0
    layers: list[Layer] = field(default_factory=list)
    is_continuous_validation: int = 0

    @classmethod
    def new(
        cls,
        nid: Hash,
        layer_nodes: list[list[int]] = None,
        props: dict[PropID, float] = None,
        parent: int | HIRCNode = 0,
    ) -> LayerContainer:
        obj = cls(nid)

        if layer_nodes:
            for layer in layer_nodes:
                obj.add_layer(layer)

        if props:
            for prop, val in props.items():
                obj.set_property(prop, val)

        obj.parent = parent
        return obj

    @property
    def wwise_link(self) -> str:
        return "https://www.audiokinetic.com/en/public-library/2025.1.7_9143/?source=Help&id=defining_contents_and_behavior_of_blend_container"

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

    def add_layer(
        self,
        layer_id: int,
        nodes: list[int | HIRCNode],
        rtpc_id: int = 0,
        rtpc_type: RtpcType = RtpcType.GameParameter,
        curves: dict[int, list[RTPCGraphPoint]] = None,
    ) -> Layer:
        """Add a blend track covering all `nodes`.

        A layer is a crossfade group, and each node in the group will get their own fade curve driven by a single RTPC. Children that merely play together don't need a layer.
        """
        if any(layer.layer_id == layer_id for layer in self.layers):
            raise ValueError(f"layer_id {layer_id} is already used")

        curves = curves or {}
        assoc = []

        for node in nodes:
            nid = node.id if isinstance(node, HIRCNode) else int(node)
            points = list(curves.get(nid, []))
            assoc.append(AssociatedChildData(nid, len(points), points))
            self.children.add(nid)

        layer = Layer(
            layer_id=layer_id,
            rtpc_id=rtpc_id,
            rtpc_type=rtpc_type,
            associated_childen_count=len(assoc),
            associated_children=assoc,
        )

        self.layers.append(layer)
        return layer

    def get_layer(self, child: HIRCNode | int) -> bool:
        if isinstance(child, HIRCNode):
            child = child.id

        if child not in self.children:
            raise ValueError(f"{child} is not associated with this container")

        for layer in self.layers:
            for associated in layer.associated_children:
                if associated.associated_child_id == child:
                    return layer

        return None

    def attach(self, other: int | HIRCNode) -> None:
        if isinstance(other, HIRCNode):
            if other.parent not in (0, self.id):
                logger.warning(
                    f"{other} is already parented to {other.parent} and will be detached"
                )
            other.parent = self.id
            other = other.id

        self.children.add(int(other))

    def detach(self, other: int | HIRCNode) -> None:
        if isinstance(other, HIRCNode):
            other = other.id

        if other in self.children:
            self.children.remove(other)
            for layer in self.layers:
                layer.associated_children = [
                    a
                    for a in layer.associated_children
                    if a.associated_child_id != other
                ]

    def validate(self) -> None:
        for layer in self.layers:
            if layer.layer_id == 0:
                raise ValueError(
                    f"{self}: corrupted layers found, you probably want to remove those"
                )

    def _build_pyo(self, my_pyo: PyoState) -> pyo.PyoObject:
        mixer = pyo.Mixer(outs=1, chnls=1)
        my_pyo["controls"] = {}
        return mixer

    # TODO each layer has an InitialRTPC object that should be merged with the context

    def play(self, ctx: PlayContext) -> None:
        my_pyo = self.pyo(ctx)
        if my_pyo.playing:
            return

        my_pyo.playing = True
        self.update_playback(ctx)

    def update_playback(self, ctx: PlayContext) -> None:
        my_pyo = self.pyo(ctx)
        ctx = my_pyo.ctx
        mixer: pyo.Mixer = my_pyo.playback

        for layer in self.layers:
            x = ctx.rtpcs.get(layer.rtpc_id)

            for child_info in layer.associated_children:
                child = ctx.bank.get(child_info.associated_child_id)
                if child:
                    # TODO not sure how to use the layer.initial_rtpc data here
                    child.play(ctx)
                    y = eval_curve(child_info.graph_points, x)
                    mixer.addInput(layer.layer_id, child.pyo(ctx).playback)
                    mixer.setAmp(layer.layer_id, y)

        super().update_playback(ctx)

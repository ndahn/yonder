from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar

from yonder.hash import Hash
from yonder.enums import PropID
from yonder.util import logger
from .hirc_node import HIRCNode
from .base_types import (
    NodeBaseParams,
    Children,
    Layer,
    AssociatedChildData,
    PropBundle,
    RTPC,
    StateChunk,
)
from .mixins import PropertyMixin


@dataclass(repr=False, eq=False)
class LayerContainer(PropertyMixin, HIRCNode):
    wwise_link: ClassVar[str] = "https://www.audiokinetic.com/en/public-library/2025.1.7_9143/?source=Help&id=defining_contents_and_behavior_of_blend_container"
    
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

    def add_layer(self, nodes: list[int]) -> Layer:
        self.layers.append(
            Layer(associated_children=[AssociatedChildData(int(nid)) for nid in nodes])
        )
        for nid in nodes:
            self.children.add(nid)

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

    def attach(self, other: int | HIRCNode, custom: bool = True) -> None:
        if isinstance(other, HIRCNode):
            if other.parent not in (0, self.id):
                logger.warning(
                    f"{other} is already parented to {other.parent} and will be detached"
                )
            other.parent = self.id
            other = other.id

        if custom:
            self.add_layer([int(other)])
        else:
            self.children.add(int(other))

    def detach(self, other: int | HIRCNode) -> None:
        if isinstance(other, HIRCNode):
            other = other.id

        if other in self.children:
            self.children.remove(other)
            for layer in self.layers:
                if other in layer.associated_children:
                    layer.associated_children.remove(other)

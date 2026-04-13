from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar

from .hirc_node import HIRCNode
from .base_types import (
    NodeBaseParams,
    Children,
    Layer,
    AssociatedChildData,
    PropBundle,
    RTPC,
)
from yonder.enums import PropID
from .mixins import PropertyMixin


@dataclass
class LayerContainer(PropertyMixin, HIRCNode):
    body_type: ClassVar[int] = 9
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    children: Children = field(default_factory=Children)
    layer_count: int = 0
    layers: list[Layer] = field(default_factory=list)
    is_continuous_validation: int = 0

    @classmethod
    def new(
        cls,
        nid: int | str,
        layer_nodes: list[list[int]] = None,
        props: dict[PropID, float] = None,
        parent: int = 0,
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
    def parent(self, new_parent: int) -> None:
        self.node_base_params.direct_parent_id = new_parent

    @property
    def properties(self) -> list[PropBundle]:
        return self.node_base_params.node_initial_params.prop_initial_values

    @property
    def rtpcs(self) -> list[RTPC]:
        return self.node_base_params.initial_rtpc.rtpcs

    def add_layer(self, nodes: list[int]) -> Layer:
        self.layers.append(
            Layer(associated_children=[AssociatedChildData(nid) for nid in nodes])
        )

    # TODO figure out how to fill children from layer data

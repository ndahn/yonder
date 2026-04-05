from dataclasses import dataclass, field
from typing import ClassVar

from .structure import _HIRCNodeBody, HIRCNode
from .rewwise_base_types import (
    NodeBaseParams,
    Children,
    RTPCGraphPoint,
    InitialRTPC,
    PropBundle,
)
from .rewwise_enums import RtpcType, PropID
from .mixins import PropertyMixin, ContainerMixin


@dataclass
class AssociatedChildData:
    associated_child_id: int
    graph_point_count: int = 0
    graph_points: list[RTPCGraphPoint] = field(default_factory=list)

    def get_references(self) -> list[tuple[str, int]]:
        return [("associated_child_id", self.associated_child_id)]


@dataclass
class Layer:
    layer_id: int
    initial_rtpc: InitialRTPC = field(default_factory=InitialRTPC)
    rtpc_id: int = 0
    rtpc_type: RtpcType = RtpcType.GameParameter
    associated_childen_count: int = 0
    associated_children: list[AssociatedChildData] = field(default_factory=list)


@dataclass
class LayerContainer(PropertyMixin, ContainerMixin, _HIRCNodeBody):
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
    ) -> "HIRCNode[LayerContainer]":
        obj = HIRCNode(nid, cls())

        if layer_nodes:
            for layer in layer_nodes:
                obj.body.add_layer(layer)

        if props:
            for prop, val in props.items():
                obj.body.set_property(prop, val)

        obj.body.parent = parent
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

    def add_layer(self, nodes: list[int]) -> Layer:
        self.layers.append(
            Layer(associated_children=[AssociatedChildData(nid) for nid in nodes])
        )

    # TODO figure out how to fill children from layer data

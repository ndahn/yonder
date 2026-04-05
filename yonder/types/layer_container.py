from dataclasses import dataclass, field
from typing import ClassVar
from field_properties import field_property

from .structure import HIRCNode
from .rewwise_base_types import (
    NodeBaseParams,
    Children,
    RTPCGraphPoint,
    InitialRTPC,
    PropBundle,
)
from yonder.enums import RtpcType, PropID
from .mixins import PropertyMixin, ContainerMixin


@dataclass
class AssociatedChildData:
    associated_child_id: int
    graph_point_count: int = field_property(init=False, raw=True)
    graph_points: list[RTPCGraphPoint] = field(default_factory=list)

    @field_property(graph_point_count)
    def get_graph_point_count(self) -> int:
        return len(self.graph_points)

    def get_references(self) -> list[tuple[str, int]]:
        return [("associated_child_id", self.associated_child_id)]


@dataclass
class Layer:
    layer_id: int
    initial_rtpc: InitialRTPC = field(default_factory=InitialRTPC)
    rtpc_id: int = 0
    rtpc_type: RtpcType = RtpcType.GameParameter
    associated_children_count: int = field_property(init=False, raw=True)
    associated_children: list[AssociatedChildData] = field(default_factory=list)

    @field_property(associated_children_count)
    def get_associated_children_count(self) -> int:
        return len(self.associated_children)


@dataclass
class LayerContainer(PropertyMixin, ContainerMixin, HIRCNode):
    body_type: ClassVar[int] = 9
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    children: Children = field(default_factory=Children)
    layer_count: int = field_property(init=False, raw=True)
    layers: list[Layer] = field(default_factory=list)
    is_continuous_validation: int = 0

    @classmethod
    def new(
        cls,
        nid: int | str,
        layer_nodes: list[list[int]] = None,
        props: dict[PropID, float] = None,
        parent: int = 0,
    ) -> "LayerContainer":
        super().__init__(nid)
        obj = cls()

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

    @field_property(layer_count)
    def get_layer_count(self) -> int:
        return len(self.layers)

    def add_layer(self, nodes: list[int]) -> Layer:
        self.layers.append(
            Layer(associated_children=[AssociatedChildData(nid) for nid in nodes])
        )

    # TODO figure out how to fill children from layer data

from dataclasses import dataclass, field
from typing import ClassVar

from .structure import _HIRCNodeBody, HIRCNode
from .rewwise_base_types import NodeBaseParams, Children, PropBundle
from .rewwise_enums import PropID
from .mixins import PropertyMixin, ContainerMixin


@dataclass
class ActorMixer(PropertyMixin, ContainerMixin, _HIRCNodeBody):
    body_type: ClassVar[int] = 7
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    children: Children = field(default_factory=Children)

    @classmethod
    def new(
        cls,
        nid: int | str,
        override_bus_id: int = 0,
        parent: int = 0,
        props: dict[PropID, float] = None,
    ) -> "HIRCNode[ActorMixer]":
        amx = HIRCNode(
            nid,
            cls(
                NodeBaseParams(
                    override_bus_id=override_bus_id,
                    direct_parent_id=parent,
                )
            ),
        )

        if props:
            for prop, val in props.items():
                amx.body.set_property(prop, val)

        return amx

    @property
    def parent(self) -> int:
        return self.node_base_params.direct_parent_id

    @parent.setter
    def parent(self, new_parent: int) -> None:
        self.node_base_params.direct_parent_id = new_parent

    @property
    def properties(self) -> list[PropBundle]:
        return self.node_base_params.node_initial_params.prop_initial_values

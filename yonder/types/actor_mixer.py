from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar

from .hirc_node import HIRCNode
from .base_types import NodeBaseParams, Children, PropBundle, RTPC
from yonder.enums import PropID
from .mixins import PropertyMixin


@dataclass
class ActorMixer(PropertyMixin, HIRCNode):
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
    ) -> ActorMixer:
        obj = cls(
            nid,
            NodeBaseParams(
                override_bus_id=override_bus_id,
                direct_parent_id=parent,
            ),
        )

        if props:
            for prop, val in props.items():
                obj.set_property(prop, val)

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

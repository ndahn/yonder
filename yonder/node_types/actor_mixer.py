from dataclasses import dataclass, field
from typing import ClassVar

from .structure import _HIRCNodeBody
from .rewwise_base_types import NodeBaseParams, Children


@dataclass
class ActorMixer(_HIRCNodeBody):
    body_type: ClassVar[int] = 7
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    children: Children = field(default_factory=Children)

    @property
    def parent(self) -> int:
        return self.node_base_params.direct_parent_id

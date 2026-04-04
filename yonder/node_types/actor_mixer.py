from dataclasses import dataclass, field
from typing import ClassVar

from .soundbank import _HIRCNodeBody
from .rewwise_base_types import NodeBaseParams, Children


@dataclass
class ActorMixer(_HIRCNodeBody):
    body_type: ClassVar[int] = 7
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    children: Children = field(default_factory=Children)

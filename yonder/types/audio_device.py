from dataclasses import dataclass, field
from typing import ClassVar

from .structure import _HIRCNodeBody, HIRCNode
from .rewwise_base_types import FxBaseInitialValues


@dataclass
class AudioDevice(_HIRCNodeBody):
    body_type: ClassVar[int] = 21
    fx_base_initial_values: FxBaseInitialValues = field(
        default_factory=lambda: FxBaseInitialValues(fx_id=0)
    )

    @classmethod
    def new(cls, nid: int | str) -> "HIRCNode[AudioDevice]":
        return HIRCNode(nid, cls())

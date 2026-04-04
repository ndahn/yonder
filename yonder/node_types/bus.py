from dataclasses import dataclass, field
from typing import ClassVar

from .structure import _HIRCNodeBody
from .rewwise_base_types import BusInitialValues


@dataclass
class Bus(_HIRCNodeBody):
    body_type: ClassVar[int] = 8
    initial_values: BusInitialValues = field(default_factory=BusInitialValues)

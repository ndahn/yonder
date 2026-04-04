from dataclasses import dataclass, field
from typing import ClassVar

from .soundbank import _HIRCNodeBody
from .rewwise_base_types import BusInitialValues


@dataclass
class AuxBus(_HIRCNodeBody):
    body_type: ClassVar[int] = 18
    initial_values: BusInitialValues = field(default_factory=BusInitialValues)

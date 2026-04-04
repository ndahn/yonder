from dataclasses import dataclass, field
from typing import ClassVar

from .structure import _HIRCNodeBody
from .rewwise_base_types import BusInitialValues, PropBundle
from .mixins import PropertyMixin


@dataclass
class Bus(PropertyMixin, _HIRCNodeBody):
    body_type: ClassVar[int] = 8
    initial_values: BusInitialValues = field(default_factory=BusInitialValues)

    @property
    def properties(self) -> list[PropBundle]:
        return self.initial_values.bus_initial_params.prop_bundle

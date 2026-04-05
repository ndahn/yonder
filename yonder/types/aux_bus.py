from dataclasses import dataclass, field
from typing import ClassVar

from .structure import HIRCNode
from .rewwise_base_types import BusInitialValues, DuckInfo, PropBundle
from yonder.enums import PropID
from .mixins import PropertyMixin


@dataclass
class AuxBus(PropertyMixin, HIRCNode):
    body_type: ClassVar[int] = 18
    initial_values: BusInitialValues = field(default_factory=BusInitialValues)

    @classmethod
    def new(
        cls,
        nid: int | str,
        override_bus_id: int = 0,
        ducks: list[DuckInfo] = None,
        props: dict[PropID, float] = None,
    ) -> "AuxBus":
        super().__init__(nid)
        obj = cls(
            BusInitialValues(
                override_bus_id=override_bus_id,
                ducks=ducks or [],
            )
        )

        if props:
            for prop, val in props.items():
                obj.set_property(prop, val)

        return obj

    @property
    def properties(self) -> list[PropBundle]:
        return self.initial_values.bus_initial_params.prop_bundle

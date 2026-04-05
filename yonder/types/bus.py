from dataclasses import dataclass, field
from typing import ClassVar

from .structure import _HIRCNodeBody, HIRCNode
from .rewwise_base_types import BusInitialValues, DuckInfo, PropBundle
from .rewwise_enums import PropID
from .mixins import PropertyMixin


@dataclass
class Bus(PropertyMixin, _HIRCNodeBody):
    body_type: ClassVar[int] = 8
    initial_values: BusInitialValues = field(default_factory=BusInitialValues)

    @classmethod
    def new(
        cls,
        nid: int | str,
        override_bus_id: int = 0,
        ducks: list[DuckInfo] = None,
        props: dict[PropID, float] = None,
    ) -> "HIRCNode[Bus]":
        bus = HIRCNode(
            nid,
            cls(
                BusInitialValues(
                    override_bus_id=override_bus_id,
                    ducks=ducks or [],
                )
            ),
        )

        if props:
            for prop, val in props.items():
                bus.body.set_property(prop, val)

        return bus

    @property
    def properties(self) -> list[PropBundle]:
        return self.initial_values.bus_initial_params.prop_bundle

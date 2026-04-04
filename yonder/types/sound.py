from dataclasses import dataclass, field
from typing import ClassVar

from .structure import _HIRCNodeBody
from .rewwise_base_types import NodeBaseParams, BankSourceData, PropBundle
from .mixins.properties import PropertyMixin


@dataclass
class Sound(PropertyMixin, _HIRCNodeBody):
    body_type: ClassVar[int] = 2
    bank_source_data: BankSourceData = field(default_factory=BankSourceData)
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)

    @property
    def parent(self) -> int:
        return self.node_base_params.direct_parent_id

    @parent.setter
    def parent(self, new_parent: int) -> None:
        self.node_base_params.direct_parent_id = new_parent

    @property
    def properties(self) -> list[PropBundle]:
        return self.node_base_params.node_initial_params.prop_initial_values

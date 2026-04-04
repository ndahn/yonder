from dataclasses import dataclass, field
from typing import ClassVar

from .soundbank import _HIRCNodeBody
from .rewwise_base_types import FxBaseInitialValues


@dataclass
class FxShareSet(_HIRCNodeBody):
    body_type: ClassVar[int] = 16
    fx_base_initial_values: FxBaseInitialValues = field(
        default_factory=lambda: FxBaseInitialValues(fx_id=0)
    )


@dataclass
class FxCustom(_HIRCNodeBody):
    body_type: ClassVar[int] = 17
    fx_base_initial_values: FxBaseInitialValues = field(
        default_factory=lambda: FxBaseInitialValues(fx_id=0)
    )

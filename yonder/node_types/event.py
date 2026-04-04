from dataclasses import dataclass, field
from typing import ClassVar, TYPE_CHECKING

from .structure import _HIRCNodeBody
from .action import SupportedActionType, ActionTypeId

if TYPE_CHECKING:
    from .soundbank import Soundbank


@dataclass
class Event(_HIRCNodeBody):
    body_type: ClassVar[int] = 4
    action_count: int = 0
    actions: list[int] = field(default_factory=list)

    def has_action_type(self, bnk: "Soundbank", val: SupportedActionType | ActionTypeId | str | int) -> bool:
        if isinstance(val, SupportedActionType):
            type_id = ActionTypeId[val.name].value
        elif isinstance(val, ActionTypeId):
            type_id = val.value
        elif isinstance(val, str):
            type_id = ActionTypeId[val].value
        else:
            type_id = val

        for aid in self.actions:
            action = bnk.get(aid)
            if action and action.type_id == type_id:
                return True

        return False

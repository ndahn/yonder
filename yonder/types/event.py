from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar, TYPE_CHECKING

from .hirc_node import HIRCNode
from .action import ActionType

if TYPE_CHECKING:
    from .soundbank import Soundbank


@dataclass
class Event(HIRCNode):
    body_type: ClassVar[int] = 4
    action_count: int = 0
    actions: list[int] = field(default_factory=list)

    @classmethod
    def new(cls, nid: int | str, actions: list[int] = None) -> Event:
        return Event(nid, actions=actions)

    def has_action_type(self, bnk: Soundbank, val: ActionType | str | int) -> bool:
        if isinstance(val, ActionType):
            type_id = val.type_id
        elif isinstance(val, str):
            type_id = ActionType[val].type_id
        else:
            type_id = val

        for aid in self.actions:
            action = bnk.get(aid)
            if action and action.type_id == type_id:
                return True

        return False

    def get_references(self) -> list[tuple[str, int]]:
        return [(f"actions:{i}", aid) for i, aid in enumerate(self.actions)]

    def __str__(self) -> str:
        return super().__str__()

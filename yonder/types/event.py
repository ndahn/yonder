from __future__ import annotations
from typing import Any
import re
from dataclasses import dataclass, field
from typing import ClassVar, TYPE_CHECKING

from yonder.hash import Hash
from yonder.enums import SoundType
from .hirc_node import HIRCNode
from .action import Action, ActionType

if TYPE_CHECKING:
    from .soundbank import Soundbank


@dataclass(repr=False, eq=False)
class Event(HIRCNode):
    body_type: ClassVar[int] = 4
    action_count: int = 0
    actions: list[int] = field(default_factory=list)

    @classmethod
    def new(cls, nid: Hash, actions: list[int] = None) -> Event:
        return Event(nid, actions=actions or [])

    def get_wwise_name(self, default: Any = None) -> str:
        name = self.name
        if not name:
            return default

        parts = name.split("_", maxsplit=1)
        if len(parts) > 1:
            return parts[1]

        return default

    def get_soundtype(self) -> SoundType:
        wwise = self.get_wwise_name()
        if wwise and re.match(r"\w\d+", wwise):
            return SoundType(wwise[0])

        return None

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

    def attach(self, other: int | HIRCNode) -> None:
        if isinstance(other, HIRCNode):
            if not isinstance(other, Action):
                raise ValueError("Cannot attach non-Actions to events")

            other = other.id

        other = int(other)
        if other not in self.actions:
            # Actions are *not* sorted
            self.actions.append(other)

    def detach(self, other: int | HIRCNode) -> None:
        if isinstance(other, HIRCNode):
            other = other.id

        if other in self.actions:
            self.actions.remove(other)

    def __str__(self) -> str:
        return super().__str__()

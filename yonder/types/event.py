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
    wwise_link: ClassVar[str] = "https://www.audiokinetic.com/en/public-library/2025.1.7_9143/?source=WwiseFundamentalApproach&id=understanding_events"
    
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

    def has_action_type(self, bnk: Soundbank, *types: ActionType | str | int) -> bool:
        for val in types:
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

    def get_related_events(self, bnk: Soundbank) -> list[Event]:
        ret = set()
        actions = set()

        for aid in self.actions:
            act: Action = bnk.get(aid)

            if not act or act.external_id <= 0:
                continue

            if act.action_type_enum == ActionType.PlayEvent:
                # Play events reference another event
                ret.add(act.external_id)
            # TODO not sure what E, EO, AEO, etc. stand for
            elif act.action_type_enum in (ActionType.Play, ActionType.StopEO, ActionType.PauseEO):
                # Collect other actions referencing the same target
                edges = bnk.tree.in_edges(act.external_id)
                for event_id, _ in edges:
                    parent = bnk.get(event_id)
                    if parent and isinstance(parent, Action):
                        actions.add(event_id)

        # Get the events for the actions we found      
        for aid in actions:
            edges = bnk.tree.in_edges(aid)
            # Only events can hold actions
            for event_id, _ in edges:
                ret.add(event_id)

        ret.discard(self.id)
        return [bnk[eid] for eid in ret]

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

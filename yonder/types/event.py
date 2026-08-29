from __future__ import annotations
from typing import Any, ClassVar, TYPE_CHECKING
import re
from dataclasses import dataclass, field
import pyo

from yonder.hash import Hash
from yonder.enums import SoundType, ActionType
from yonder.audio import PlayContext
from .hirc_node import HIRCNode, PyoState
from .action import Action

if TYPE_CHECKING:
    from .soundbank import Soundbank


@dataclass(repr=False, eq=False)
class Event(HIRCNode):
    """Events are signals wwise uses to start, stop or change audio playback.
    """

    body_type: ClassVar[int] = 4
    action_count: int = 0
    actions: list[int] = field(default_factory=list)

    @classmethod
    def new(cls, nid: Hash, actions: list[int] = None) -> Event:
        return Event(nid, actions=actions or [])

    def get_action_nodes(self, bnk: Soundbank) -> list[Action]:
        ret = []

        for aid in self.actions:
            action = bnk.get(aid)
            if action:
                ret.append(action)

        return ret

    @property
    def wwise_link(self):
        return "https://www.audiokinetic.com/en/public-library/2025.1.7_9143/?source=WwiseFundamentalApproach&id=understanding_events"

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
                type_id = val.value
            elif isinstance(val, str):
                type_id = ActionType[val].value
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
            elif act.action_type_enum in (
                ActionType.Play,
                ActionType.StopEO,
                ActionType.PauseEO,
            ):
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

    def _build_pyo(self, my_pyo: PyoState) -> pyo.PyoObject:
        ctx = my_pyo.ctx
        return sum(n.pyo(ctx).playback for n in self.get_action_nodes(ctx.bank))

    def play(self, ctx: PlayContext) -> None:
        my_pyo = self.pyo(ctx)
        if my_pyo.playing:
            return

        my_pyo.playing = True
        ctx = my_pyo.ctx

        for action in self.get_action_nodes(ctx.bank):
            action.play(ctx)

        my_pyo.play()

    def __str__(self) -> str:
        return super().__str__()

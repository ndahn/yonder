from typing import Any

from yonder.node import Node
from yonder.util import logger
from yonder.enums import SoundType


class Event(Node):
    """Event that triggers actions in response to game calls.

    Events are the interface between game code and Wwise audio. When the game posts an event, it executes the associated actions (play, stop, etc.).
    """

    @classmethod
    def new(cls, name: str) -> "Event":
        """Create a new Event node.

        Parameters
        ----------
        name : str
            The name by which this event will be triggered, e.g. "Play_c123456789".

        Returns
        -------
        Event
            New Event instance.
        """
        temp = cls.load_template(cls.__name__)
        event = cls(temp)
        event.name = name
        logger.info(f"Created new node {event}")
        return event

    @classmethod
    def make_event_name(
        sound_type: SoundType, event_id: int, event_type: str = None
    ) -> str:
        if not 0 < event_id < 1_000_000_000:
            raise ValueError(f"event ID {event_id} outside expected range")

        if not event_type:
            return f"{sound_type}{event_id:010d}"

        return f"{event_type}_{sound_type}{event_id:010d}"

    def get_wwise_id(self, default: Any = None) -> str:
        name = self.lookup_name()
        if name and "_" in name:
            return name.split("_")[1]

        return default

    @property
    def actions(self) -> list[int]:
        """Actions executed when this event is triggered.

        Returns
        -------
        list[int]
            List of action node IDs.
        """
        return self["actions"]

    def add_action(self, action_id: int | Node) -> None:
        """Associates an action with this event for execution on trigger.

        Parameters
        ----------
        action_id : int | Node
            Action node ID or Action instance.
        """
        if isinstance(action_id, Node):
            action_id = action_id.id

        actions = self["actions"]
        if action_id not in actions:
            actions.append(action_id)
            self["action_count"] = len(actions)

    def remove_action(self, action_id: int | Node) -> bool:
        """Disassociates an action from this event.

        Parameters
        ----------
        action_id : int | Node
            Action node ID or Action instance to remove.

        Returns
        -------
        bool
            True if action was removed, False if not found.
        """
        if isinstance(action_id, Node):
            action_id = action_id.id

        actions = self["actions"]
        if action_id in actions:
            actions.remove(action_id)
            self["action_count"] = len(actions)
            return True
        return False

    def clear_actions(self) -> None:
        """Disassociates all actions from this event."""
        self["actions"] = []
        self["action_count"] = 0

    def get_references(self) -> list[tuple[str, int]]:
        refs = super().get_references()
        
        for i, act in enumerate(self.actions):
            if act > 0:
                refs.append((f"actions:{i}", act))
                
        return refs

    def __str__(self):
        return f"{self.lookup_name('<?>')} ({self.id})"

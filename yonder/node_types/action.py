from typing import Any

from yonder import Soundbank, Node
from yonder.enums import ActionType
from yonder.util import logger, PathDict


class Action(Node):
    """Unified Action node for all action types.

    Actions are triggered by Events and perform operations like playing, stopping, pausing sounds, muting buses, or modifying properties.
    """

    # Factory methods for different action types

    @classmethod
    def _new_action(
        cls,
        nid: int,
        action_type: ActionType,
        params_key: str,
        is_bus: bool = False,
    ) -> "Action":
        temp = cls.load_template(cls.__name__)
        action = cls(temp)

        action.id = nid
        action.action_type = action_type
        action["params"] = {params_key: {}}
        action.is_bus = is_bus

        return action

    @classmethod
    def new_play_action(
        cls,
        nid: int,
        target_id: int,
        bank_id: int = 0,
        fade_curve: int = 4,
    ) -> "Action":
        """Creates an action that starts audio playback.

        Parameters
        ----------
        nid : int
            Action ID (hash).
        target_id : int
            Target sound/container ID to play.
        bank_id : int, default=0
            ID of the target soundbank.
        fade_curve : int, default=4
            Fade curve type.

        Returns
        -------
        Action
            New Play action instance.
        """
        return PlayAction.new(
            nid, bank_id=bank_id, target_id=target_id, fade_curve=fade_curve
        )

    @classmethod
    def new_stop_action(
        cls,
        nid: int,
        target_id: int,
        flags1: int = 4,
        flags2: int = 6,
        exceptions: list[int] = None,
    ) -> "Action":
        """Creates an action that stops audio playback.

        Parameters
        ----------
        nid : int
            Action ID (hash).
        target_id : int
            Target sound/container ID to stop.
        flags1 : int, default=4
            Stop flags 1.
        flags2 : int, default=6
            Stop flags 2.
        exceptions: list[int], default=None
            Objects that will not be stopped by this action.

        Returns
        -------
        Action
            New Stop action instance.
        """
        return StopAction.new(
            nid, target_id, flags1=flags1, flags2=flags2, exception=exceptions
        )

    @classmethod
    def new_event_action(cls, nid: int, target_event: int) -> "Action":
        """Creates an action that triggers another event.

        Parameters
        ----------
        nid : int
            Action ID (hash).
        target_event : int
            ID of the event to trigger.

        Returns
        -------
        Action
            New PlayEvent action instance.
        """
        return EventAction.new(nid, target_event)

    @classmethod
    def new_set_state_action(
        cls,
        nid: int,
        switch_group_id: int,
        switch_state_id: int,
    ) -> "Action":
        return SetStateAction.new(nid, switch_group_id, switch_state_id)

    @classmethod
    def new_mute_bus_action(
        cls,
        nid: int,
        target_bus_id: int,
        fade_curve: int = 4,
        bank_id: int = 0,
    ) -> "Action":
        """Creates an action that mutes a bus, silencing all audio routed through it.

        Parameters
        ----------
        nid : int
            Action ID (hash).
        target_bus_id : int
            Target bus ID to mute.
        fade_curve : int, default=4
            Fade curve type.
        bank_id : int, default=0
            ID of the target soundbank.

        Returns
        -------
        Action
            New Mute Bus action instance.
        """
        temp = cls.load_template(cls.__name__)
        action = cls(temp)

        action.id = nid
        action.action_type = ActionType.MUTE_BUS
        action.set("params/MuteM", {})
        action.target_id = target_bus_id
        action.is_bus = True
        action.fade_curve = fade_curve
        action.bank_id = bank_id

        logger.info(f"Created new node {action}")
        return action

    # TODO SetVolumeM action 2562
    # TODO ResetVolumeM action 2818
    # TODO UnmuteM (bus) action 1794
    # TODO UnmuteALL (bus) action 1796
    # TODO ResetBusVolumeALL action 3332

    @classmethod
    def new_reset_bus_volume_action(
        cls,
        nid: int,
        target_bus_id: int,
        transition_time: int = 2000,
        fade_curve: int = 4,
        bank_id: int = 0,
    ) -> "Action":
        """Creates an action that restores a bus to its default volume.

        Parameters
        ----------
        nid : int
            Action ID (hash).
        target_bus_id : int
            Target bus ID.
        transition_time : int, default=2000
            Transition time in milliseconds.
        fade_curve : int, default=4
            Fade curve type.
        bank_id : int, default=0
            ID of the target soundbank.

        Returns
        -------
        Action
            New Reset Bus Volume action instance.
        """
        temp = cls.load_template(cls.__name__)
        action = cls(temp)

        action.id = nid
        action.action_type = ActionType.RESET_BUS_VOLUME
        action.set("params/ResetBusVolumeM", {})

        action.target_id = target_bus_id
        action.is_bus = True
        if transition_time != 0:
            action.transition_time = transition_time
        action.fade_curve = fade_curve
        action.bank_id = bank_id

        logger.info(f"Created new node {action}")
        return action

    @classmethod
    def new_reset_bus_lpfm_action(
        cls,
        nid: int,
        target_bus_id: int,
        transition_time: int = 2000,
        fade_curve: int = 4,
        bank_id: int = 0,
    ) -> "Action":
        """Creates an action that restores a bus's low-pass filter to default settings.

        Parameters
        ----------
        nid : int
            Action ID (hash).
        target_bus_id : int
            Target bus ID.
        transition_time : int, default=2000
            Transition time in milliseconds.
        fade_curve : int, default=4
            Fade curve type.
        bank_id : int, default=0
            ID of the target soundbank.

        Returns
        -------
        Action
            New Reset Bus LPFM action instance.
        """
        temp = cls.load_template(cls.__name__)
        action = cls(temp)

        action.id = nid
        action.action_type = ActionType.RESET_BUS_LPFM
        action.target_id = target_bus_id
        action.is_bus = True
        if transition_time != 0:
            action.transition_time = transition_time
        action.fade_curve = fade_curve
        action.bank_id = bank_id

        logger.info(f"Created new node {action}")
        return action

    def __new__(cls, node_dict: dict):
        action_classes = {
            ActionType.PLAY: PlayAction,
            ActionType.STOP: StopAction,
            ActionType.EVENT: EventAction,
            # TODO complete
        }

        action_type = node_dict["action_type"]
        new_cls = action_classes.get(action_type)
        if new_cls:
            return new_cls.__new__(new_cls, node_dict)

        return object.__new__(cls, node_dict)

    @property
    def action_type(self) -> ActionType | int:
        """Action type identifier.

        Returns
        -------
        int
            Action type code (e.g., 1027=Play, 259=Stop, 1538=Mute).
        """
        return ActionType(self["action_type"])

    @action_type.setter
    def action_type(self, value: ActionType) -> None:
        self["action_type"] = int(value)

    @property
    def target_id(self) -> int:
        """Target object ID.

        Returns
        -------
        int
            ID of the target sound/container/bus.
        """
        return self["external_id"]

    @target_id.setter
    def target_id(self, value: int) -> None:
        self["external_id"] = value

    @property
    def is_bus(self) -> bool:
        """Indicates whether this action targets a bus or a sound/container.

        Returns
        -------
        bool
            True if targeting a bus, False if targeting a sound/container.
        """
        return bool(self["is_bus"])

    @is_bus.setter
    def is_bus(self, value: bool) -> None:
        self["is_bus"] = int(value)

    @property
    def transition_time(self) -> int:
        """Transition time.

        Returns
        -------
        int
            Transition time in milliseconds (0 if not set).
        """
        for prop in self["prop_bundle"]:
            if "TransitionTime" in prop:
                return prop["TransitionTime"]
        return 0

    @transition_time.setter
    def transition_time(self, value: int) -> None:
        # Remove existing TransitionTime if present
        prop_bundle = self["prop_bundle"]
        prop_bundle[:] = [p for p in prop_bundle if "TransitionTime" not in p]
        # Add new value if non-zero
        if value != 0:
            prop_bundle.append({"TransitionTime": value})

    @property
    def delay(self) -> int:
        """Delay before this action activates.

        Returns
        -------
        int
            Delay in milliseconds (0 if not set).
        """
        for prop in self["prop_bundle"]:
            if "Delay" in prop:
                return prop["Delay"]
        return 0

    @delay.setter
    def delay(self, value: int) -> None:
        # Remove existing delay if present
        prop_bundle = self["prop_bundle"]
        prop_bundle[:] = [p for p in prop_bundle if "Delay" not in p]
        # Add new value if non-zero
        if value != 0:
            prop_bundle.append({"Delay": value})

    @property
    def params(self) -> dict[str, Any]:
        params = self["params"]
        if isinstance(params, str):
            # For reference actions like "PlayEvent"
            return None

        param_key = next(iter(params.keys()))
        return PathDict(params[param_key])

    def get_references(self) -> list[tuple[str, int]]:
        return super().get_references() + [("external_id", self.target_id)]


class PlayAction(Action):
    @classmethod
    def new(
        cls,
        nid: int,
        target_id: int,
        bank_id: int = 0,
        fade_curve: int = 4,
    ) -> "Action":
        """Creates an action that starts audio playback.

        Parameters
        ----------
        nid : int
            Action ID (hash).
        target_id : int
            Target sound/container ID to play.
        bank_id : int, default=0
            ID of the target soundbank.
        fade_curve : int, default=4
            Fade curve type.

        Returns
        -------
        Action
            New Play action instance.
        """
        action = cls._new_action(nid, ActionType.PLAY, "Play", is_bus=False)

        action = cls(action.dict)
        action.target_id = target_id
        action.fade_curve = fade_curve
        action.bank_id = bank_id

        logger.info(f"Created new node {action}")
        return action

    @property
    def fade_curve(self) -> int:
        """Fade curve (if applicable to this action type).

        Returns
        -------
        int
            Fade curve identifier (0 if not applicable).
        """
        return self.params.get("fade_curve", 0)

    @fade_curve.setter
    def fade_curve(self, value: int) -> None:
        self.params["fade_curve"] = value

    @property
    def bank_id(self) -> int:
        """Soundbank containing the target of this action.

        Returns
        -------
        int
            The soundbank's ID.
        """
        return self.params.get("bank_id", 0)

    @bank_id.setter
    def bank_id(self, value: int | Soundbank) -> None:
        if isinstance(value, Soundbank):
            value = value.id

        self.params["bank_id"] = value


class StopAction(Action):
    @classmethod
    def new(
        cls,
        nid: int,
        target_id: int,
        flags1: int = 4,
        flags2: int = 6,
        exceptions: list[int] = None,
    ) -> "Action":
        """Creates an action that stops audio playback.

        Parameters
        ----------
        nid : int
            Action ID (hash).
        target_id : int
            Target sound/container ID to stop.
        flags1 : int, default=4
            Stop flags 1.
        flags2 : int, default=6
            Stop flags 2.
        exceptions: list[int], default=None
            Objects that will not be stopped by this action.

        Returns
        -------
        Action
            New Stop action instance.
        """
        if exceptions is None:
            exceptions = []

        temp = cls._new_action(nid, ActionType.STOP, "StopEO")

        action = cls(temp.dict)
        action.target_id = target_id
        action.flags1 = flags1
        action.flags2 = flags2
        action.exceptions = exceptions or []

        logger.info(f"Created new node {action}")
        return action

    @property
    def flags1(self) -> int:
        return self.params["stop/flags1"]

    @flags1.setter
    def flags1(self, flags: int) -> None:
        self.params["stop/flags1"] = flags

    @property
    def flags2(self) -> int:
        return self.params["stop/flags2"]

    @flags2.setter
    def flags2(self, flags: int) -> None:
        self.params["stop/flags2"] = flags

    @property
    def exceptions(self) -> list[int]:
        """Objects excluded from this action's effects.

        Returns
        -------
        list[int]
            List of IDs to exclude from this action.
        """
        return self.params["except/exceptions"]

    @exceptions.setter
    def exceptions(self, exceptions: list[int]) -> None:
        self.params["except/exceptions"] = exceptions
        self.params["except/count"] = len(exceptions)

    def add_exception(self, exception_id: int) -> None:
        """Excludes a specific object from this action's effects.

        Parameters
        ----------
        exception_id : int
            ID of object to exclude from this action.
        """
        exceptions = self.params["except/exceptions"]
        if exception_id not in exceptions:
            exceptions.append(exception_id)
            self.params["except/count"] = len(exceptions)

    def clear_exceptions(self) -> None:
        """Clears all exceptions, allowing this action to affect all targets."""
        params = self.params
        if "except" in params:
            params["except/exceptions"] = []
            params["except/count"] = 0


class EventAction(Action):
    @classmethod
    def new(cls, nid: int, target_event: int) -> "Action":
        """Creates an action that triggers another event.

        Parameters
        ----------
        nid : int
            Action ID (hash).
        target_event : int
            ID of the event to trigger.

        Returns
        -------
        Action
            New PlayEvent action instance.
        """
        temp = cls._new_action(nid, ActionType.EVENT, None)

        action = cls(temp.dict)
        action.target_id = target_event
        # NOTE not a dict in this case!
        action["params"] = "PlayEvent"

        logger.info(f"Created new node {action}")
        return action


class SetStateAction(Action):
    @classmethod
    def new(
        cls,
        nid: int,
        switch_group_id: int,
        switch_state_id: int,
    ) -> "Action":
        temp = cls._new_action(nid, ActionType.SET_STATE, "SetState")

        action = cls(temp)
        action.id = nid
        action.switch_group_id = switch_group_id
        action.switch_state_id = switch_state_id

        logger.info(f"Created new node {action}")
        return action

    @property
    def switch_group_id(self) -> int:
        return self.params["switch_group_id"]

    @switch_group_id.setter
    def switch_group_id(self, flags: int) -> None:
        self.params["switch_group_id"] = flags

    @property
    def switch_state_id(self) -> int:
        return self.params["switch_state_id"]

    @switch_state_id.setter
    def switch_state_id(self, flags: int) -> None:
        self.params["switch_state_id"] = flags

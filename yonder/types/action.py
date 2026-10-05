from __future__ import annotations
from typing import Any, ClassVar
from dataclasses import dataclass, field, replace
import pyo

from yonder.hash import Hash, calc_hash
from yonder.enums import (
    ValueMeaning,
    ActionType,
    ActionScope,
    CurveInterpolation,
    PropID,
)
from yonder.util import logger
from yonder.audio import PlayContext, PlaybackState
from .base_types import PropBundle, PropRangedModifiers
from .hirc_node import HIRCNode
from .serialization import _serialize_value, _deserialize_fields
from .mixins import PropertyMixin


# The high byte of an ActionType picks the verb, the low byte the ActionScope.
# Only the verbs we have constructors for are named here.
_STOP = 0x01
_PAUSE = 0x02
_RESUME = 0x03
_PLAY = 0x04
_MUTE = 0x06
_UNMUTE = 0x07
_SET_GAME_PARAMETER = 0x13
_SEEK = 0x1E

# Properties with a dedicated set/reset action verb. Note that reset is *not*
# simply set + 1 - the HPF actions sit in a different range than the rest.
PROP_ACTIONS: dict[PropID, tuple[int, int]] = {
    PropID.Pitch: (0x08, 0x09),
    PropID.Volume: (0x0A, 0x0B),
    PropID.BusVolume: (0x0C, 0x0D),
    PropID.LPF: (0x0E, 0x0F),
    PropID.HPF: (0x20, 0x30),
}


def resolve_action_type(verb: int, scope: ActionScope) -> ActionType:
    """Combine a verb byte and an `ActionScope` into the matching `ActionType`.

    Raises if the combination doesn't exist, which is common - most verbs only
    support a subset of the scopes. Use `get_action_scopes` to find out which.
    """
    try:
        return ActionType((verb << 8) | int(scope))
    except ValueError:
        raise ValueError(
            f"There is no action for verb 0x{verb:02X} with scope "
            f"{ActionScope(scope).name}"
        ) from None


def get_action_scope(action_type: ActionType) -> ActionScope:
    """An action type's scope, or None if it doesn't follow the verb/scope scheme.

    A few types encode something else entirely in their low byte, e.g.
    `SetSwitch` (0x1901) or `Trigger` (0x1D00).
    """
    try:
        return ActionScope(action_type & 0xFF)
    except ValueError:
        return None


def get_valid_action_scopes(action_type: ActionType) -> list[ActionScope]:
    """The scopes an action type's verb can be switched to, supported ones only."""
    ret = []

    for scope in ActionScope:
        try:
            other = resolve_action_type(action_type.verb(), scope)
        except ValueError:
            continue

        if get_params_for_action(other) is not None:
            ret.append(scope)

    return ret


def _prop_verbs(prop: PropID) -> tuple[int, int]:
    verbs = PROP_ACTIONS.get(prop)
    if verbs is None:
        supported = ", ".join(p.name for p in PROP_ACTIONS)
        raise ValueError(f"{prop.name} has no action, expected one of {supported}")

    return verbs


def _as_hash(value: Hash | HIRCNode) -> int:
    if isinstance(value, HIRCNode):
        return value.id

    if isinstance(value, str):
        return calc_hash(value)

    return int(value or 0)


def _make_exceptions(
    exceptions: list[Hash | tuple[Hash, bool]] = None,
) -> ActionParamsExcept:
    """Normalize an exception list, entries being either an object or (object, is_bus)."""
    items = []

    for entry in exceptions or []:
        is_bus = False
        if isinstance(entry, tuple):
            entry, is_bus = entry

        items.append(ActionParamsExceptEntry(_as_hash(entry), 1 if is_bus else 0))

    return ActionParamsExcept(len(items), items)


@dataclass(repr=False, eq=False)
class Action(PropertyMixin, HIRCNode):
    body_type: ClassVar[int] = 3
    action_type: int = 0
    external_id: int = 0
    params: ActionParams | str = None
    is_bus: int = 0  # NOTE not a bool!
    prop_bundle: list[PropBundle] = field(default_factory=list)
    ranged_modifiers: PropRangedModifiers = field(default_factory=PropRangedModifiers)

    def __post_init__(self, id: Hash):
        super().__post_init__(id)

        if self.action_type == 0:
            if self.params == "PlayEvent":
                self.action_type = ActionType.PlayEvent.value
            else:
                self.action_type = self.params.action_type.value

        if self.action_type == ActionType.Unk2102:
            logger.warning(f"Found action with unknown type {self.action_type}: {self}")
        elif self.action_type == ActionType.PlayEvent:
            # NOTE rewwise is strange, for PlayEvents params will actually be a string
            if not isinstance(self.params, str):
                logger.warning("Found unexpectedly normal PlayEvent")

    # === Constructors ==================================================

    @classmethod
    def new(
        cls,
        nid: Hash,
        action_type: ActionType,
        target: Hash | HIRCNode = 0,
        *,
        props: dict[PropID, float] = None,
        is_bus: bool = False,
        **params: Any,
    ) -> Action:
        """Create an action of any supported type.

        This is the generic form; the verb constructors below (`new_play`,
        `new_stop`, `new_set_prop`, ...) are nicer to use and cover everything
        except the exotic types. `params` are forwarded to the `ActionParams`
        subclass belonging to `action_type` and default to whatever that class
        declares.

        Parameters
        ----------
        nid : Hash
            ID or name of the new action.
        action_type : ActionType
            What the action does, including its `ActionScope`.
        target : Hash | HIRCNode, default=0
            The object the action refers to. For `ActionScope.Except` scopes
            this is the object everything else is applied *except* to.
        props : dict[PropID, float], optional
            Properties to set on the action itself.
        is_bus : bool, default=False
            Whether `target` is a bus rather than a regular node.
        """
        params_cls = get_params_for_action(action_type)
        if params_cls is None:
            raise ValueError(f"Action type {action_type.name} is not supported yet")

        if params_cls is str:
            # NOTE rewwise is strange, for PlayEvents params will be a string
            action_params = "PlayEvent"
        else:
            action_params = params_cls(action_type, **params)

        obj = cls(
            id=nid,
            external_id=_as_hash(target),
            params=action_params,
            is_bus=1 if is_bus else 0,
        )

        if props:
            for prop, val in props.items():
                obj.set_property(prop, val)

        return obj

    @classmethod
    def new_play(
        cls,
        nid: Hash,
        target: Hash | HIRCNode,
        *,
        bank_id: Hash = 0,
        fade_curve: CurveInterpolation = CurveInterpolation.Linear,
        props: dict[PropID, float] = None,
    ) -> Action:
        """Start playing `target`. Wwise only uses one scope for this verb."""
        return cls.new(
            nid,
            ActionType.Play,
            target,
            props=props,
            bank_id=_as_hash(bank_id),
            fade_curve=int(fade_curve),
        )

    @classmethod
    def new_play_event(cls, nid: Hash, event: Hash | HIRCNode) -> Action:
        """Post another event, i.e. run all of its actions."""
        return cls.new(nid, ActionType.PlayEvent, event)

    @classmethod
    def new_stop(
        cls,
        nid: Hash,
        target: Hash | HIRCNode,
        *,
        scope: ActionScope = ActionScope.TargetLocal,
        exceptions: list[Hash | tuple[Hash, bool]] = None,
        flags1: int = 4,  # ? usually 4, rarely 7
        flags2: int = 6,  # ? usually 6
    ) -> Action:
        """Stop `target`."""
        return cls.new(
            nid,
            resolve_action_type(_STOP, scope),
            target,
            stop=ActionStopParams(flags1=flags1, flags2=flags2),
            except_=_make_exceptions(exceptions),
        )

    @classmethod
    def new_pause(
        cls,
        nid: Hash,
        target: Hash | HIRCNode,
        *,
        scope: ActionScope = ActionScope.Target,
        fade_curve: CurveInterpolation = CurveInterpolation.Linear,
        exceptions: list[Hash | tuple[Hash, bool]] = None,
        flags: int = 0,
    ) -> Action:
        """Pause `target`, keeping its playback position."""
        return cls.new(
            nid,
            resolve_action_type(_PAUSE, scope),
            target,
            pause=ActionPauseParams(flags=flags),
            except_=_make_exceptions(exceptions),
            fade_curve=int(fade_curve),
        )

    @classmethod
    def new_resume(
        cls,
        nid: Hash,
        target: Hash | HIRCNode,
        *,
        scope: ActionScope = ActionScope.Target,
        fade_curve: CurveInterpolation = CurveInterpolation.Linear,
        master_resume: bool = False,
        exceptions: list[Hash | tuple[Hash, bool]] = None,
    ) -> Action:
        """Resume `target` where a pause action left it."""
        return cls.new(
            nid,
            resolve_action_type(_RESUME, scope),
            target,
            fade_curve=int(fade_curve),
            resume=1 if master_resume else 0,
            except_=_make_exceptions(exceptions),
        )

    @classmethod
    def new_mute(
        cls,
        nid: Hash,
        target: Hash | HIRCNode,
        *,
        scope: ActionScope = ActionScope.Target,
        fade_curve: CurveInterpolation = CurveInterpolation.Linear,
        exceptions: list[Hash | tuple[Hash, bool]] = None,
    ) -> Action:
        """Silence `target` without stopping it."""
        return cls.new(
            nid,
            resolve_action_type(_MUTE, scope),
            target,
            fade_curve=int(fade_curve),
            except_=_make_exceptions(exceptions),
        )

    @classmethod
    def new_unmute(
        cls,
        nid: Hash,
        target: Hash | HIRCNode,
        *,
        scope: ActionScope = ActionScope.Target,
        fade_curve: CurveInterpolation = CurveInterpolation.Linear,
        exceptions: list[Hash | tuple[Hash, bool]] = None,
    ) -> Action:
        """Undo a mute action on `target`."""
        return cls.new(
            nid,
            resolve_action_type(_UNMUTE, scope),
            target,
            fade_curve=int(fade_curve),
            except_=_make_exceptions(exceptions),
        )

    @classmethod
    def new_set_prop(
        cls,
        nid: Hash,
        target: Hash | HIRCNode,
        prop: PropID,
        value: float,
        *,
        scope: ActionScope = ActionScope.Target,
        meaning: ValueMeaning = ValueMeaning.Offset,
        value_min: float = 0.0,
        value_max: float = 0.0,
        fade_curve: CurveInterpolation = CurveInterpolation.Linear,
        exceptions: list[Hash | tuple[Hash, bool]] = None,
        is_bus: bool = False,
    ) -> Action:
        """Override one of `target`'s properties for as long as the action lasts.

        Only the properties in `PROP_ACTIONS` have their own action verb.
        `value_min`/`value_max` randomize the value per activation.
        """
        return cls.new(
            nid,
            resolve_action_type(_prop_verbs(prop)[0], scope),
            target,
            is_bus=is_bus,
            set_ak_prop=ActionSetAkPropParams(
                value_meaning=meaning,
                randomizer_modifier=RandomizerModifier(value, value_min, value_max),
            ),
            except_=_make_exceptions(exceptions),
            fade_curve=int(fade_curve),
        )

    @classmethod
    def new_reset_prop(
        cls,
        nid: Hash,
        target: Hash | HIRCNode,
        prop: PropID,
        *,
        scope: ActionScope = ActionScope.Target,
        fade_curve: CurveInterpolation = CurveInterpolation.Linear,
        exceptions: list[Hash | tuple[Hash, bool]] = None,
        is_bus: bool = False,
    ) -> Action:
        """Undo a `new_set_prop` action, restoring the authored value."""
        return cls.new(
            nid,
            resolve_action_type(_prop_verbs(prop)[1], scope),
            target,
            is_bus=is_bus,
            set_ak_prop=ActionSetAkPropParams(),
            except_=_make_exceptions(exceptions),
            fade_curve=int(fade_curve),
        )

    @classmethod
    def new_seek(
        cls,
        nid: Hash,
        target: Hash | HIRCNode,
        position: float,
        *,
        scope: ActionScope = ActionScope.TargetLocal,
        relative_to_duration: bool = False,
        snap_to_marker: bool = False,
        exceptions: list[Hash | tuple[Hash, bool]] = None,
    ) -> Action:
        """Jump `target` to `position`, in ms or as a 0..1 fraction of its duration."""
        return cls.new(
            nid,
            resolve_action_type(_SEEK, scope),
            target,
            seek=ActionSeekParams(
                is_seek_relative_to_duration=1 if relative_to_duration else 0,
                randomizer_modifier=RandomizerModifier(position),
                snap_to_nearest_marker=1 if snap_to_marker else 0,
            ),
            except_=_make_exceptions(exceptions),
        )

    @classmethod
    def new_set_state(cls, nid: Hash, state_group: Hash, value: Hash) -> Action:
        """Set a global state, e.g. to switch what a MusicSwitchContainer plays."""
        # NOTE: SetState actions from rewwise have the correct type ID but use
        # ActionSetSwitch, so that's what we have to write to round-trip.
        # See https://github.com/vswarte/rewwise/pull/5
        return cls.new(
            nid,
            ActionType.SetState,
            value,
            switch_group_id=_as_hash(state_group),
            switch_state_id=_as_hash(value),
        )

    @classmethod
    def new_set_switch(cls, nid: Hash, switch_group: Hash, value: Hash) -> Action:
        """Set a switch, i.e. a state scoped to the calling game object."""
        return cls.new(
            nid,
            ActionType.SetSwitch,
            value,
            switch_group_id=_as_hash(switch_group),
            switch_state_id=_as_hash(value),
        )

    @classmethod
    def new_set_game_parameter(
        cls,
        nid: Hash,
        target: Hash | HIRCNode,
        value: float,
        *,
        scope: ActionScope = ActionScope.Target,
        meaning: ValueMeaning = ValueMeaning.Default,
        value_min: float = 0.0,
        value_max: float = 0.0,
        bypass_transition: bool = False,
        exceptions: list[Hash | tuple[Hash, bool]] = None,
    ) -> Action:
        """Set an RTPC game parameter, `target` being the parameter itself."""
        return cls.new(
            nid,
            resolve_action_type(_SET_GAME_PARAMETER, scope),
            target,
            set_game_parameter=ActionSetGameParameterParams(
                bypass_transition=1 if bypass_transition else 0,
                value_meaning=meaning,
                randomizer_modifier=RandomizerModifier(value, value_min, value_max),
            ),
            except_=_make_exceptions(exceptions),
        )

    @staticmethod
    def supported_types() -> list[ActionType]:
        """The action types yonder can create and serialize, in enum order.

        Everything else in `ActionType` is known by name only - rewwise doesn't
        model its parameters yet, so we can't write it back out.
        """
        return [t for t in ActionType if get_params_for_action(t) is not None]

    @property
    def wwise_link(self) -> str:
        return "https://ndahn.github.io/yonder/wwise/events/#actions"

    @property
    def action_type_enum(self) -> ActionType:
        # NOTE "action_type" is already reserved for serialization
        return ActionType(self.action_type)

    @property
    def scope(self) -> ActionScope:
        """Which objects this action affects, or None if its type has no scope."""
        return get_action_scope(self.action_type_enum)

    def change_type(self, new_type: ActionType) -> None:
        """Turn this into an action of another type, keeping compatible params."""
        params_cls = get_params_for_action(new_type)
        if params_cls is None:
            raise ValueError(f"Action type {new_type.name} is not supported yet")

        if params_cls is str:
            params = "PlayEvent"
        elif isinstance(self.params, params_cls):
            # Same parameters, e.g. only the scope changed - keep what's set
            params = replace(self.params, action_type=new_type)
        else:
            params = params_cls(new_type)

        self.action_type = new_type.value
        self.params = params

    def change_scope(self, new_scope: ActionScope) -> None:
        """Keep the verb, but apply it to a different set of objects."""
        self.change_type(resolve_action_type(self.action_type_enum.verb(), new_scope))

    @property
    def properties(self) -> list[PropBundle]:
        return self.prop_bundle

    def attach(self, other: int | HIRCNode) -> None:
        from .event import Event

        if isinstance(other, HIRCNode):
            if (
                isinstance(other, Event)
                and self.action_type_enum != ActionType.PlayEvent
            ):
                raise ValueError("Cannot attach an event to a non-PlayEvent action")

            if isinstance(other, Action):
                raise ValueError("Cannot attach actions to actions")

            other = other.id

        self.external_id = int(other)

    def detach(self, other: int | HIRCNode) -> None:
        if isinstance(other, HIRCNode):
            other = other.id

        if self.external_id == other:
            self.external_id = 0

    def get_references(self) -> list[tuple[str, int]]:
        return [("external_id", self.external_id)]

    def _build_pyo(self, my_pyo: PlaybackState) -> pyo.PyoObject:
        node = my_pyo.ctx.bank.get(self.external_id)
        if node:
            return node.pyo(my_pyo.ctx).output

        return pyo.Sig(0)

    def play(self, ctx: PlayContext) -> None:
        my_pyo = self.pyo(ctx)
        if my_pyo.playing:
            return

        ctx = my_pyo.ctx

        if self.action_type_enum == ActionType.SetState:
            # TODO mistake in rewwise
            params: ActionSetSwitch = self.params
            ctx.states[params.switch_group_id] = params.switch_state_id

        elif self.action_type_enum == ActionType.SetSwitch:
            params: ActionSetSwitch = self.params
            ctx.states[params.switch_group_id] = params.switch_state_id

        # game objects: something in-game which posted an event
        # E: reference (global scope)
        # EO: reference owned by calling game object (local scope)
        # AE: everything except the global reference
        # AEO: everything except the local reference
        # ALL: all playing nodes?
        # M: seems to have no meaning
        elif self.action_type_enum in (
            ActionType.SetVolumeM,
            ActionType.SetVolumeO,
            ActionType.ResetVolumeM,
            ActionType.ResetVolumeO,
            ActionType.ResetVolumeALL,
            ActionType.SetPitchM,
            ActionType.SetPitchO,
            ActionType.ResetPitchM,
            ActionType.ResetPitchO,
            ActionType.ResetPitchALL,
            ActionType.ResetPitchALLO,
            ActionType.ResetPitchAE,
            ActionType.ResetPitchAEO,
            ActionType.SetLPFM,
            ActionType.SetLPFO,
            ActionType.ResetLPFM,
            ActionType.ResetLPFO,
            ActionType.ResetLPFALL,
            ActionType.SetHPFM,
            ActionType.SetHPFO,
            ActionType.ResetHPFM,
            ActionType.ResetHPFALL,
            # Busses not simulated for now
            # ActionType.SetBusVolumeM,
            # ActionType.ResetBusVolumeM,
            # ActionType.ResetBusVolumeALL,
        ):
            logger.warning(
                f"Don't know how to handle action type {self.action_type_enum.name} yet:\n{self.json()}"
            )

        elif self.action_type_enum in (ActionType.Play, ActionType.PlayEvent):
            node = ctx.bank.get(self.external_id)
            if node:
                node.play(ctx)

        elif self.action_type_enum in (
            ActionType.StopE,
            ActionType.StopEO,
            ActionType.StopAEO,
            ActionType.StopEvent,
        ):
            node = ctx.bank.get(self.external_id)
            if node:
                node.stop(ctx)

        elif self.action_type_enum in (
            ActionType.SeekE,
            ActionType.SeekEO,
            ActionType.SeekAE,
            ActionType.SeekAEO,
            ActionType.SeekALL,
            ActionType.SeekALLO,
            ActionType.SetGameParameter,  # RTPC?
            ActionType.SetGameParameterO,
        ):
            logger.warning(
                f"Don't know how to handle action type {self.action_type_enum.name} yet:\n{self.json()}"
            )

        my_pyo.play()

    def __str__(self) -> str:
        return f"[A] <{self.action_type_enum.name}> #{self.id}"


@dataclass
class ActionParams:
    action_type: ActionType

    def to_dict(self) -> dict:
        # Needed for serialization, but not part of it
        data = _serialize_value(self)
        data.pop("action_type")
        return {self.action_type.name: data}

    @classmethod
    def from_dict(cls, data: dict) -> ActionParams:
        action_type = ActionType[next(iter(data.keys()))]
        param_cls = get_params_for_action(action_type)
        if not param_cls:
            raise KeyError(f"Action type {action_type} is not supported yet")

        param_data = data[action_type.name]
        param_data["action_type"] = action_type
        return _deserialize_fields(param_cls, param_data)


@dataclass(slots=True)
class RandomizerModifier:
    base: float = 0.0
    min: float = 0.0
    max: float = 0.0


@dataclass(slots=True)
class ActionParamsExceptEntry:
    object_id: int = 0
    is_bus: int = 0


@dataclass(slots=True)
class ActionParamsExcept:
    count: int = 0
    exceptions: list[ActionParamsExceptEntry] = field(default_factory=list)


@dataclass
class ActionSetState(ActionParams):
    state_group_id: int = 0
    target_state_id: int = 0


@dataclass
class ActionSetSwitch(ActionParams):
    switch_group_id: int = 0
    switch_state_id: int = 0


@dataclass(slots=True)
class ActionSetGameParameterParams:
    bypass_transition: int = 0
    value_meaning: ValueMeaning = ValueMeaning.Default
    randomizer_modifier: RandomizerModifier = field(default_factory=RandomizerModifier)


@dataclass
class ActionSetGameParameter(ActionParams):
    set_game_parameter: ActionSetGameParameterParams = field(
        default_factory=ActionSetGameParameterParams
    )
    except_: ActionParamsExcept = field(default_factory=ActionParamsExcept)
    flags: int = 0


@dataclass
class ActionMute(ActionParams):
    fade_curve: int = 0
    except_: ActionParamsExcept = field(default_factory=ActionParamsExcept)


@dataclass
class ActionResume(ActionParams):
    fade_curve: int = 0
    resume: int = 0
    except_: ActionParamsExcept = field(default_factory=ActionParamsExcept)


@dataclass(slots=True)
class ActionSetAkPropParams:
    value_meaning: ValueMeaning = ValueMeaning.Default
    randomizer_modifier: RandomizerModifier = field(default_factory=RandomizerModifier)


@dataclass
class ActionSetAkProp(ActionParams):
    set_ak_prop: ActionSetAkPropParams = field(default_factory=ActionSetAkPropParams)
    except_: ActionParamsExcept = field(default_factory=ActionParamsExcept)
    fade_curve: int = 0


@dataclass(slots=True)
class ActionSeekParams:
    is_seek_relative_to_duration: int = 0
    randomizer_modifier: RandomizerModifier = field(default_factory=RandomizerModifier)
    snap_to_nearest_marker: int = 0


@dataclass
class ActionSeek(ActionParams):
    seek: ActionSeekParams = field(default_factory=ActionSeekParams)
    except_: ActionParamsExcept = field(default_factory=ActionParamsExcept)


@dataclass
class ActionPlay(ActionParams):
    bank_id: int = 0
    fade_curve: int = 4


@dataclass(slots=True)
class ActionPauseParams:
    flags: int = 0


@dataclass
class ActionPause(ActionParams):
    pause: ActionPauseParams = field(default_factory=ActionPauseParams)
    except_: ActionParamsExcept = field(default_factory=ActionParamsExcept)
    fade_curve: int = 0


@dataclass(slots=True)
class ActionStopParams:
    # NOTE: unknown, usually 4 and 6, sometimes 7 and 6
    flags1: int = 4
    flags2: int = 6


@dataclass
class ActionStop(ActionParams):
    stop: ActionStopParams = field(default_factory=ActionStopParams)
    except_: ActionParamsExcept = field(default_factory=ActionParamsExcept)


def get_params_for_action(action_type: ActionType) -> type[ActionParams]:
    return {
        ActionType.None_: None,
        ActionType.SetState: ActionSetSwitch,  # NOTE mistake in rewwise
        ActionType.BypassFXM: None,
        ActionType.BypassFXO: None,
        ActionType.ResetBypassFXM: None,
        ActionType.ResetBypassFXO: None,
        ActionType.ResetBypassFXALL: None,
        ActionType.ResetBypassFXALLO: None,
        ActionType.ResetBypassFXAE: None,
        ActionType.ResetBypassFXAEO: None,
        ActionType.SetSwitch: ActionSetSwitch,
        ActionType.UseStateE: None,
        ActionType.UnuseStateE: None,
        ActionType.Play: ActionPlay,
        ActionType.PlayAndContinue: None,
        ActionType.StopE: ActionStop,
        ActionType.StopEO: ActionStop,
        ActionType.StopALL: None,
        ActionType.StopALLO: None,
        ActionType.StlopAE: None,
        ActionType.StopAEO: None,
        ActionType.PauseE: ActionPause,
        ActionType.PauseEO: None,
        ActionType.PauseALL: None,
        ActionType.PauseALLO: None,
        ActionType.PauseAE: None,
        ActionType.PauseAEO: None,
        ActionType.ResumeE: ActionResume,
        ActionType.ResumeEO: None,
        ActionType.ResumeALL: None,
        ActionType.ResumeALLO: None,
        ActionType.ResumeAE: None,
        ActionType.ResumeAEO: None,
        ActionType.BreakE: None,
        ActionType.BreakEO: None,
        ActionType.MuteM: ActionMute,
        ActionType.MuteO: ActionMute,
        ActionType.UnmuteM: ActionMute,
        ActionType.UnmuteO: ActionMute,
        ActionType.UnmuteALL: ActionMute,
        ActionType.UnmuteALLO: ActionMute,
        ActionType.UnmuteAE: ActionMute,
        ActionType.UnmuteAEO: ActionMute,
        ActionType.SetVolumeM: ActionSetAkProp,
        ActionType.SetVolumeO: ActionSetAkProp,
        ActionType.ResetVolumeM: ActionSetAkProp,
        ActionType.ResetVolumeO: ActionSetAkProp,
        ActionType.ResetVolumeALL: ActionSetAkProp,
        ActionType.ResetVolumeALLO: None,
        ActionType.ResetVolumeAE: None,
        ActionType.ResetVolumeAEO: None,
        ActionType.SetPitchM: ActionSetAkProp,
        ActionType.SetPitchO: ActionSetAkProp,
        ActionType.ResetPitchM: ActionSetAkProp,
        ActionType.ResetPitchO: ActionSetAkProp,
        ActionType.ResetPitchALL: ActionSetAkProp,
        ActionType.ResetPitchALLO: ActionSetAkProp,
        ActionType.ResetPitchAE: ActionSetAkProp,
        ActionType.ResetPitchAEO: ActionSetAkProp,
        ActionType.SetLPFM: ActionSetAkProp,
        ActionType.SetLPFO: ActionSetAkProp,
        ActionType.ResetLPFM: ActionSetAkProp,
        ActionType.ResetLPFO: ActionSetAkProp,
        ActionType.ResetLPFALL: ActionSetAkProp,
        ActionType.ResetLPFALLO: None,
        ActionType.ResetLPFAE: None,
        ActionType.ResetLPFAEO: None,
        ActionType.SetHPFM: ActionSetAkProp,
        ActionType.SetHPFO: ActionSetAkProp,
        ActionType.ResetHPFM: ActionSetAkProp,
        ActionType.ResetHPFO: None,
        ActionType.ResetHPFALL: ActionSetAkProp,
        ActionType.ResetHPFALLO: None,
        ActionType.ResetHPFAE: None,
        ActionType.ResetHPFAEO: None,
        ActionType.SetBusVolumeM: ActionSetAkProp,
        ActionType.SetBusVolumeO: None,
        ActionType.ResetBusVolumeM: ActionSetAkProp,
        ActionType.ResetBusVolumeO: None,
        ActionType.ResetBusVolumeALL: ActionSetAkProp,
        ActionType.ResetBusVolumeAE: None,
        ActionType.StopEvent: None,
        ActionType.PauseEvent: None,
        ActionType.ResumeEvent: None,
        ActionType.Duck: None,
        ActionType.Trigger: None,
        ActionType.TriggerO: None,
        ActionType.SeekE: None,
        ActionType.SeekEO: ActionSeek,
        ActionType.SeekALL: None,
        ActionType.SeekALLO: None,
        ActionType.SeekAE: None,
        ActionType.SeekAEO: None,
        ActionType.ResetPlaylistE: None,
        ActionType.ResetPlaylistEO: None,
        ActionType.SetGameParameter: ActionSetGameParameter,
        ActionType.SetGameParameterO: None,
        ActionType.ResetGameParameter: None,
        ActionType.ResetGameParameterO: None,
        ActionType.Release: None,
        ActionType.ReleaseO: None,
        ActionType.Unk2102: None,
        ActionType.PlayEvent: str,
    }[action_type]

from __future__ import annotations
from typing import ClassVar
from dataclasses import dataclass, field
import pyo

from yonder.hash import Hash
from yonder.enums import ValueMeaning, ActionType
from yonder.util import logger
from yonder.audio import PlayContext
from .base_types import PropBundle, PropRangedModifiers
from .hirc_node import HIRCNode
from .serialization import _serialize_value, _deserialize_fields
from .mixins import PropertyMixin


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

    @classmethod
    def new_play_action(
        cls, nid: int, external_id: int, bank_id: int = 0, fade_curve: int = 4
    ) -> Action:
        return cls(
            id=nid,
            external_id=external_id,
            params=ActionPlay(ActionType.Play, bank_id, fade_curve),
        )

    @classmethod
    def new_stop_action(
        cls,
        nid: int,
        external_id: int,
        flags1: int = 4,  # ? usually 4, rarely 7
        flags2: int = 6,  # ? usually 6
        exceptions: list[int | tuple[int, bool]] = None,
    ) -> Action:
        if exceptions:
            exc_items = []
            for oid in exceptions:
                is_bus = False
                if isinstance(oid, tuple):
                    oid, is_bus = oid
                exc_items.append(ActionParamsExceptEntry(oid, is_bus))
        else:
            exc_items = []

        return cls(
            id=nid,
            external_id=external_id,
            params=ActionStop(
                ActionType.StopEO,
                ActionStopParams(flags1=flags1, flags2=flags2),
                ActionParamsExcept(exceptions=exc_items),
            ),
        )

    @classmethod
    def new_setstate_action(
        cls,
        nid: int,
        state_group: Hash,
        value: Hash,
    ) -> Action:
        # NOTE: SetState actions from rewwise have the correct type ID but use ActionSetSwitch.
        # See https://github.com/vswarte/rewwise/pull/5
        return cls(
            id=nid,
            external_id=value,
            params=ActionSetState(
                ActionType.SetState,
                state_group_id=state_group,
                target_state_id=value,
            ),
        )

    @property
    def action_type_enum(self) -> ActionType:
        # NOTE "action_type" is already reserved for serialization
        return ActionType(self.action_type)

    def change_type(self, new_type: ActionType) -> None:
        if not new_type.params_cls:
            raise ValueError(f"Action type {new_type} is not supported yet")

        if new_type == ActionType.PlayEvent:
            params = "PlayEvent"
        else:
            params = get_params_for_action(new_type)(new_type)

        self.action_type = new_type.value
        self.params = params

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

    def _build_pyo(self, ctx: PlayContext) -> pyo.PyoObject:
        node = ctx.bank.get(self.external_id)
        if node:
            return node.pyo(ctx)

        return pyo.Sig(0)

    def play(self, ctx: PlayContext) -> None:
        ctx, my_pyo = self.pyo(ctx)

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

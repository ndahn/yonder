from __future__ import annotations
from typing import Type, ClassVar
from dataclasses import dataclass, field
from enum import Enum

from yonder.enums import ValueMeaning
from yonder.util import logger
from .base_types import PropBundle, PropRangedModifiers
from .hirc_node import HIRCNode
from .serialization import _serialize_value, _deserialize_fields


@dataclass
class Action(HIRCNode):
    body_type: ClassVar[int] = 3
    action_type: int = 0
    external_id: int = 0
    params: ActionParams = None
    is_bus: int = 0
    prop_bundle: list[PropBundle] = field(default_factory=list)
    ranged_modifiers: PropRangedModifiers = field(default_factory=PropRangedModifiers)

    def __post_init__(self, nid: int | str):
        try:
            action_type = ActionType(self.action_type)
        except KeyError:
            action_type = None

        if not action_type or action_type == ActionType.Unk2102:
            logger.warning(f"Found action with unknown type {self.action_type}: {self}")
        elif action_type == ActionType.PlayEvent:
            # NOTE rewwise is strange, for PlayEvents params will actually be a string
            if not isinstance(self.params, str):
                logger.warning("Found unexpectedly normal PlayEvent")

    @classmethod
    def new_play_action(
        cls, nid: int, external_id: int, bank_id: int = 0, fade_curve: int = 4
    ) -> Action:
        return cls(
            nid,
            external_id,
            is_bus=False,
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
            nid,
            external_id,
            is_bus=False,
            params=ActionStop(
                ActionType.StopEO,
                ActionStopParams(flags1=flags1, flags2=flags2),
                ActionParamsExcept(exceptions=exc_items),
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
            params = new_type.params_cls(new_type)

        self.action_type = new_type.type_id
        self.params = params

    def get_references(self) -> list[tuple[str, int]]:
        return [("external_id", self.external_id)]

    def __str__(self) -> str:
        return f"Action<{self.action_type_enum.name}> #{self.id}"


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
        param_cls = action_type.params_cls
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


class ActionType(Enum):
    type_id: int
    params_cls: Type[ActionParams]

    def __new__(cls, type_id: int, params_cls: Type[ActionParams]):
        member = object.__new__(cls)
        member._value_ = type_id
        member.type_id = type_id
        member.params_cls = params_cls
        return member

    None_ = 0x0000, None
    SetState = 0x1204, ActionSetSwitch
    BypassFXM = 0x1A02, None
    BypassFXO = 0x1A03, None
    ResetBypassFXM = 0x1B02, None
    ResetBypassFXO = 0x1B03, None
    ResetBypassFXALL = 0x1B04, None
    ResetBypassFXALLO = 0x1B05, None
    ResetBypassFXAE = 0x1B08, None
    ResetBypassFXAEO = 0x1B09, None
    SetSwitch = 0x1901, ActionSetSwitch
    UseStateE = 0x1002, None
    UnuseStateE = 0x1102, None
    Play = 0x0403, ActionPlay
    PlayAndContinue = 0x0503, None
    StopE = 0x0102, ActionStop
    StopEO = 0x0103, ActionStop
    StopALL = 0x0104, None
    StopALLO = 0x0105, None
    StlopAE = 0x0108, None
    StopAEO = 0x0109, None
    PauseE = 0x0202, ActionPause
    PauseEO = 0x0203, None
    PauseALL = 0x0204, None
    PauseALLO = 0x0205, None
    PauseAE = 0x0208, None
    PauseAEO = 0x0209, None
    ResumeE = 0x0302, ActionResume
    ResumeEO = 0x0303, None
    ResumeALL = 0x0304, None
    ResumeALLO = 0x0305, None
    ResumeAE = 0x0308, None
    ResumeAEO = 0x0309, None
    BreakE = 0x1C02, None
    BreakEO = 0x1C03, None
    MuteM = 0x0602, ActionMute
    MuteO = 0x0603, ActionMute
    UnmuteM = 0x0702, ActionMute
    UnmuteO = 0x0703, ActionMute
    UnmuteALL = 0x0704, ActionMute
    UnmuteALLO = 0x0705, ActionMute
    UnmuteAE = 0x0708, ActionMute
    UnmuteAEO = 0x0709, ActionMute
    SetVolumeM = 0x0A02, ActionSetAkProp
    SetVolumeO = 0x0A03, ActionSetAkProp
    ResetVolumeM = 0x0B02, ActionSetAkProp
    ResetVolumeO = 0x0B03, ActionSetAkProp
    ResetVolumeALL = 0x0B04, ActionSetAkProp
    ResetVolumeALLO = 0x0B05, None
    ResetVolumeAE = 0x0B08, None
    ResetVolumeAEO = 0x0B09, None
    SetPitchM = 0x0802, ActionSetAkProp
    SetPitchO = 0x0803, ActionSetAkProp
    ResetPitchM = 0x0902, ActionSetAkProp
    ResetPitchO = 0x0903, ActionSetAkProp
    ResetPitchALL = 0x0904, ActionSetAkProp
    ResetPitchALLO = 0x0905, ActionSetAkProp
    ResetPitchAE = 0x0908, ActionSetAkProp
    ResetPitchAEO = 0x0909, ActionSetAkProp
    SetLPFM = 0x0E02, ActionSetAkProp
    SetLPFO = 0x0E03, ActionSetAkProp
    ResetLPFM = 0x0F02, ActionSetAkProp
    ResetLPFO = 0x0F03, ActionSetAkProp
    ResetLPFALL = 0x0F04, ActionSetAkProp
    ResetLPFALLO = 0x0F05, None
    ResetLPFAE = 0x0F08, None
    ResetLPFAEO = 0x0F09, None
    SetHPFM = 0x2002, ActionSetAkProp
    SetHPFO = 0x2003, ActionSetAkProp
    ResetHPFM = 0x3002, ActionSetAkProp
    ResetHPFO = 0x3003, None
    ResetHPFALL = 0x3004, ActionSetAkProp
    ResetHPFALLO = 0x3005, None
    ResetHPFAE = 0x3008, None
    ResetHPFAEO = 0x3009, None
    SetBusVolumeM = 0x0C02, ActionSetAkProp
    SetBusVolumeO = 0x0C03, None
    ResetBusVolumeM = 0x0D02, ActionSetAkProp
    ResetBusVolumeO = 0x0D03, None
    ResetBusVolumeALL = 0x0D04, ActionSetAkProp
    ResetBusVolumeAE = 0x0D08, None
    StopEvent = 0x1511, None
    PauseEvent = 0x1611, None
    ResumeEvent = 0x1711, None
    Duck = 0x1820, None
    Trigger = 0x1D00, None
    TriggerO = 0x1D01, None
    SeekE = 0x1E02, None
    SeekEO = 0x1E03, ActionSeek
    SeekALL = 0x1E04, None
    SeekALLO = 0x1E05, None
    SeekAE = 0x1E08, None
    SeekAEO = 0x1E09, None
    ResetPlaylistE = 0x2202, None
    ResetPlaylistEO = 0x2203, None
    SetGameParameter = 0x1302, ActionSetGameParameter
    SetGameParameterO = 0x1303, None
    ResetGameParameter = 0x1402, None
    ResetGameParameterO = 0x1403, None
    Release = 0x1F02, None
    ReleaseO = 0x1F03, None
    Unk2102 = 0x2102, None
    PlayEvent = 0x2103, str

from __future__ import annotations
from typing import Union, ClassVar
from dataclasses import dataclass, field
from enum import Enum, IntEnum

from .rewwise_enums import ValueMeaning
from .rewwise_base_types import PropBundle, PropRangedModifiers
from .structure import _HIRCNodeBody
from .rewwise_parse import serialize, deserialize


@dataclass
class Action(_HIRCNodeBody):
    body_type: ClassVar[int] = 3
    action_type: int
    external_id: int
    is_bus: int = 0
    prop_bundle: list[PropBundle] = field(default_factory=list)
    ranged_modifiers: PropRangedModifiers = field(default_factory=PropRangedModifiers)
    params: _ActionParams

    def __init__(
        self,

        action_type: SupportedActionType,
        external_id: int,
        is_bus: bool = False,
        **params_kwargs,
    ):
        action_name = ActionTypeId(action_type).name
        if action_name == "Unk2102":
            raise ValueError(f"Action type {action_type} (Unk2102) is not supported")

        if action_name == "PlayEvent":
            params = "PlayEvent"
        else:
            param_cls = SupportedActionType[action_name].value
            params = param_cls(**params_kwargs)

        super().__init__(
            action_type=action_type,
            external_id=external_id,
            is_bus=is_bus,
            params=params,
        )

    @classmethod
    def new_play_action(cls, nid)


@dataclass
class _ActionParams:
    def to_dict(self) -> dict:
        action_name = ActionTypeId(self.action_type).name
        return {action_name: serialize(self)}

    @classmethod
    def from_dict(cls, data: dict) -> "_ActionParams":
        action_name = next(data.keys())
        param_cls = SupportedActionType[action_name].value
        return deserialize(param_cls, data[action_name])


@dataclass
class RandomizerModifier:
    base: float = 0.0
    min: float = 0.0
    max: float = 0.0


@dataclass
class ActionParamsExceptEntry:
    object_id: int
    is_bus: int = 0


@dataclass
class ActionParamsExcept:
    count: int = 0
    exceptions: list[ActionParamsExceptEntry] = field(default_factory=list)


@dataclass
class ActionSetState(_ActionParams):
    state_group_id: int
    target_state_id: int


@dataclass
class ActionSetSwitch(_ActionParams):
    switch_group_id: int
    switch_state_id: int


@dataclass
class ActionSetGameParameterParams:
    bypass_transition: int = 0
    value_meaning: ValueMeaning = ValueMeaning.Default
    randomizer_modifier: RandomizerModifier = field(default_factory=RandomizerModifier)


@dataclass
class ActionSetGameParameter(_ActionParams):
    set_game_parameter: ActionSetGameParameterParams = field(
        default_factory=ActionSetGameParameterParams
    )
    except_: ActionParamsExcept = field(default_factory=ActionParamsExcept)
    flags: int = 0


@dataclass
class ActionMute(_ActionParams):
    fade_curve: int = 0
    except_: ActionParamsExcept = field(default_factory=ActionParamsExcept)


@dataclass
class ActionResume(_ActionParams):
    fade_curve: int = 0
    resume: int = 0
    except_: ActionParamsExcept = field(default_factory=ActionParamsExcept)


@dataclass
class ActionSetAkPropParams:
    value_meaning: ValueMeaning = ValueMeaning.Default
    randomizer_modifier: RandomizerModifier = field(default_factory=RandomizerModifier)


@dataclass
class ActionSetAkProp(_ActionParams):
    set_ak_prop: ActionSetAkPropParams = field(default_factory=ActionSetAkPropParams)
    except_: ActionParamsExcept = field(default_factory=ActionParamsExcept)
    fade_curve: int = 0


@dataclass
class ActionSeekParams:
    is_seek_relative_to_duration: int = 0
    randomizer_modifier: RandomizerModifier = field(default_factory=RandomizerModifier)
    snap_to_nearest_marker: int = 0


@dataclass
class ActionSeek(_ActionParams):
    seek: ActionSeekParams = field(default_factory=ActionSeekParams)
    except_: ActionParamsExcept = field(default_factory=ActionParamsExcept)


@dataclass
class ActionPlay(_ActionParams):
    bank_id: int
    fade_curve: int = 0


@dataclass
class ActionPauseParams:
    flags: int = 0


@dataclass
class ActionPause(_ActionParams):
    pause: ActionPauseParams = field(default_factory=ActionPauseParams)
    except_: ActionParamsExcept = field(default_factory=ActionParamsExcept)
    fade_curve: int = 0


@dataclass
class ActionStopParams:
    # NOTE: unknown, usually 4 and 6, sometimes 7 and 6
    flags1: int = 4
    flags2: int = 6


@dataclass
class ActionStop(_ActionParams):
    stop: ActionStopParams = field(default_factory=ActionStopParams)
    except_: ActionParamsExcept = field(default_factory=ActionParamsExcept)


ActionParams = Union[
    ActionSetState,
    ActionSetSwitch,
    ActionPlay,
    ActionStop,
    ActionPause,
    ActionResume,
    ActionMute,
    ActionSetAkProp,
    ActionSeek,
    ActionSetGameParameter,
]


class ActionTypeId(IntEnum):
    None_ = 0x0000
    SetState = 0x1204
    BypassFXM = 0x1A02
    BypassFXO = 0x1A03
    ResetBypassFXM = 0x1B02
    ResetBypassFXO = 0x1B03
    ResetBypassFXALL = 0x1B04
    ResetBypassFXALLO = 0x1B05
    ResetBypassFXAE = 0x1B08
    ResetBypassFXAEO = 0x1B09
    SetSwitch = 0x1901
    UseStateE = 0x1002
    UnuseStateE = 0x1102
    Play = 0x0403
    PlayAndContinue = 0x0503
    StopE = 0x0102
    StopEO = 0x0103
    StopALL = 0x0104
    StopALLO = 0x0105
    StlopAE = 0x0108
    StopAEO = 0x0109
    PauseE = 0x0202
    PauseEO = 0x0203
    PauseALL = 0x0204
    PauseALLO = 0x0205
    PauseAE = 0x0208
    PauseAEO = 0x0209
    ResumeE = 0x0302
    ResumeEO = 0x0303
    ResumeALL = 0x0304
    ResumeALLO = 0x0305
    ResumeAE = 0x0308
    ResumeAEO = 0x0309
    BreakE = 0x1C02
    BreakEO = 0x1C03
    MuteM = 0x0602
    MuteO = 0x0603
    UnmuteM = 0x0702
    UnmuteO = 0x0703
    UnmuteALL = 0x0704
    UnmuteALLO = 0x0705
    UnmuteAE = 0x0708
    UnmuteAEO = 0x0709
    SetVolumeM = 0x0A02
    SetVolumeO = 0x0A03
    ResetVolumeM = 0x0B02
    ResetVolumeO = 0x0B03
    ResetVolumeALL = 0x0B04
    ResetVolumeALLO = 0x0B05
    ResetVolumeAE = 0x0B08
    ResetVolumeAEO = 0x0B09
    SetPitchM = 0x0802
    SetPitchO = 0x0803
    ResetPitchM = 0x0902
    ResetPitchO = 0x0903
    ResetPitchALL = 0x0904
    ResetPitchALLO = 0x0905
    ResetPitchAE = 0x0908
    ResetPitchAEO = 0x0909
    SetLPFM = 0x0E02
    SetLPFO = 0x0E03
    ResetLPFM = 0x0F02
    ResetLPFO = 0x0F03
    ResetLPFALL = 0x0F04
    ResetLPFALLO = 0x0F05
    ResetLPFAE = 0x0F08
    ResetLPFAEO = 0x0F09
    SetHPFM = 0x2002
    SetHPFO = 0x2003
    ResetHPFM = 0x3002
    ResetHPFO = 0x3003
    ResetHPFALL = 0x3004
    ResetHPFALLO = 0x3005
    ResetHPFAE = 0x3008
    ResetHPFAEO = 0x3009
    SetBusVolumeM = 0x0C02
    SetBusVolumeO = 0x0C03
    ResetBusVolumeM = 0x0D02
    ResetBusVolumeO = 0x0D03
    ResetBusVolumeALL = 0x0D04
    ResetBusVolumeAE = 0x0D08
    StopEvent = 0x1511
    PauseEvent = 0x1611
    ResumeEvent = 0x1711
    Duck = 0x1820
    Trigger = 0x1D00
    TriggerO = 0x1D01
    SeekE = 0x1E02
    SeekEO = 0x1E03
    SeekALL = 0x1E04
    SeekALLO = 0x1E05
    SeekAE = 0x1E08
    SeekAEO = 0x1E09
    ResetPlaylistE = 0x2202
    ResetPlaylistEO = 0x2203
    SetGameParameter = 0x1302
    SetGameParameterO = 0x1303
    ResetGameParameter = 0x1402
    ResetGameParameterO = 0x1403
    Release = 0x1F02
    ReleaseO = 0x1F03
    Unk2102 = 0x2102
    PlayEvent = 0x2103


# NOTE: Includes only the ones we actually support
class SupportedActionType(Enum):
    SetState = ActionSetSwitch
    SetSwitch = ActionSetSwitch
    Play = ActionPlay
    StopE = ActionStop
    StopEO = ActionStop
    PauseE = ActionPause
    ResumeE = ActionResume
    MuteM = ActionMute
    MuteO = ActionMute
    UnmuteM = ActionMute
    UnmuteO = ActionMute
    UnmuteALL = ActionMute
    UnmuteALLO = ActionMute
    UnmuteAE = ActionMute
    UnmuteAEO = ActionMute
    SetVolumeM = ActionSetAkProp
    SetVolumeO = ActionSetAkProp
    ResetVolumeM = ActionSetAkProp
    ResetVolumeO = ActionSetAkProp
    ResetVolumeALL = ActionSetAkProp
    SetPitchM = ActionSetAkProp
    SetPitchO = ActionSetAkProp
    ResetPitchM = ActionSetAkProp
    ResetPitchO = ActionSetAkProp
    ResetPitchALL = ActionSetAkProp
    ResetPitchALLO = ActionSetAkProp
    ResetPitchAE = ActionSetAkProp
    ResetPitchAEO = ActionSetAkProp
    SetLPFM = ActionSetAkProp
    SetLPFO = ActionSetAkProp
    ResetLPFM = ActionSetAkProp
    ResetLPFO = ActionSetAkProp
    ResetLPFALL = ActionSetAkProp
    SetHPFM = ActionSetAkProp
    SetHPFO = ActionSetAkProp
    ResetHPFM = ActionSetAkProp
    ResetHPFALL = ActionSetAkProp
    SetBusVolumeM = ActionSetAkProp
    ResetBusVolumeM = ActionSetAkProp
    ResetBusVolumeALL = ActionSetAkProp
    SeekEO = ActionSeek
    SetGameParameter = ActionSetGameParameter
    Unk2102 = None
    PlayEvent = str

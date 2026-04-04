from __future__ import annotations
from typing import Union
from dataclasses import dataclass, field

from .rewwise_enums import AkValueMeaning
from .rewwise_parse import serialize, deserialize


@dataclass
class _ActionParams:
    def to_dict(self) -> dict:
        action_name = ACTION_PARAM_IDS[self.action_type]
        return {action_name: serialize(self)}

    @classmethod
    def from_dict(cls, data: dict) -> "_ActionParams":
        action_name = next(data.keys())
        param_cls = ACTION_PARAM_TYPES[action_name]
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
class ActionSetState:
    state_group_id: int
    target_state_id: int


@dataclass
class ActionSetSwitch:
    switch_group_id: int
    switch_state_id: int


@dataclass
class ActionSetGameParameterParams:
    bypass_transition: int = 0
    value_meaning: AkValueMeaning = AkValueMeaning.Default
    randomizer_modifier: RandomizerModifier = field(default_factory=RandomizerModifier)


@dataclass
class ActionSetGameParameter:
    set_game_parameter: ActionSetGameParameterParams = field(
        default_factory=ActionSetGameParameterParams
    )
    except_: ActionParamsExcept = field(default_factory=ActionParamsExcept)
    flags: int = 0


@dataclass
class ActionMute:
    fade_curve: int = 0
    except_: ActionParamsExcept = field(default_factory=ActionParamsExcept)


@dataclass
class ActionResume:
    fade_curve: int = 0
    resume: int = 0
    except_: ActionParamsExcept = field(default_factory=ActionParamsExcept)


@dataclass
class ActionSetAkPropParams:
    value_meaning: AkValueMeaning = AkValueMeaning.Default
    randomizer_modifier: RandomizerModifier = field(default_factory=RandomizerModifier)


@dataclass
class ActionSetAkProp:
    set_ak_prop: ActionSetAkPropParams = field(default_factory=ActionSetAkPropParams)
    except_: ActionParamsExcept = field(default_factory=ActionParamsExcept)
    fade_curve: int = 0


@dataclass
class ActionSeekParams:
    is_seek_relative_to_duration: int = 0
    randomizer_modifier: RandomizerModifier = field(default_factory=RandomizerModifier)
    snap_to_nearest_marker: int = 0


@dataclass
class ActionSeek:
    seek: ActionSeekParams = field(default_factory=ActionSeekParams)
    except_: ActionParamsExcept = field(default_factory=ActionParamsExcept)


@dataclass
class ActionPlay:
    bank_id: int
    fade_curve: int = 0


@dataclass
class ActionPauseParams:
    flags: int = 0


@dataclass
class ActionPause:
    pause: ActionPauseParams = field(default_factory=ActionPauseParams)
    except_: ActionParamsExcept = field(default_factory=ActionParamsExcept)
    fade_curve: int = 0


@dataclass
class ActionStopParams:
    flags1: int = 0
    flags2: int = 0


@dataclass
class ActionStop:
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


ACTION_PARAM_IDS = {
    0x0000: "None_",
    0x1204: "SetState",
    0x1A02: "BypassFXM",
    0x1A03: "BypassFXO",
    0x1B02: "ResetBypassFXM",
    0x1B03: "ResetBypassFXO",
    0x1B04: "ResetBypassFXALL",
    0x1B05: "ResetBypassFXALLO",
    0x1B08: "ResetBypassFXAE",
    0x1B09: "ResetBypassFXAEO",
    0x1901: "SetSwitch",
    0x1002: "UseStateE",
    0x1102: "UnuseStateE",
    0x0403: "Play",
    0x0503: "PlayAndContinue",
    0x0102: "StopE",
    0x0103: "StopEO",
    0x0104: "StopALL",
    0x0105: "StopALLO",
    0x0108: "StlopAE",
    0x0109: "StopAEO",
    0x0202: "PauseE",
    0x0203: "PauseEO",
    0x0204: "PauseALL",
    0x0205: "PauseALLO",
    0x0208: "PauseAE",
    0x0209: "PauseAEO",
    0x0302: "ResumeE",
    0x0303: "ResumeEO",
    0x0304: "ResumeALL",
    0x0305: "ResumeALLO",
    0x0308: "ResumeAE",
    0x0309: "ResumeAEO",
    0x1C02: "BreakE",
    0x1C03: "BreakEO",
    0x0602: "MuteM",
    0x0603: "MuteO",
    0x0702: "UnmuteM",
    0x0703: "UnmuteO",
    0x0704: "UnmuteALL",
    0x0705: "UnmuteALLO",
    0x0708: "UnmuteAE",
    0x0709: "UnmuteAEO",
    0x0A02: "SetVolumeM",
    0x0A03: "SetVolumeO",
    0x0B02: "ResetVolumeM",
    0x0B03: "ResetVolumeO",
    0x0B04: "ResetVolumeALL",
    0x0B05: "ResetVolumeALLO",
    0x0B08: "ResetVolumeAE",
    0x0B09: "ResetVolumeAEO",
    0x0802: "SetPitchM",
    0x0803: "SetPitchO",
    0x0902: "ResetPitchM",
    0x0903: "ResetPitchO",
    0x0904: "ResetPitchALL",
    0x0905: "ResetPitchALLO",
    0x0908: "ResetPitchAE",
    0x0909: "ResetPitchAEO",
    0x0E02: "SetLPFM",
    0x0E03: "SetLPFO",
    0x0F02: "ResetLPFM",
    0x0F03: "ResetLPFO",
    0x0F04: "ResetLPFALL",
    0x0F05: "ResetLPFALLO",
    0x0F08: "ResetLPFAE",
    0x0F09: "ResetLPFAEO",
    0x2002: "SetHPFM",
    0x2003: "SetHPFO",
    0x3002: "ResetHPFM",
    0x3003: "ResetHPFO",
    0x3004: "ResetHPFALL",
    0x3005: "ResetHPFALLO",
    0x3008: "ResetHPFAE",
    0x3009: "ResetHPFAEO",
    0x0C02: "SetBusVolumeM",
    0x0C03: "SetBusVolumeO",
    0x0D02: "ResetBusVolumeM",
    0x0D03: "ResetBusVolumeO",
    0x0D04: "ResetBusVolumeALL",
    0x0D08: "ResetBusVolumeAE",
    0x1511: "StopEvent",
    0x1611: "PauseEvent",
    0x1711: "ResumeEvent",
    0x1820: "Duck",
    0x1D00: "Trigger",
    0x1D01: "TriggerO",
    0x1E02: "SeekE",
    0x1E03: "SeekEO",
    0x1E04: "SeekALL",
    0x1E05: "SeekALLO",
    0x1E08: "SeekAE",
    0x1E09: "SeekAEO",
    0x2202: "ResetPlaylistE",
    0x2203: "ResetPlaylistEO",
    0x1302: "SetGameParameter",
    0x1303: "SetGameParameterO",
    0x1402: "ResetGameParameter",
    0x1403: "ResetGameParameterO",
    0x1F02: "Release",
    0x1F03: "ReleaseO",
    0x2102: "Unk2102",
    0x2103: "PlayEvent",
}

ACTION_PARAM_TYPES = {
    "SetState": ActionSetSwitch,
    "SetSwitch": ActionSetSwitch,
    "Play": ActionPlay,
    "StopE": ActionStop,
    "StopEO": ActionStop,
    "PauseE": ActionPause,
    "ResumeE": ActionResume,
    "MuteM": ActionMute,
    "MuteO": ActionMute,
    "UnmuteM": ActionMute,
    "UnmuteO": ActionMute,
    "UnmuteALL": ActionMute,
    "UnmuteALLO": ActionMute,
    "UnmuteAE": ActionMute,
    "UnmuteAEO": ActionMute,
    "SetVolumeM": ActionSetAkProp,
    "SetVolumeO": ActionSetAkProp,
    "ResetVolumeM": ActionSetAkProp,
    "ResetVolumeO": ActionSetAkProp,
    "ResetVolumeALL": ActionSetAkProp,
    "SetPitchM": ActionSetAkProp,
    "SetPitchO": ActionSetAkProp,
    "ResetPitchM": ActionSetAkProp,
    "ResetPitchO": ActionSetAkProp,
    "ResetPitchALL": ActionSetAkProp,
    "ResetPitchALLO": ActionSetAkProp,
    "ResetPitchAE": ActionSetAkProp,
    "ResetPitchAEO": ActionSetAkProp,
    "SetLPFM": ActionSetAkProp,
    "SetLPFO": ActionSetAkProp,
    "ResetLPFM": ActionSetAkProp,
    "ResetLPFO": ActionSetAkProp,
    "ResetLPFALL": ActionSetAkProp,
    "SetHPFM": ActionSetAkProp,
    "SetHPFO": ActionSetAkProp,
    "ResetHPFM": ActionSetAkProp,
    "ResetHPFALL": ActionSetAkProp,
    "SetBusVolumeM": ActionSetAkProp,
    "ResetBusVolumeM": ActionSetAkProp,
    "ResetBusVolumeALL": ActionSetAkProp,
    "SeekEO": ActionSeek,
    "SetGameParameter": ActionSetGameParameter,
    "Unk2102": None,
    "PlayEvent": str,
}

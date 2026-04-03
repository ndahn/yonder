from __future__ import annotations
from typing import Union
from dataclasses import dataclass, field

from .rewwise_enums import AkValueMeaning


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
class ActionSetGameParameter:
    @dataclass
    class Params:
        bypass_transition: int = 0
        value_meaning: AkValueMeaning = AkValueMeaning.Default
        randomizer_modifier: RandomizerModifier = field(
            default_factory=RandomizerModifier
        )

    set_game_parameter: Params = field(default_factory=Params)
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
class ActionSetAkProp:
    @dataclass
    class Params:
        value_meaning: AkValueMeaning = AkValueMeaning.Default
        randomizer_modifier: RandomizerModifier = field(
            default_factory=RandomizerModifier
        )

    set_ak_prop: Params = field(default_factory=Params)
    except_: ActionParamsExcept = field(default_factory=ActionParamsExcept)
    fade_curve: int = 0


@dataclass
class ActionSeek:
    @dataclass
    class Params:
        is_seek_relative_to_duration: int = 0
        randomizer_modifier: RandomizerModifier = field(
            default_factory=RandomizerModifier
        )
        snap_to_nearest_marker: int = 0

    seek: Params = field(default_factory=Params)
    except_: ActionParamsExcept = field(default_factory=ActionParamsExcept)


@dataclass
class ActionPlay:
    bank_id: int
    fade_curve: int = 0


@dataclass
class ActionPause:
    @dataclass
    class Params:
        flags: int = 0

    pause: Params = field(default_factory=Params)
    except_: ActionParamsExcept = field(default_factory=ActionParamsExcept)
    fade_curve: int = 0


@dataclass
class ActionStop:
    @dataclass
    class Params:
        flags1: int = 0
        flags2: int = 0

    stop: Params = field(default_factory=Params)
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


ACTION_TYPE_MAP: dict[int, type] = {
    0x1204: ActionSetState,
    0x1901: ActionSetSwitch,
    0x0403: ActionPlay,
    0x0102: ActionStop,
    0x0103: ActionStop,
    0x0202: ActionPause,
    0x0302: ActionResume,
    0x0602: ActionMute,
    0x0603: ActionMute,
    0x0702: ActionMute,
    0x0703: ActionMute,
    0x0704: ActionMute,
    0x0705: ActionMute,
    0x0708: ActionMute,
    0x0709: ActionMute,
    0x0A02: ActionSetAkProp,
    0x0A03: ActionSetAkProp,
    0x0B02: ActionSetAkProp,
    0x0B03: ActionSetAkProp,
    0x0B04: ActionSetAkProp,
    0x0802: ActionSetAkProp,
    0x0803: ActionSetAkProp,
    0x0902: ActionSetAkProp,
    0x0903: ActionSetAkProp,
    0x0904: ActionSetAkProp,
    0x0905: ActionSetAkProp,
    0x0908: ActionSetAkProp,
    0x0909: ActionSetAkProp,
    0x0E02: ActionSetAkProp,
    0x0E03: ActionSetAkProp,
    0x0F02: ActionSetAkProp,
    0x0F03: ActionSetAkProp,
    0x0F04: ActionSetAkProp,
    0x2002: ActionSetAkProp,
    0x2003: ActionSetAkProp,
    0x3002: ActionSetAkProp,
    0x3004: ActionSetAkProp,
    0x0C02: ActionSetAkProp,
    0x0D02: ActionSetAkProp,
    0x0D04: ActionSetAkProp,
    0x1E03: ActionSeek,
    0x1302: ActionSetGameParameter,
    0x2102: ActionStop,  # Unk2102
    0x2103: str,  # PlayEvent
}
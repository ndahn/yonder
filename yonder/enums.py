from typing import Literal, TypeAlias
from enum import StrEnum, IntFlag


class SoundType(StrEnum):
    ENVIRONMENT = "a"
    CHARACTER = "c"
    MENU = "f"
    OBJECT = "o"
    CUTSCENE_SE = "p"
    SFX = "s"
    BGM = "m"
    VOICE = "v"
    FLOOR_MATERIAL_DETERMINED = "x"
    ARMOR_MATERIAL_DETERMINED = "b"
    PHANTOM = "i"
    MULTI_CHANNEL_STREAMING = "y"
    MATERIAL_RELATED = "z"
    FOOT_EFFECT = "e"
    GEOMETRY_ASSET = "g"
    DYNAMIC_DIALOG = "d"

    @classmethod
    def values(cls) -> str:
        return "".join(s.value for s in cls)


# Not a flag, just a convenient way to map the known types
class ActionType(IntFlag):
    PLAY = 1027
    STOP = 259
    MUTE_BUS = 1538
    RESET_BUS_VOLUME = 2818
    RESET_BUS_LPFM = 3842


RtpcType: TypeAlias = Literal["GameParameter"]
AccumulationType: TypeAlias = Literal["Additive"]
ScalingType: TypeAlias = Literal["DB", "Linear", "None"]
CurveType: TypeAlias = Literal[
    "Constant",
    "Linear",
    "SCurve",
    "InvSCurve",
    "Log1",
    "Log2",
    "Log3",
    "Exp1",
    "Exp2",
    "Exp3",
    "Sine",
]
ClipType: TypeAlias = Literal["FadeIn", "FadeOut", "Volume", "HPF", "LPF"]
SyncType: TypeAlias = Literal["Immediate", "NextGrid", "NextBar", "ExitCue"]
SourceType: TypeAlias = Literal["Embedded", "Streaming", "PrefetchStreaming"]
PluginType: TypeAlias = Literal["VORBIS", "PCM"]
VirtualQueueBehavior: TypeAlias = Literal[
    "Resume", "PlayFromElapsedTime", "PlayFromBeginning"
]


property_defaults = {
    "Volume": -3.0,
    "PriorityDistanceOffset": -49.0,
    "UserAuxSendVolume0": -96.0,
    "UserAuxSendVolume1": -96.0,
    "UserAuxSendVolume2": -96.0,
    "UserAuxSendVolume3": -96.0,
    "GameAuxSendVolume": -6.0,
    "CenterPCT": 50.0,
    "AttenuationID": 0,
    "Priority": 20.0,
    "LPF": 20.0,
    "HPF": 35.0,
    "Pitch": -500.0,
}

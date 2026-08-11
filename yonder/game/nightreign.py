from .game import Game, GameObjects, EnumWithUnknown
from .collectors.actormixer_summary import load_actormixer_summary
from .collectors.gamestate_summary import load_gamestate_summary


# Presumably the same as in ER?
class RTPCParameter_Nightreign(EnumWithUnknown):
    UNKNOWN = -1
    Volume = 0
    # ADDITIVE_PARAMS_START
    LFE = 1
    Pitch = 2
    LPF = 3
    HPF = 4
    BusVolume = 5
    InitialDelay = 6
    MakeUpGain = 7
    Deprecated_RTPC_FeedbackVolume = 8
    Deprecated_RTPC_FeedbackLowpass = 9
    Deprecated_RTPC_FeedbackPitch = 10
    MidiTransposition = 11
    MidiVelocityOffset = 12
    PlaybackSpeed = 13
    MuteRatio = 14
    PlayMechanismSpecialTransitionsValue = 15
    MaxNumInstances = 16
    # OVERRIDABLE_PARAMS_START
    Priority = 17
    Position_PAN_X_2D = 18
    Position_PAN_Y_2D = 19
    Position_PAN_X_3D = 20
    Position_PAN_Y_3D = 21
    Position_PAN_Z_3D = 22
    PositioningTypeBlend = 23
    Positioning_Divergence_Center_PCT = 24
    Positioning_Cone_Attenuation_ON_OFF = 25
    Positioning_Cone_Attenuation = 26
    Positioning_Cone_LPF = 27
    Positioning_Cone_HPF = 28
    BypassFX0 = 29
    BypassFX1 = 30
    BypassFX2 = 31
    BypassFX3 = 32
    BypassAllFX = 33
    HDRBusThreshold = 34
    HDRBusReleaseTime = 35
    HDRBusRatio = 36
    HDRActiveRange = 37
    GameAuxSendVolume = 38
    UserAuxSendVolume0 = 39
    UserAuxSendVolume1 = 40
    UserAuxSendVolume2 = 41
    UserAuxSendVolume3 = 42
    OutputBusVolume = 43
    OutputBusHPF = 44
    OutputBusLPF = 45
    Positioning_EnableAttenuation = 46
    ReflectionsVolume = 47
    UserAuxSendLPF0 = 48
    UserAuxSendLPF1 = 49
    UserAuxSendLPF2 = 50
    UserAuxSendLPF3 = 51
    UserAuxSendHPF0 = 52
    UserAuxSendHPF1 = 53
    UserAuxSendHPF2 = 54
    UserAuxSendHPF3 = 55
    GameAuxSendLPF = 56
    GameAuxSendHPF = 57
    Position_PAN_Z_2D = 58
    BypassAllMetadata = 59
    MaxNumRTPC = 58


class GameNightreign(GameObjects):
    game = Game.Nightreign
    regbin_key = bytes.fromhex(
        "9a8ee90c4c01a43168a17d9d75e4a7d02107ebcf43d5acb0554f941601b57918"
    )
    rtpc_params = RTPCParameter_Nightreign
    game_states = load_gamestate_summary(Game.Nightreign)
    amx_summary = load_actormixer_summary(Game.Nightreign)

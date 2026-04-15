from enum import IntEnum


class Game(IntEnum):
    EldenRing = 0
    Nightreign = 1


class RTPCParameter_EldenRing(IntEnum):
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
    MaxNumRTPC = 58

    @classmethod
    def _missing_(cls, value: int):
        if not isinstance(value, int):
            raise ValueError(f"{value} is not a valid {cls.__name__} value")

        tmp = int.__new__(cls, value)
        tmp._name_ = cls.UNKNOWN.name
        tmp._value_ = value
        return tmp

    def __eq__(self, other) -> bool:
        if isinstance(other, type(self)) and self.name == self.UNKNOWN.name:
            return other.name == self.UNKNOWN.name
        return super().__eq__(other)


class GameObjects:
    selected_game: Game = Game.EldenRing
    RTPCParameter = RTPCParameter_EldenRing

    @classmethod
    def set_game(cls, game: Game) -> None:
        from yonder.util import logger

        cls.selected_game = game
        
        if game == Game.EldenRing:
            cls.RTPCParameter = RTPCParameter_EldenRing
        else:
            logger.warning(
                f"Game {game} is not supported yet, using EldenRing settings"
            )
            cls.set_game(Game.EldenRing)

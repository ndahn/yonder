from __future__ import annotations
from enum import IntEnum, StrEnum


class EnumWithUnknown(IntEnum):
    @classmethod
    def _missing_(cls, value: int):
        if not isinstance(value, int):
            raise TypeError(f"{value} is not a valid {cls.__name__} value")

        tmp = int.__new__(cls, value)
        tmp._name_ = "UNKNOWN"
        tmp._value_ = value
        return tmp

    def __eq__(self, other) -> bool:
        if isinstance(other, type(self)) and self.name == "UNKNOWN":
            return other.name == "UNKNOWN"
        return super().__eq__(other)


class Game(IntEnum):
    EldenRing = 0
    Nightreign = 1
    # ArmoredCore6 = 2


class SoundType(StrEnum):
    Environment = "a"
    Character = "c"
    Menu = "f"
    Object = "o"
    CutsceneSe = "p"
    Sfx = "s"
    Bgm = "m"
    Voice = "v"
    FloorMaterialDetermined = "x"
    ArmorMaterialDetermined = "b"
    Phantom = "i"
    MultiChannelStreaming = "y"
    MaterialRelated = "z"
    FootEffect = "e"
    GeometryAsset = "g"
    DynamicDialog = "d"

    @classmethod
    def values(cls) -> str:
        return "".join(s.value for s in cls)

    def __str__(self) -> str:
        return f"{self.name} ({self.value})"


class ActionType(IntEnum):
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


class CurveInterpolation(IntEnum):
    Log3 = 0x0
    Sine = 0x1
    Log1 = 0x2
    InvSCurve = 0x3
    Linear = 0x4
    SCurve = 0x5
    Exp1 = 0x6
    SineRecip = 0x7
    Exp3 = 0x8
    Constant = 0x9


class CurveScaling(IntEnum):
    None_ = 0x0
    DB = 0x2
    Log = 0x3
    DBToLin = 0x4


# NOTE quite different in more recent versions of wwise, but ER and NR are using 2019.2 (v135)
class AttenuationProperty(IntEnum):
    Volume = 0
    AuxSendGame = 1
    AuxSendUser = 2
    LPF = 3
    HPF = 4
    Spread = 5
    Focus = 6


# NOTE Unused for now, more meant for documentation purposes
class AttenuationDrivers(IntEnum):
    Distance = 0
    Obstruction = 1
    Occlusion = 2
    Diffraction = 3
    Transmission = 4


class RandomMode(IntEnum):
    Standard = 0
    Shuffle = 1


class RandomSequenceMode(IntEnum):
    ContinuousSequence = 0
    StepSequence = 1
    ContinuousRandom = 2
    StepRandom = 3
    Inherit = 0xFFFFFFFF


class PlaybackMode(IntEnum):
    Random = 0
    Sequence = 1


class MusicTrackType(EnumWithUnknown):
    Normal = 0
    # Expected to also contain the following modes:
    # - RandomStep
    # - SequenceStep
    # - Switch


class PropID(IntEnum):
    Volume = 0x00
    LFE = 0x01
    Pitch = 0x02
    LPF = 0x03
    HPF = 0x04
    BusVolume = 0x05
    MakeUpGain = 0x06
    Priority = 0x07
    PriorityDistanceOffset = 0x08
    MuteRatio = 0x0B
    PanLR = 0x0C
    PanFR = 0x0D
    CenterPCT = 0x0E
    DelayTime = 0x0F
    TransitionTime = 0x10
    Probability = 0x11
    DialogueMode = 0x12
    UserAuxSendVolume0 = 0x13
    UserAuxSendVolume1 = 0x14
    UserAuxSendVolume2 = 0x15
    UserAuxSendVolume3 = 0x16
    GameAuxSendVolume = 0x17
    OutputBusVolume = 0x18
    OutputBusHPF = 0x19
    OutputBusLPF = 0x1A
    HDRBusThreshold = 0x1B
    HDRBusRatio = 0x1C
    HDRBusReleaseTime = 0x1D
    HDRBusGameParam = 0x1E
    HDRBusGameParamMin = 0x1F
    HDRBusGameParamMax = 0x20
    HDRActiveRange = 0x21
    LoopStart = 0x22
    LoopEnd = 0x23
    TrimInTime = 0x24
    TrimOutTime = 0x25
    FadeInTime = 0x26
    FadeOutTime = 0x27
    FadeInCurve = 0x28
    FadeOutCurve = 0x29
    LoopCrossfadeDuration = 0x2A
    CrossfadeUpCurve = 0x2B
    CrossfadeDownCurve = 0x2C
    MidiTrackingRootNote = 0x2D
    MidiPlayOnNoteType = 0x2E
    MidiTransposition = 0x2F
    MidiVelocityOffset = 0x30
    MidiKeyRangeMin = 0x31
    MidiKeyRangeMax = 0x32
    MidiVelocityRangeMin = 0x33
    MidiVelocityRangeMax = 0x34
    MidiChannelMask = 0x35
    PlaybackSpeed = 0x36
    MidiTempoSource = 0x37
    MidiTargetNode = 0x38
    AttachedPluginFXID = 0x39
    Loop = 0x3A
    InitialDelay = 0x3B
    UserAuxSendLPF0 = 0x3C
    UserAuxSendLPF1 = 0x3D
    UserAuxSendLPF2 = 0x3E
    UserAuxSendLPF3 = 0x3F
    UserAuxSendHPF0 = 0x40
    UserAuxSendHPF1 = 0x41
    UserAuxSendHPF2 = 0x42
    UserAuxSendHPF3 = 0x43
    GameAuxSendLPF = 0x44
    GameAuxSendHPF = 0x45
    AttenuationID = 0x46
    PositioningTypeBlend = 0x47
    ReflectionBusVolume = 0x48

    def is_accumulating(self) -> bool:
        return self in (
            PropID.LFE,
            PropID.Pitch,
            PropID.LPF,
            PropID.HPF,
            PropID.BusVolume,
            PropID.InitialDelay,
            PropID.MakeUpGain,
            PropID.MidiTransposition,
            PropID.MidiVelocityOffset,
            PropID.PlaybackSpeed,
            PropID.MuteRatio,
        )


# TODO these should be used by the TimeModulator instead of PropID
class ModulatorPropID(IntEnum):
    Scope: 0x0
    EnvelopeStopPlayback: 0x1
    LFODepth: 0x2
    LFOAttack: 0x3
    LFOFrequency: 0x4
    LFOWaveform: 0x5
    LFOSmoothing: 0x6
    LFOPWM: 0x7
    LFOInitialPhase: 0x8
    LFORetrigger: 0x9
    EnvelopeAttackTime: 0xA
    EnvelopeAttackCurve: 0xB
    EnvelopeDecayTime: 0xC
    EnvelopeSustainLevel: 0xD
    EnvelopeSustainTime: 0xE
    EnvelopeReleaseTime: 0xF
    EnvelopeTriggerOn: 0x10
    TimeDuration: 0x11
    TimeLoops: 0x12
    TimePlaybackRate: 0x13
    TimeInitialDelay: 0x14


class ParameterID(IntEnum):
    Volume = 0x0
    LFE = 0x1
    Pitch = 0x2
    LPF = 0x3
    HPF = 0x4
    BusVolume = 0x5
    InitialDelay = 0x6
    MakeUpGain = 0x7
    DeprecatedFeedbackVolume = 0x8
    DeprecatedFeedbackLowpass = 0x9
    DeprecatedFeedbackPitch = 0xA
    MidiTransposition = 0xB
    MidiVelocityOffset = 0xC
    PlaybackSpeed = 0xD
    MuteRatio = 0xE
    PlayMechanismSpecialTransitionsValue = 0xF
    MaxNumInstances = 0x10
    Priority = 0x11
    PositionPANX2D = 0x12
    PositionPANY2D = 0x13
    PositionPANX3D = 0x14
    PositionPANY3D = 0x15
    PositionPANZ3D = 0x16
    PositioningTypeBlend = 0x17
    PositioningDivergenceCenterPCT = 0x18
    PositioningConeAttenuationONOFF = 0x19
    PositioningConeAttenuation = 0x1A
    PositioningConeLPF = 0x1B
    PositioningConeHPF = 0x1C
    BypassFX0 = 0x1D
    BypassFX1 = 0x1E
    BypassFX2 = 0x1F
    BypassFX3 = 0x20
    BypassAllFX = 0x21
    HDRBusThreshold = 0x22
    HDRBusReleaseTime = 0x23
    HDRBusRatio = 0x24
    HDRActiveRange = 0x25
    GameAuxSendVolume = 0x26
    UserAuxSendVolume0 = 0x27
    UserAuxSendVolume1 = 0x28
    UserAuxSendVolume2 = 0x29
    UserAuxSendVolume3 = 0x2A
    OutputBusVolume = 0x2B
    OutputBusHPF = 0x2C
    OutputBusLPF = 0x2D
    PositioningEnableAttenuation = 0x2E
    ReflectionsVolume = 0x2F
    UserAuxSendLPF0 = 0x30
    UserAuxSendLPF1 = 0x31
    UserAuxSendLPF2 = 0x32
    UserAuxSendLPF3 = 0x33
    UserAuxSendHPF0 = 0x34
    UserAuxSendHPF1 = 0x35
    UserAuxSendHPF2 = 0x36
    UserAuxSendHPF3 = 0x37
    GameAuxSendLPF = 0x38
    GameAuxSendHPF = 0x39
    PositionPANZ2D = 0x3A
    BypassAllMetadata = 0x3B
    MaxNumRTPC = 0x3C
    Custom1 = 0x3D
    Custom2 = 0x3E
    Custom3 = 0x3F
    Custom4 = 0x40
    Custom5 = 0x41


class ValueMeaning(IntEnum):
    Default = 0x0
    Independent = 0x1
    Offset = 0x2


class PathMode(IntEnum):
    StepSequence = 0x0
    StepRandom = 0x1
    ContinuousSequence = 0x2
    ContinuousRandom = 0x3
    StepSequencePickNewPath = 0x4
    StepRandomPickNewPath = 0x5


class ThreeDSpatializationMode(IntEnum):
    None_ = 0x0
    PositionOnly = 0x1
    PositionAndOrientation = 0x2


class SpeakerPanningType(IntEnum):
    DirectSpeakerAssignment = 0x0
    BalanceFadeHeight = 0x1
    SteeringPanner = 0x2


class ThreeDPositionType(IntEnum):
    Emitter = 0x0
    EmitterWithAutomation = 0x1
    ListenerWithAutomation = 0x2


class VirtualQueueBehavior(IntEnum):
    PlayFromBeginning = 0x0
    PlayFromElapsedTime = 0x1
    Resume = 0x2


class BelowThresholdBehavior(IntEnum):
    ContinueToPlay = 0x0
    KillVoice = 0x1
    SetAsVirtualVoice = 0x2
    KillIfOneShotElseVirtual = 0x3


class SyncType(IntEnum):
    Immediate = 0x0
    NextGrid = 0x1
    NextBar = 0x2
    NextBeat = 0x3
    NextMarket = 0x4
    NextUserMarker = 0x5
    EntryMarker = 0x6
    ExitMarker = 0x7
    ExitNever = 0x8
    LastExitPosition = 0x9


class RtpcAccum(IntEnum):
    None_ = 0x0
    Exclusive = 0x1
    Additive = 0x2
    Multiply = 0x3
    Boolean = 0x4
    Maximum = 0x5
    Filter = 0x6


class RtpcType(IntEnum):
    GameParameter = 0x0
    MIDIParameter = 0x1
    Modulator = 0x2


class GroupType(IntEnum):
    Switch = 0x0
    """Specific to individual objects"""

    State = 0x1
    """Global, seen by all objects"""


class DecisionTreeMode(IntEnum):
    BestMatch = 0x0
    Weighted = 0x1


class ClipAutomationType(IntEnum):
    Volume = 0x00
    LPF = 0x01
    HPF = 0x02
    FadeIn = 0x03
    FadeOut = 0x04


class SourceType(IntEnum):
    Embedded = 0x0
    PrefetchStreaming = 0x1
    Streaming = 0x2


class EffectPlugin(IntEnum):
    None_ = 0x00000000
    BANK = 0x00000001
    PCM = 0x00010001
    ADPCM = 0x00020001
    XMA = 0x00030001
    VORBIS = 0x00040001
    WIIADPCM = 0x00050001
    PCMEX = 0x00070001
    EXTERNALSOURCE = 0x00080001
    XWMA = 0x00090001
    AAC = 0x000A0001
    FILEPACKAGE = 0x000B0001
    ATRAC9 = 0x000C0001
    VAGHEVAG = 0x000D0001
    PROFILERCAPTURE = 0x000E0001
    ANALYSISFILE = 0x000F0001
    MIDI = 0x00100001
    OPUSNX = 0x00110001
    CAF = 0x00120001
    OPUS = 0x00130001
    OPUSWEM1 = 0x00140001
    OPUSWEM2 = 0x00150001
    SONY360 = 0x00160001
    WwiseSine = 0x00640002
    WwiseSilence = 0x00650002
    WwiseToneGenerator = 0x00660002
    WwiseUnk1 = 0x00670003
    WwiseUnk2 = 0x00680003
    WwiseParametricEQ = 0x00690003
    WwiseDelay = 0x006A0003
    WwiseCompressor = 0x006C0003
    WwiseExpander = 0x006D0003
    WwisePeakLimiter = 0x006E0003
    WwiseUnk3 = 0x006F0003
    WwiseUnk4 = 0x00700003
    WwiseMatrixReverb = 0x00730003
    SoundSeedImpact = 0x00740003
    WwiseRoomVerb = 0x00760003
    SoundSeedAirWind = 0x00770002
    SoundSeedAirWoosh = 0x00780002
    WwiseFlanger = 0x007D0003
    WwiseGuitarDistortion = 0x007E0003
    WwiseConvolutionReverb = 0x007F0003
    WwiseMeter = 0x00810003
    WwiseTimeStretch = 0x00820003
    WwiseTremolo = 0x00830003
    WwiseRecorder = 0x00840003
    WwiseStereoDelay = 0x00870003
    WwisePitchShifter = 0x00880003
    WwiseHarmonizer = 0x008A0003
    WwiseGain = 0x008B0003
    WwiseSynthOne = 0x00940002
    WwiseReflect = 0x00AB0003
    System = 0x00AE0007
    Communication = 0x00B00007
    ControllerHeadphones = 0x00B10007
    ControllerSpeaker = 0x00B30007
    NoOutput = 0x00B50007
    WwiseSystemOutputSettings = 0x03840009
    SoundSeedGrain = 0x00B70002
    MasteringSuite = 0x00BA0003
    WwiseAudioInput = 0x00C80002
    WwiseMotionGenerator1 = 0x01950002
    WwiseMotionGenerator2 = 0x01950005
    WwiseMotionSource1 = 0x01990002
    WwiseMotionSource2 = 0x01990005
    WwiseMotion = 0x01FB0007
    AuroHeadphone = 0x044C1073
    McDSPML1 = 0x00671003
    McDSPFutzBox = 0x006E1003
    IZotopeHybridReverb = 0x00021033
    IZotopeTrashDistortion = 0x00031033
    IZotopeTrashDelay = 0x00041033
    IZotopeTrashDynamicsMono = 0x00051033
    IZotopeTrashFilters = 0x00061033
    IZotopeTrashBoxModeler = 0x00071033
    IZotopeTrashMultibandDistortion = 0x00091033
    PlatinumMatrixSurroundMk2 = 0x006E0403
    PlatinumLoudnessMeter = 0x006F0403
    PlatinumSpectrumViewer = 0x00710403
    PlatinumEffectCollection = 0x00720403
    PlatinumMeterWithFilter = 0x00730403
    PlatinumSimple3D = 0x00740403
    PlatinumUpmixer = 0x00750403
    PlatinumReflection = 0x00760403
    PlatinumDownmixer = 0x00770403
    PlatinumFlex = 0x00780403
    CodemastersEffect = 0x00020403
    Ubisoft = 0x00640332
    UbisoftEffect1 = 0x04F70803
    UbisoftMixer = 0x04F80806
    UbisoftEffect2 = 0x04F90803
    MicrosoftSpatialSound = 0x00AA1137
    CPRimpleDelay = 0x000129A3
    CPRVoiceBroadcastReceive1 = 0x000229A2
    CPRVoiceBroadcastSend1 = 0x000329A3
    CPRVoiceBroadcastReceive2 = 0x000429A2
    CPRVoiceBroadcastSend2 = 0x000529A3
    CrankcaseREVModelPlayer = 0x01A01052


class EffectPluginType(EnumWithUnknown):
    Source = 2
    Effect = 3


class MarkerId(IntEnum):
    # We don't know the string values of these
    LoopStart = 43573010
    LoopEnd = 1539036744


# Cutoff frequencies for low pass filters:
# From https://www.audiokinetic.com/en/public-library/2025.1.9_9197/?source=Help&id=associating_low_pass_filter_values_with_their_corresponding_cutoff_frequencies
WwiseCutoffFrequencies = {
    0: 20000,
    1: 19567,
    2: 19133,
    3: 18700,
    4: 18267,
    5: 17833,
    6: 17400,
    7: 16967,
    8: 16533,
    9: 16100,
    10: 15667,
    11: 15233,
    12: 14800,
    13: 14367,
    14: 13933,
    15: 13500,
    16: 13067,
    17: 12633,
    18: 12200,
    19: 11767,
    20: 11333,
    21: 10900,
    22: 10467,
    23: 10033,
    24: 9600,
    25: 9167,
    26: 8733,
    27: 8300,
    28: 7867,
    29: 7433,
    30: 7000,
    31: 6422,
    32: 5892,
    33: 5405,
    34: 4959,
    35: 4550,
    36: 4174,
    37: 3829,
    38: 3513,
    39: 3223,
    40: 2957,
    41: 2713,
    42: 2489,
    43: 2283,
    44: 2095,
    45: 1922,
    46: 1763,
    47: 1618,
    48: 1484,
    49: 1361,
    50: 1249,
    51: 1146,
    52: 1051,
    53: 964,
    54: 885,
    55: 812,
    56: 745,
    57: 683,
    58: 627,
    59: 575,
    60: 528,
    61: 484,
    62: 444,
    63: 407,
    64: 374,
    65: 343,
    66: 315,
    67: 289,
    68: 265,
    69: 243,
    70: 223,
    71: 204,
    72: 188,
    73: 172,
    74: 158,
    75: 145,
    76: 133,
    77: 122,
    78: 112,
    79: 103,
    80: 94,
    81: 86,
    82: 79,
    83: 73,
    84: 67,
    85: 61,
    86: 56,
    87: 51,
    88: 47,
    89: 43,
    90: 40,
    91: 36,
    92: 33,
    93: 31,
    94: 28,
    95: 26,
    96: 24,
    97: 22,
    98: 20,
    99: 18,
    100: 17,
}

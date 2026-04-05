from enum import IntEnum, StrEnum


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


# TODO guessed
class CurveParameters(IntEnum):
    None_ = -1
    Volume1 = 0
    LPF = 1
    Volume2 = 2
    HPF = 3
    Spread = 4
    Focus = 5
    Reserved = 6


class RandomMode(IntEnum):
    Random = 0
    Shuffle = 1


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


class CurveScaling(IntEnum):
    None_ = 0x0
    DB = 0x2
    Log = 0x3
    DBToLin = 0x4


class GroupType(IntEnum):
    Switch = 0x0
    State = 0x1


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


class PluginId(IntEnum):
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


class MarkerIds(IntEnum):
    # We don't know the string values of these
    LoopStart = 43573010
    LoopEnd = 1539036744


# Seems to be a fixed sequence, probably hashes
SWITCH_GROUP_IDS = [
    3542429633,
    2515591576,
    866585565,
    847446114,
    1150349822,
    1902202008,
    483902209,
    1441934824,
    514904032,
    56759204,
    3126989719,
    1489354423,
    3905525753,
    1971625096,
    3637915147,
    1616602882,
    3894496501,
    3481581068,
    2271924278,
    1004196637,
    1442528243,
    4013339729,
    2796307820,
    613742101,
    525485163,
    4192883481,
    1292925647,
    518062628,
    1025216116,
    1568474447,
    2596938600,
    4206702229,
    3559404471,
    1784841708,
    3765513826,
    2037129417,
    4272577682,
    2135765449,
    2599511129,
    2613716188,
    2613716189,
    2613716190,
    1538950451,
    2078827875,
    1575902214,
    1476027921,
    4236723293,
    1933317553,
    4053036951,
    4017163688,
    2004483904,
    4019004407,
    412461880,
    2108245638,
    1945499476,
    2862950052,
    1836395786,
    1888528824,
    1462887001,
    33890273,
    1563051363,
    909606183,
    3977549511,
    1508413002,
    16109090,
    2003766585,
    2522610764,
    473615746,
    3159832036,
    4184793337,
    2418102691,
    3331638571,
    1605139770,
    520439139,
    3225389263,
    447954687,
    3692604948,
    3779067511,
    2426704050,
    1922044877,
    3079245127,
    3787844203,
    2653478244,
    3991679221,
    532698448,
    32379660,
    1454810063,
    1257305533,
    1089779977,
    2115764262,
    1323658502,
    3336129037,
    2814860561,
    2081655754,
    3005002201,
    4125122048,
    518912088,
    4068273420,
    1089688443,
    1431954419,
    3956179598,
    2326066381,
    437457885,
    1695064557,
    567805169,
    4002554925,
    24264894,
    1993718132,
    1575440872,
    4271758898,
    997184810,
    1291441777,
    597197681,
    1012311631,
    940968422,
]
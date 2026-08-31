from yonder import Game
from yonder.enums import EnumWithUnknown
from .game import GameObjects
from .data import load_actormixer_summary, load_gamestate_summary


# From wwiser, AkRTPC_ParameterID_135 seemed to match ER
# https://github.com/bnnm/wwiser/blob/master/wwiser/parser/wdefs.py
class RTPCParameter_EldenRing(EnumWithUnknown):
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


# TODO not used yet
AMBIENCE_SWITCH_GROUPS = [
    "_000_Silence",
    "_001_StonePavement",
    "_002_Stone",
    "_003_Dirt",
    "_004_Timber",
    "_005_Grass",
    "_006_Gravel",
    "_007_Magma",
    "_008_Wood",
    "_009_Swamp",
    "_010_nest",
    "_011_Iron",
    "_012_FleshAndBlood",
    "_013_Sand",
    "_014_Bone",
    "_015_Ash",
    "_016_RoofingTile",
    "_017_Cloth",
    "_018_FallenLeaves",
    "_019_Bell",
    "_020_Paddle",
    "_021_Water",
    "_022_WaterKnee",
    "_023_PoisonSwamp",
    "_024_PoisonSwampDeep",
    "_025_PoisonSwampKnee",
    "_026_PoisonSwampPaddle",
    "_027_WaterWaist",
    "_028_Carpet",
    "_029_None",
    "_030_Eclipse",
    "_031",
    "_032_Cloud",
    "_033_Abyss",
    "_034_Glass",
    "_035_Maggot",
    "_036_DeadlyPSwampPaddle",
    "_037_DeadlyPSwamp",
    "_038_DeadlyPSwampDeep",
    "_039_DeadlyPSwampKnee",
    "_040",
    "_041",
    "_042",
    "_043_Snow",
    "_044_Mud",
    "_045_Ice",
    "_100_IronWeapon",
    "_101_Mercury",
    "_102_WoodWeapon",
    "_103_FleshWeapon",
    "_104_IronShield",
    "_105_WoodShield",
    "_106_Iron",
    "_107_DriedFlesh",
    "_108_LeatherArmor",
    "_109_Flesh",
    "_110_FleshWeakness",
    "_111_FleshWeaknessHuge",
    "_112_HeavyIron",
    "_113_Cloth",
    "_114_Rune",
    "_115_RuneWeakness",
    "_116_StoneSoft",
    "_117_Stone",
    "_118_Mud",
    "_119_LavaWeakness",
    "_120_Lava",
    "_121_Spirit",
    "_122_Crystal",
    "_123_Shell",
    "_124_Bone",
    "_125_Carapace",
    "_126_SpiritWeakness",
    "_127_StoneShield",
    "_128_Wood",
    "_129_HeavyIronShield",
    "_130_WhiteGhost",
    "_134_Shadow",
    "_135_WGhostGuard",
    "_139_None",
    "_140_OldMetal",
    "_141_ShadowWeakness",
    "_142_SpiritGeneral",
    "_143_SpiritGeneralWeakness",
    "_144_ChainMail",
    "_145_BodyFluid",
    "_146_BodyFluidWeakness",
    "_147_Rotten",
    "_148_RottenWeakness",
    "_149_IronWeapon_Light",
    "_150_IronWeapon_Middle",
    "_151_IronWeapon_Heavy",
    "_152_WoodWeapon_Heavy",
    "_153_StoneWeapon",
    "_154_StoneWeapon_Light",
    "_155_StoneWeapon_Heavy",
    "_156_MercuryWeapon",
    "_157_CrystalWeapon",
    "_158_LetterWeapon",
    "_159_FingerWeapon",
    "_160_IronShield_Light",
    "_161_WoodShield_Heavy",
    "_162_StoneShield_Heavy",
    "_163_CrystalShield",
    "_164_GhostShield",
    "_165_MercuryHard",
    "_166_MalikethRobe",
    "_167_MalikethArmor",
    "_168_MassiveUniverse",
    "_171_Scale",
    "_172_ScaleWeakness",
    "_173_ScaleWeaknessHuge",
    "_174_HardScale",
    "_151114",
    "#940968422",
]


class GameEldenring(GameObjects):
    game = Game.EldenRing
    steam_app_id = 1245620
    regbin_key = bytes.fromhex(
        "99bffc366a6bc8c6f5827d093602d676c42892a01c207fb024d3af4e493fef99"
    )
    rtpc_params = RTPCParameter_EldenRing
    game_states = load_gamestate_summary(Game.EldenRing)
    amx_summary = load_actormixer_summary(Game.EldenRing)

from enum import IntEnum


class Game(IntEnum):
    EldenRing = 0
    Nightreign = 1


# Collected from cs_main and cs_smain
GameStates_EldenRing = {
    "FieldBattleState": ["FieldBattle", "FieldNormal"],
    "Set_State_EnvPlaceType": [
        "Env_000_Green",
        "Env_010_Lake",
        "Env_020_Mountain",
        "Env_030_Plain",
        "Env_040_Snow",
        "Env_050_Cemetery",
        "Env_051_CemeteryLatter",
        "Env_052_Hill",
        "Env_053_DarkTree",
        "Env_054_AbyssForest",
        "Env_100_Castle",
        "Env_110_KingCity",
        "Env_120_UgLabyrinth",
        "Env_130_Remains",
        "Env_140_Academy",
        "Env_150_RottenBigTree",
        "Env_160_VolcanoPrison",
        "Env_180_Tutorial",
        "Env_190_Ritual",
        "Env_200_TowerLow",
        "Env_202_TowerRevival",
        "Env_210_CenterFortress",
        "Env_220_Ark",
        "Env_280_Hall",
        "Env_300_Catacombs",
        "Env_310_Cave",
        "Env_320_Tunnel",
        "Env_340_Tower",
        "Env_350_UgKingCity",
        "Env_390_CliffTunnel",
        "Env_400_Catacombs_B",
        "Env_410_Prison",
        "Env_420_Blacksmith",
        "Env_430_Cave_B",
        "Env_500_Fortress",
        "Env_550_RoadFortress",
    ],
    "TimeZone": ["DayTime", "NightTime"],
    "BossBattleState": ["HU1", "HU2", "NoBattle"],
    "OutdoorIndoor": ["IndoorAll", "IndoorHalf", "Outdoor"],
    "StateWeatherType": [
        "_00_Sunny",
        "_01_ClearSky",
        "_10_WeakCloudy",
        "_11_Cloudy",
        "_20_Rain",
        "_21_HeavyRain",
        "_30_Storm",
        "_31_StormForBattle",
        "_40_Snow",
        "_41_HeavySnow",
        "_50_Fog",
        "_51_HeavyFog",
        "_52_HeavyFogRain",
        "_60_SandStorm",
        "_81_Snowstorm",
        "_82_Lightningstorm",
        "_83_Reserved",
        "_86_Reserved",
        "_87_Reserved",
        "_88_Reserved",
        "#137203006",
        "#4150439223",
    ],
    "CommonPlaceType": [
        "_01",
        "_02",
        "_03",
        "_10",
        "_11",
        "_12",
        "_14",
        "_15",
        "_16",
        "_17",
        "_18",
        "_20",
        "_22",
        "_23",
        "_24",
        "_29",
    ],
    "OutdoorIndoorForEnv": ["IndoorAll", "IndoorHalf", "Outdoor"],
    "BgmCutsceneId": ["s13000040"],
    "LoopCheck": ["None", "On"],
    "EasyOcclusionID": ["_1"],
    "OutdoorIndoorForRain": ["IndoorAll", "IndoorHalf", "Outdoor"],
    "BgmEnemyType": [
        "EventBoss_Reserved15",
        "EventBoss_Reserved14",
        "EventBoss_Reserved13",
        "EventBoss_Reserved12",
        "EventBoss_Reserved11",
        "EventBoss_Reserved10",
        "EventBoss_Reserved09",
        "EventBoss_Reserved08",
        "FieldBoss_Lv02",
        "FieldBoss_Lv03",
        "FieldBoss_Lv04",
        "FieldBoss_Lv05",
        "FieldBoss_Lv06",
        "FieldBoss_Lv07",
        "FieldBoss_Lv08",
        "FieldBoss_Lv09",
        "FieldBoss_Lv10",
        "FieldBoss_Lv11",
        "FieldBoss_Lv12",
        "FieldBoss_Lv13",
        "FieldBoss_Lv14",
        "FieldBoss_Lv15",
        "FieldBoss_Lv16",
        "FieldBoss_Lv17",
        "FieldBoss_Lv18",
        "FieldBoss_Lv19",
        "FieldBoss_Lv20",
        "FieldBoss_Lv21",
        "FieldBoss_Lv22",
        "FieldBoss_Lv23",
        "FieldBoss_Lv24",
        "FieldBoss_Lv25",
        "FieldBoss_Lv26",
        "FieldBoss_Lv27",
        "FieldBoss_Lv28",
        "FieldBoss_Lv29",
        "FieldBoss_Lv30",
        "FieldBoss_Lv31",
        "FieldStrongEnemyA",
        "FieldStrongEnemyB",
        "MidBoss_Aster",
        "MidBoss_BasementRoom",
        "MidBoss_BlackSword",
        "MidBoss_CarianRoyal",
        "MidBoss_Catacombs",
        "MidBoss_Catacombs_B",
        "MidBoss_Cave",
        "MidBoss_CircleEvent",
        "MidBoss_Creepy",
        "MidBoss_DaemonPhantom",
        "MidBoss_DarkKnights",
        "MidBoss_DeathGenus",
        "MidBoss_DeepBlood",
        "MidBoss_FieldDragon",
        "MidBoss_Fortress",
        "MidBoss_Godman",
        "MidBoss_Melee",
        "MidBoss_MeleeLast",
        "MidBoss_MeteoricIronBeast",
        "MidBoss_NewCircle",
        "MidBoss_Prison",
        "MidBoss_TreeDaemon",
        "MidBoss_TreeKnights",
        "MidBoss_Tunnel",
        "MidBoss_UgRemains",
        "MidBoss_Wolf",
        "MidBoss_Wyvern",
        "MultiHostile_00",
        "MultiHostile_01",
        "MultiHostile_02",
        "MultiHostile_03",
        "MultiHostile_04",
        "MultiHostile_05",
        "Reserved",
        "_BgmSilent",
        "_BgmSilent_MistWall",
        "c2030",
        "c2030_B",
        "c2110",
        "c2120",
        "c2130_A",
        "c2130_B",
        "c2190",
        "c3560",
        "c4510",
        "c4520",
        "c4670",
        "c4710",
        "c4720",
        "c4720_B",
        "c4730",
        "c4750",
        "c4760",
        "c4800",
        "c5020",
        "c5030",
        "c5050",
        "c5120",
        "c5130",
        "c5200",
        "c5210",
        "c5220",
        "c5230",
        "c5300",
    ],
    "BgmPlaceType": [
        "Bgm_000_Green",
        "Bgm_010_Lake",
        "Bgm_020_Mountain",
        "Bgm_021_Volcano",
        "Bgm_030_Plain",
        "Bgm_040_Snow",
        "Bgm_041_SnowUnder",
        "Bgm_050_Cemetery",
        "Bgm_051_CemeteryLatter",
        "Bgm_052_Hill",
        "Bgm_053_DarkTree",
        "Bgm_054_AbyssForest",
        "Bgm_100_Castle",
        "Bgm_110_KingCity",
        "Bgm_111_Hub",
        "Bgm_120_UgLabyrinth",
        "Bgm_121_UgLabyrinth_Ruins",
        "Bgm_130_Remains",
        "Bgm_140_Academy",
        "Bgm_150_RottenBigTree",
        "Bgm_151_RottenBigTreeLatter",
        "Bgm_160_VolcanoPrison",
        "Bgm_161_VolcanoHall",
        "Bgm_180_Tutorial",
        "Bgm_190_Ritual",
        "Bgm_200_TowerLow",
        "Bgm_201_TowerHigh",
        "Bgm_202_TowerRevival",
        "Bgm_210_CenterFortress",
        "Bgm_220_Ark",
        "Bgm_221_Npc405",
        "Bgm_250_Nursery",
        "Bgm_280_Hall",
        "Bgm_300_Catacombs",
        "Bgm_310_Cave",
        "Bgm_320_Tunnel",
        "Bgm_340_Tower",
        "Bgm_350_UgKingCity",
        "Bgm_351_UgKingCity_Tomb",
        "Bgm_390_CliffTunnel",
        "Bgm_400_Catacombs_B",
        "Bgm_410_Prison",
        "Bgm_420_Blacksmith",
        "Bgm_430_Cave_B",
        "Bgm_500_Fortress",
        "Bgm_501_FortressPlain",
        "Bgm_502_FortressPlainFes",
        "Bgm_550_RoadFortress",
        "Bgm_560_MtDragon",
        "Bgm_561_Frontier",
        "Bgm_562_FingerRuin",
        "Bgm_563_MediumVil",
    ],
    "FallenLeaves": ["On"],
    "#1807931947": ["A", "B"],
    "IsVisibleRetryDialog": ["Yes"],
    "Set_State_PlayerState": ["PlayerCrouching", "PlayerResting"],
    "FieldBgmSilent": ["On"],
    "TreeBurning": ["Burning_petit", "No"],
}


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
    GameStates = GameStates_EldenRing

    @classmethod
    def set_game(cls, game: Game) -> None:
        from yonder.util import logger

        cls.selected_game = game

        if game == Game.EldenRing:
            cls.RTPCParameter = RTPCParameter_EldenRing
            cls.GameStates = GameStates_EldenRing
        else:
            logger.warning(
                f"Game {game} is not supported yet, using EldenRing settings"
            )
            cls.set_game(Game.EldenRing)

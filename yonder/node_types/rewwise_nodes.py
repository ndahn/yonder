from __future__ import annotations
from typing import ClassVar, Optional, Union, get_args
from dataclasses import dataclass, field

from .rewwise_base_types import (
    AkGameSync,
    AkDecisionTreeNode,
    PropRangedModifiers,
    InitialRTPC,
    PropBundle,
    NodeBaseParams,
    AkBankSourceData,
    FxBaseInitialValues,
    BusInitialValues,
    SwitchPackage,
    AkSwitchNodeParams,
    Children,
    Playlist,
    ConeParams,
    AkConversionTable,
    MusicNodeParams,
    AkMusicMarkerWwise,
    AkClipAutomation,
    AkTrackSrcInfo,
    MusicTransNodeParams,
    AkMusicRanSeqPlaylistItem,
    AkLayer,
)
from .rewwise_action_params import ActionParams
from .rewwise_enums import AkGroupType, AkDecisionTreeMode


@dataclass
class AkStateObj:
    body_type: ClassVar[int] = 1
    entry_count: int = 0
    parameters: list[int] = field(default_factory=list)
    values: list[float] = field(default_factory=list)


@dataclass
class Sound:
    body_type: ClassVar[int] = 2
    bank_source_data: AkBankSourceData
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)


@dataclass
class Action:
    body_type: ClassVar[int] = 3
    action_type: int
    external_id: int
    is_bus: int = 0
    prop_bundle: list[PropBundle] = field(default_factory=list)
    ranged_modifiers: PropRangedModifiers = field(default_factory=PropRangedModifiers)
    params: ActionParams


@dataclass
class Event:
    body_type: ClassVar[int] = 4
    action_count: int = 0
    actions: list[int] = field(default_factory=list)


@dataclass
class RandomSequenceContainer:
    body_type: ClassVar[int] = 5
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    loop_count: int = 0
    loop_mod_min: int = 0
    loop_mod_max: int = 0
    transition_time: float = 0.0
    transition_time_mod_min: float = 0.0
    transition_time_mod_max: float = 0.0
    avoid_repeat_count: int = 0
    transition_mode: int = 0
    random_mode: int = 0
    mode: int = 0
    flags: int = 0
    children: Children = field(default_factory=Children)
    playlist: Playlist = field(default_factory=Playlist)


@dataclass
class SwitchContainer:
    body_type: ClassVar[int] = 6
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    group_type: int = 0
    group_id: int = 0
    default_switch: int = 0
    continuous_validation: int = 0
    children: Children = field(default_factory=Children)
    switch_group_count: int = 0
    switch_groups: list[SwitchPackage] = field(default_factory=list)
    switch_param_count: int = 0
    switch_params: list[AkSwitchNodeParams] = field(default_factory=list)


@dataclass
class ActorMixer:
    body_type: ClassVar[int] = 7
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    children: Children = field(default_factory=Children)


@dataclass
class Bus:
    body_type: ClassVar[int] = 8
    initial_values: BusInitialValues = field(default_factory=BusInitialValues)


@dataclass
class LayerContainer:
    body_type: ClassVar[int] = 9
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    children: Children = field(default_factory=Children)
    layer_count: int = 0
    layers: list[AkLayer] = field(default_factory=list)
    is_continuous_validation: int = 0


@dataclass
class Attentuation:
    body_type: ClassVar[int] = 14
    is_cone_enabled: int = 0
    cone_params: Optional[ConeParams] = None
    curves_to_use: list[int] = field(default_factory=lambda: [-1] * 7)
    curve_count: int = 0
    curves: list[AkConversionTable] = field(default_factory=list)
    initial_rtpc: InitialRTPC = field(default_factory=InitialRTPC)


@dataclass
class MusicRandomSequenceContainer:
    body_type: ClassVar[int] = 13
    music_trans_node_params: MusicTransNodeParams = field(
        default_factory=MusicTransNodeParams
    )
    playlist_item_count: int = 0
    playlist_items: list[AkMusicRanSeqPlaylistItem] = field(default_factory=list)


@dataclass
class MusicSegment:
    body_type: ClassVar[int] = 10
    music_node_params: MusicNodeParams = field(default_factory=MusicNodeParams)
    duration: float = 0.0
    marker_count: int = 0
    markers: list[AkMusicMarkerWwise] = field(default_factory=list)


@dataclass
class MusicTrack:
    body_type: ClassVar[int] = 11
    flags: int = 0
    source_count: int = 0
    sources: list[AkBankSourceData] = field(default_factory=list)
    playlist_item_count: int = 0
    playlist: list[AkTrackSrcInfo] = field(default_factory=list)
    subtrack_count: int = 0
    clip_item_count: int = 0
    clip_items: list[AkClipAutomation] = field(default_factory=list)
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    track_type: int = 0
    look_ahead_time: int = 0


@dataclass
class MusicSwitchContainer:
    body_type: ClassVar[int] = 12
    music_trans_node_params: MusicTransNodeParams = field(
        default_factory=MusicTransNodeParams
    )
    continue_playback: int = 0
    tree_depth: int = 0
    arguments: list[AkGameSync] = field(default_factory=list)
    group_types: list[AkGroupType] = field(default_factory=list)
    tree_size: int = 0
    tree_mode: AkDecisionTreeMode = AkDecisionTreeMode.BestMatch
    tree: AkDecisionTreeNode = field(
        default_factory=lambda: AkDecisionTreeNode(
            key=0, node_id=0, first_child_index=0
        )
    )


@dataclass
class DialogueEvent:
    body_type: ClassVar[int] = 15
    probability: int = 100
    tree_depth: int = 0
    arguments: list[AkGameSync] = field(default_factory=list)
    group_types: list[AkGroupType] = field(default_factory=list)
    tree_size: int = 0
    tree_mode: AkDecisionTreeMode = AkDecisionTreeMode.BestMatch
    tree: AkDecisionTreeNode = field(
        default_factory=lambda: AkDecisionTreeNode(
            key=0, node_id=0, first_child_index=0
        )
    )
    prop_bundle: list[PropBundle] = field(default_factory=list)
    ranged_modifiers: PropRangedModifiers = field(default_factory=PropRangedModifiers)


@dataclass
class FxShareSet:
    body_type: ClassVar[int] = 16
    fx_base_initial_values: FxBaseInitialValues = field(
        default_factory=lambda: FxBaseInitialValues(fx_id=0)
    )


@dataclass
class FxCustom:
    body_type: ClassVar[int] = 17
    fx_base_initial_values: FxBaseInitialValues = field(
        default_factory=lambda: FxBaseInitialValues(fx_id=0)
    )


@dataclass
class AuxBus:
    body_type: ClassVar[int] = 18
    initial_values: BusInitialValues = field(default_factory=BusInitialValues)


@dataclass
class AudioDevice:
    body_type: ClassVar[int] = 21
    fx_base_initial_values: FxBaseInitialValues = field(
        default_factory=lambda: FxBaseInitialValues(fx_id=0)
    )


@dataclass
class TimeModulator:
    body_type: ClassVar[int] = 22
    prop_bundle: list[PropBundle] = field(default_factory=list)
    ranged_modifiers: PropRangedModifiers = field(default_factory=PropRangedModifiers)
    initial_rtpc: InitialRTPC = field(default_factory=InitialRTPC)


@dataclass
class TodoObject:
    body_type: ClassVar[int] = 0
    data: list[int] = field(default_factory=list)


AkNodeType = Union[
    AkStateObj,
    Sound,
    Action,
    Event,
    RandomSequenceContainer,
    SwitchContainer,
    ActorMixer,
    Bus,
    LayerContainer,
    MusicSegment,
    MusicTrack,
    MusicSwitchContainer,
    MusicRandomSequenceContainer,
    Attentuation,
    DialogueEvent,
    FxShareSet,
    FxCustom,
    AuxBus,
    TodoObject,
    AudioDevice,
    TimeModulator,
]


BODY_TYPE_MAP = {cls.body_type: cls for cls in get_args(AkNodeType)}
from __future__ import annotations
from typing import Any, ClassVar, Optional, Union, get_args
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
from .rewwise_enums import AkGroupType, AkDecisionTreeMode
from .rewwise_parse import serialize, deserialize
from .object_id import ObjectId


# rewwise inserts the class name of the node type into the hierarchy
# (e.g. body: {Sound: ...})
@dataclass
class _HIRCNodeBody:
    def to_dict(self) -> dict:
        return {type(self).__name__: serialize(self)}

    @classmethod
    def from_dict(cls, data: dict) -> "_HIRCNodeBody":
        for sub in cls.__subclasses__():
            if sub.__name__ in data:
                return deserialize(sub, data[sub.__name__])

        raise ValueError(f"Not a valid _HIRCNodeBody: {data}")


@dataclass
class HIRCNode:
    id: ObjectId
    body: _HIRCNodeBody

    @property
    def type_id(self) -> int:
        return type(self.body).body_type

    @property
    def type_name(self) -> str:
        return type(self.body).__name__

    def to_dict(self) -> dict:
        ser = serialize(self)
        ser.update(
            {
                # These two are just here to make rewwise happy
                "body_type": self.type_id,
                "size": 0,
            }
        )
        return ser



@dataclass
class State(_HIRCNodeBody):
    body_type: ClassVar[int] = 1
    entry_count: int = 0
    parameters: list[int] = field(default_factory=list)
    values: list[float] = field(default_factory=list)


@dataclass
class Sound(_HIRCNodeBody):
    body_type: ClassVar[int] = 2
    bank_source_data: AkBankSourceData = field(default_factory=AkBankSourceData)
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)


@dataclass
class Action(_HIRCNodeBody):
    body_type: ClassVar[int] = 3
    action_type: int
    external_id: int
    is_bus: int = 0
    prop_bundle: list[PropBundle] = field(default_factory=list)
    ranged_modifiers: PropRangedModifiers = field(default_factory=PropRangedModifiers)
    params: _ActionParams


@dataclass
class Event(_HIRCNodeBody):
    body_type: ClassVar[int] = 4
    action_count: int = 0
    actions: list[int] = field(default_factory=list)


@dataclass
class RandomSequenceContainer(_HIRCNodeBody):
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
class SwitchContainer(_HIRCNodeBody):
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
class ActorMixer(_HIRCNodeBody):
    body_type: ClassVar[int] = 7
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    children: Children = field(default_factory=Children)


@dataclass
class Bus(_HIRCNodeBody):
    body_type: ClassVar[int] = 8
    initial_values: BusInitialValues = field(default_factory=BusInitialValues)


@dataclass
class LayerContainer(_HIRCNodeBody):
    body_type: ClassVar[int] = 9
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    children: Children = field(default_factory=Children)
    layer_count: int = 0
    layers: list[AkLayer] = field(default_factory=list)
    is_continuous_validation: int = 0


@dataclass
class Attentuation(_HIRCNodeBody):
    body_type: ClassVar[int] = 14
    is_cone_enabled: int = 0
    cone_params: Optional[ConeParams] = None
    curves_to_use: list[int] = field(default_factory=lambda: [-1] * 7)
    curve_count: int = 0
    curves: list[AkConversionTable] = field(default_factory=list)
    initial_rtpc: InitialRTPC = field(default_factory=InitialRTPC)


@dataclass
class MusicRandomSequenceContainer(_HIRCNodeBody):
    body_type: ClassVar[int] = 13
    music_trans_node_params: MusicTransNodeParams = field(
        default_factory=MusicTransNodeParams
    )
    playlist_item_count: int = 0
    playlist_items: list[AkMusicRanSeqPlaylistItem] = field(default_factory=list)


@dataclass
class MusicSegment(_HIRCNodeBody):
    body_type: ClassVar[int] = 10
    music_node_params: MusicNodeParams = field(default_factory=MusicNodeParams)
    duration: float = 0.0
    marker_count: int = 0
    markers: list[AkMusicMarkerWwise] = field(default_factory=list)


@dataclass
class MusicTrack(_HIRCNodeBody):
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
class MusicSwitchContainer(_HIRCNodeBody):
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
class DialogueEvent(_HIRCNodeBody):
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
class FxShareSet(_HIRCNodeBody):
    body_type: ClassVar[int] = 16
    fx_base_initial_values: FxBaseInitialValues = field(
        default_factory=lambda: FxBaseInitialValues(fx_id=0)
    )


@dataclass
class FxCustom(_HIRCNodeBody):
    body_type: ClassVar[int] = 17
    fx_base_initial_values: FxBaseInitialValues = field(
        default_factory=lambda: FxBaseInitialValues(fx_id=0)
    )


@dataclass
class AuxBus(_HIRCNodeBody):
    body_type: ClassVar[int] = 18
    initial_values: BusInitialValues = field(default_factory=BusInitialValues)


@dataclass
class AudioDevice(_HIRCNodeBody):
    body_type: ClassVar[int] = 21
    fx_base_initial_values: FxBaseInitialValues = field(
        default_factory=lambda: FxBaseInitialValues(fx_id=0)
    )


@dataclass
class TimeModulator(_HIRCNodeBody):
    body_type: ClassVar[int] = 22
    prop_bundle: list[PropBundle] = field(default_factory=list)
    ranged_modifiers: PropRangedModifiers = field(default_factory=PropRangedModifiers)
    initial_rtpc: InitialRTPC = field(default_factory=InitialRTPC)


@dataclass
class TodoObject(_HIRCNodeBody):
    body_type: ClassVar[int] = 0
    data: list[int] = field(default_factory=list)


# AkNodeType = Union[*_HIRCNodeBody.__subclasses__()]
AkNodeType = Union[
    State,
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

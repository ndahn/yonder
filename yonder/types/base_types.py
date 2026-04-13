from __future__ import annotations
from typing import Any, Iterator
from dataclasses import dataclass, field

from yonder.hash import lookup_name
from yonder.enums import (
    CurveInterpolation,
    ClipAutomationType,
    PropID,
    ParameterID,
    PathMode,
    ThreeDSpatializationMode,
    SpeakerPanningType,
    ThreeDPositionType,
    VirtualQueueBehavior,
    BelowThresholdBehavior,
    SyncType,
    RtpcAccum,
    RtpcType,
    CurveScaling,
    SourceType,
    PluginId,
)


@dataclass(slots=True)
class GameSync:
    group_id: int


@dataclass(slots=True)
class ConeParams:
    inside_degrees: float = 0.0
    outside_degrees: float = 0.0
    outside_volume: float = 0.0
    low_pass: float = 0.0
    high_pass: float = 0.0


@dataclass(slots=True)
class MusicFade:
    transition_time: int = 0
    curve: CurveInterpolation = CurveInterpolation.Log3
    offset: int = 0


@dataclass(slots=True)
class MusicTransitionObject:
    segment_id: int = 0
    fade_out: MusicFade = field(default_factory=MusicFade)
    fade_in: MusicFade = field(default_factory=MusicFade)
    play_pre_entry: int = 0
    play_post_exit: int = 0

    def get_references(self) -> list[tuple[str, int]]:
        return [("segment_id", self.segment_id)]


@dataclass(slots=True)
class MusicTransSrcRule:
    transition_time: int = 0
    fade_curve: CurveInterpolation = CurveInterpolation.Linear
    fade_offet: int = 0  # TODO typo in bnk2json
    sync_type: SyncType = SyncType.Immediate
    clue_filter_hash: int = 0
    play_post_exit: int = 0


@dataclass(slots=True)
class MusicTransDstRule:
    transition_time: int = 0
    fade_curve: CurveInterpolation = CurveInterpolation.Linear
    fade_offet: int = 0  # TODO typo in bnk2json
    clue_filter_hash: int = 0
    jump_to_id: int = 0
    jump_to_type: int = 0
    entry_type: int = 0
    play_pre_entry: int = 0
    destination_match_source_cue_name: int = 0

    def get_references(self) -> list[tuple[str, int]]:
        return [("jump_to_id", self.jump_to_id)]


@dataclass(slots=True)
class MusicTransitionRule:
    source_transition_rule_count: int = 0
    source_ids: list[int] = field(default_factory=lambda: [-1])
    destination_transition_rule_count: int = 0
    destination_ids: list[int] = field(default_factory=lambda: [-1])
    source_transition_rule: MusicTransSrcRule = field(default_factory=MusicTransSrcRule)
    destination_transition_rule: MusicTransDstRule = field(
        default_factory=MusicTransDstRule
    )
    alloc_trans_object_flag: int = 0
    transition_object: MusicTransitionObject = field(
        default_factory=MusicTransitionObject
    )

    def get_references(self) -> list[tuple[str, int]]:
        refs = []
        refs.extend([(f"source_ids:{i}", sid) for i, sid in enumerate(self.source_ids)])
        refs.extend(
            [
                (f"destination_ids:{i}", did)
                for i, did in enumerate(self.destination_ids)
            ]
        )
        return refs


@dataclass(slots=True)
class RTPCGraphPoint:
    from_: float = 0.0
    to: float = 0.0
    interpolation: CurveInterpolation = CurveInterpolation.Linear

    @property
    def coords(self) -> tuple[float, float]:
        return (self.from_, self.to)


@dataclass(slots=True)
class ConversionTable:
    curve_scaling: CurveScaling = CurveScaling.None_
    point_count: int = 0
    points: list[RTPCGraphPoint] = field(default_factory=list)


@dataclass(slots=True)
class ObsOccCurve:
    curve_enabled: int = 0
    curve_scaling: int = 0
    point_count: int = 0
    points: list[RTPCGraphPoint] = field(default_factory=list)


@dataclass(slots=True)
class ObsConversionTable:
    curve_obs_vol: ObsOccCurve = field(default_factory=ObsOccCurve)
    curve_obs_lpf: ObsOccCurve = field(default_factory=ObsOccCurve)
    curve_obs_hpf: ObsOccCurve = field(default_factory=ObsOccCurve)
    curve_occ_vol: ObsOccCurve = field(default_factory=ObsOccCurve)
    curve_occ_lpf: ObsOccCurve = field(default_factory=ObsOccCurve)
    curve_occ_hpf: ObsOccCurve = field(default_factory=ObsOccCurve)


@dataclass(slots=True)
class TrackSrcInfo:
    track_id: int = 0
    source_id: int = 0
    event_id: int = 0
    play_at: float = 0.0
    begin_trim_offset: float = 0.0
    end_trim_offset: float = 0.0
    source_duration: float = 0.0

    def get_references(self) -> list[tuple[str, int]]:
        # TODO not sure about track_id and event_id
        # source_id might also match an fx effect
        return [("source_id", self.source_id)]


@dataclass(slots=True)
class ClipAutomation:
    clip_index: int = 0
    auto_type: ClipAutomationType = ClipAutomationType.Volume
    graph_point_count: int = 0
    graph_points: list[RTPCGraphPoint] = field(default_factory=list)


@dataclass(slots=True)
class IAkPlugin:
    plugin_id: PluginId
    dll_name_length: int = 0
    dll_name: str = ""


@dataclass(slots=True)
class StateTransition:
    from_state: int = 0
    to_state: int = 0
    transition_time: int = 0


@dataclass(slots=True)
class SwitchGraphPoint:
    rtpc_value: float = 0.0
    switch: int = 0
    curve_shape: int = 0


@dataclass(slots=True)
class StateGroup:
    id: int = 0
    default_transition_time: int = 0
    transition_count: int = 0
    transitions: list[StateTransition] = field(default_factory=list)


@dataclass(slots=True)
class SwitchGroup:
    id: int = 0
    rtpc_id: int = 0
    rtpc_type: int = 0
    graph_point_count: int = 0
    graph_points: list[SwitchGraphPoint] = field(default_factory=list)


@dataclass(slots=True)
class RTPCRamping:
    rtpc_id: int = 0
    value: int = 0
    ramp_type: int = 0
    ramp_up: float = 0.0
    ramp_down: float = 0.0
    bind_to_built_in_param: int = 0


@dataclass(slots=True)
class AcousticTexture:
    id: int = 0
    absorption_offset: float = 0.0
    absorption_low: float = 0.0
    absorption_mid_low: float = 0.0
    absorption_mid_high: float = 0.0
    absorption_high: float = 0.0
    scattering: float = 0.0


@dataclass(slots=True)
class FXChunk:
    fx_index: int = 0
    fx_id: int = 0
    is_share_set: int = 0
    is_rendered: int = 0

    def get_references(self) -> list[tuple[str, int]]:
        return [("fx_id", self.fx_id)]


@dataclass(slots=True)
class PropRangedModifier:
    prop_type: int = 0
    min: float = 0.0
    max: float = 0.0


@dataclass(slots=True)
class PropRangedModifiers:
    count: int = 0
    entries: list[PropRangedModifier] = field(default_factory=list)


@dataclass(slots=True)
class PathVertex:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    duration: int = 0


@dataclass(slots=True)
class PathListItemOffset:
    vertices_offset: int = 0
    vertices_count: int = 0


@dataclass(slots=True)
class Ak3DAutomationParams:
    range_x: float = 0.0
    range_y: float = 0.0
    range_z: float = 0.0


@dataclass(slots=True)
class PositioningParams:
    unk1: bool = False
    three_dimensional_position_type: ThreeDPositionType = ThreeDPositionType.Emitter
    speaker_panning_type: SpeakerPanningType = (
        SpeakerPanningType.DirectSpeakerAssignment
    )
    listener_relative_routing: bool = False
    override_parent: bool = False
    unk2: bool = False
    enable_diffraction: bool = False
    hold_listener_orientation: bool = False
    hold_emitter_position_and_orientation: bool = False
    enable_attenuation: bool = False
    three_dimensional_spatialization_mode: ThreeDSpatializationMode = (
        ThreeDSpatializationMode.None_
    )
    path_mode: PathMode = PathMode.StepSequence
    transition_time: int = 0
    vertex_count: int = 0
    vertices: list[PathVertex] = field(default_factory=list)
    path_list_item_count: int = 0
    path_list_item_offsets: list[PathListItemOffset] = field(default_factory=list)
    three_dimensional_automation_params: list[Ak3DAutomationParams] = field(
        default_factory=list
    )


@dataclass(slots=True)
class AuxParams:
    unk1: bool = False
    unk2: bool = False
    unk3: bool = False
    override_reflections_aux_bus: bool = False
    has_aux: bool = False
    override_user_aux_sends: bool = False
    unk4: int = 0
    aux1: int = 0
    aux2: int = 0
    aux3: int = 0
    aux4: int = 0
    reflections_aux_bus: int = 0

    def get_references(self) -> list[tuple[str, int]]:
        return [
            ("aux1", self.aux1),
            ("aux2", self.aux2),
            ("aux3", self.aux3),
            ("aux4", self.aux4),
            ("reflection_aux_bus", self.reflection_aux_bus),
        ]


@dataclass(slots=True)
class AdvSettingsParams:
    unk1: bool = False
    unk2: bool = False
    unk3: bool = False
    is_virtual_voices_opt_override_parent: bool = False
    ignore_parent_maximum_instances: bool = False
    unk4: bool = False
    use_virtual_behavior: bool = False
    kill_newest: bool = False
    virtual_queue_behavior: VirtualQueueBehavior = (
        VirtualQueueBehavior.PlayFromBeginning
    )
    max_instance_count: int = 0
    below_threshold_behavior: BelowThresholdBehavior = (
        BelowThresholdBehavior.ContinueToPlay
    )
    unk5: bool = False
    unk6: bool = False
    unk7: bool = False
    unk8: bool = False
    enable_envelope: bool = False
    normalize_loudness: bool = False
    override_analysis: bool = False
    override_hdr_envelope: bool = False


@dataclass(slots=True)
class AkState:
    state_id: int = 0
    state_instance_id: int = 0

    def get_references(self) -> list[tuple[str, int]]:
        # TODO not sure about this one
        return [("state_id", self.state_id)]


@dataclass(slots=True)
class StatePropertyInfo:
    property: PropID = PropID.Volume
    accum_type: RtpcAccum = RtpcAccum.None_
    in_db: int = 0


@dataclass(slots=True)
class StateGroupChunk:
    state_group_id: int = 0
    sync_type: SyncType = SyncType.Immediate
    state_count: int = 0
    states: list[AkState] = field(default_factory=list)


@dataclass(slots=True)
class StateChunk:
    state_property_count: int = 0
    state_property_info: list[StatePropertyInfo] = field(default_factory=list)
    state_group_count: int = 0
    state_group_chunks: list[StateGroupChunk] = field(default_factory=list)


@dataclass(slots=True)
class RTPC:
    id: int = 0
    rtpc_type: RtpcType = RtpcType.GameParameter
    rtpc_accum: RtpcAccum = RtpcAccum.None_
    param_id: int = 0
    curve_id: int = 0
    curve_scaling: CurveScaling = CurveScaling.None_
    graph_point_count: int = 0
    graph_points: list[RTPCGraphPoint] = field(default_factory=list)

    def get_name(self, default: Any = None) -> str:
        return lookup_name(self.id, default)    


@dataclass(slots=True)
class InitialRTPC:
    count: int = 0
    rtpcs: list[RTPC] = field(default_factory=list)


@dataclass(slots=True)
class NodeInitialFxParams:
    is_override_parent_fx: int = 0
    fx_chunk_count: int = 0
    fx_bypass_bits: int = 0
    fx_chunks: list[FXChunk] = field(default_factory=list)


@dataclass(slots=True)
class PropBundle:
    prop_id: PropID = PropID.Volume
    value: float = 0.0

    def get_references(self) -> list[tuple[str, int]]:
        if self.prop_id in (PropID.AttachedPluginFXID, PropID.AttenuationID):
            return [("value", int(self.value))]

    @classmethod
    def from_dict(cls, data: dict) -> PropBundle:
        prop_id, value = next(iter(data.items()))
        return cls(PropID[prop_id], value)

    def to_dict(self) -> dict:
        return {self.prop_id.name: self.value}


@dataclass(slots=True)
class NodeInitialParams:
    prop_initial_values: list[PropBundle] = field(default_factory=list)
    prop_ranged_modifiers: PropRangedModifiers = field(
        default_factory=PropRangedModifiers
    )

    # TODO might also use attenuation or FX but enum is not known atm


@dataclass(slots=True)
class PropBundleByte:
    count: int = 0
    types: list[PropID] = field(default_factory=list)
    values: list[float] = field(default_factory=list)

    def validate(self) -> None:
        if len(self.types) != len(self.values):
            raise ValueError("types and values must be the same length")


@dataclass(slots=True)
class Children:
    count: int = 0
    items: list[int] = field(default_factory=list)

    def add(self, item: int) -> None:
        if item not in self.items:
            self.items.add(item)
            self.items.sort()

    def pop(self, item: int, missing_ok: bool = True) -> None:
        for idx, val in enumerate(self.items):
            if val == item:
                del self.items[idx]
                return

        if not missing_ok:
            raise ValueError(f"Item {item} not found")

    def clear(self) -> None:
        self.items.clear()

    def __getitem__(self, idx: int) -> int:
        return self.items[idx]

    def __setitem__(self, idx: int, item: int) -> int:
        self.items[idx] = item

    def __delitem__(self, idx: int) -> None:
        del self.items[idx]

    def __iter__(self) -> Iterator[int]:
        yield from self.items

    def __len__(self) -> int:
        return len(self.items)

    def validate(self) -> None:
        self.items = sorted(set(self.items))

    def get_references(self) -> list[tuple[str, int]]:
        return [(f"items:{i}", item) for i, item in enumerate(self.items)]


@dataclass(slots=True)
class NodeBaseParams:
    node_initial_fx_parameters: NodeInitialFxParams = field(
        default_factory=NodeInitialFxParams
    )
    override_attachment_params: int = 0
    override_bus_id: int = 0
    direct_parent_id: int = 0
    unknown_flags: int = 0
    node_initial_params: NodeInitialParams = field(default_factory=NodeInitialParams)
    positioning_params: PositioningParams = field(default_factory=PositioningParams)
    aux_params: AuxParams = field(default_factory=AuxParams)
    adv_settings_params: AdvSettingsParams = field(default_factory=AdvSettingsParams)
    state_chunk: StateChunk = field(default_factory=StateChunk)
    initial_rtpc: InitialRTPC = field(default_factory=InitialRTPC)

    def get_references(self) -> list[tuple[str, int]]:
        return [("override_bus_id", self.override_bus_id)]


@dataclass(slots=True)
class MediaInformation:
    source_id: int = 0
    in_memory_media_size: int = 0
    source_flags: int = 0

    def get_references(self) -> list[tuple[str, int]]:
        # May match an fx effect
        return [("source_id", self.source_id)]


@dataclass(slots=True)
class BankSourceData:
    plugin: PluginId = PluginId.VORBIS
    source_type: SourceType = SourceType.Embedded
    media_information: MediaInformation = field(
        default_factory=lambda: MediaInformation(source_id=0)
    )
    params_size: int = 0
    params: list[int] = field(default_factory=list)


@dataclass(slots=True)
class DuckInfo:
    bus_id: int = 0
    duck_volume: float = 0.0
    fade_out_time: int = 0
    fade_in_time: int = 0
    fade_curve: CurveInterpolation = CurveInterpolation.Linear
    target_prop: PropID = PropID.Volume

    def get_references(self) -> list[tuple[str, int]]:
        return [("bus_id", self.bus_id)]


@dataclass(slots=True)
class BusInitialParams:
    prop_bundle: list[PropBundle] = field(default_factory=list)
    positioning_params: PositioningParams = field(default_factory=PositioningParams)
    aux_params: AuxParams = field(default_factory=AuxParams)
    flags: int = 0
    max_instance_count: int = 0
    channel_config: int = 0
    hdr_flags: int = 0


@dataclass(slots=True)
class BusInitialFxParams:
    fx_count: int = 0
    fx_bypass: int = 0
    fx: list[FXChunk] = field(default_factory=list)
    fx_id_0: int = 0
    is_share_set_0: int = 0

    def get_references(self) -> list[tuple[str, int]]:
        return [("fx_id_0", self.fx_id_0)]


@dataclass(slots=True)
class BusInitialValues:
    override_bus_id: int = 0
    device_share_set_id: int = 0
    bus_initial_params: BusInitialParams = field(default_factory=BusInitialParams)
    recovery_time: int = 0
    max_duck_volume: float = 0.0
    duck_count: int = 0
    ducks: list[DuckInfo] = field(default_factory=list)
    bus_initial_fx_params: BusInitialFxParams = field(
        default_factory=BusInitialFxParams
    )
    override_attachment_params: int = 0
    initial_rtpc: InitialRTPC = field(default_factory=InitialRTPC)
    state_chunk: StateChunk = field(default_factory=StateChunk)

    def get_references(self) -> list[tuple[str, int]]:
        return [
            ("override_bus_id", self.override_bus_id),
            ("device_share_set_id", self.device_share_set_id),
        ]


@dataclass(slots=True)
class MediaMap:
    index: int = 0
    source_id: int = 0

    def get_references(self) -> list[tuple[str, int]]:
        # Usually not a reference, but might be paired with an effect
        return [("source_id", self.source_id)]


@dataclass(slots=True)
class PluginPropertyValue:
    property: ParameterID = ParameterID.Volume
    rtpc_accum: RtpcAccum = RtpcAccum.None_
    value: float = 0.0


@dataclass(slots=True)
class FxBaseInitialValues:
    fx_id: int = 0
    params_size: int = 0
    params: list[int] = field(default_factory=list)
    media_count: int = 0
    media: list[MediaMap] = field(default_factory=list)
    initial_rtpc: InitialRTPC = field(default_factory=InitialRTPC)
    state_chunk: StateChunk = field(default_factory=StateChunk)
    property_value_count: int = 0
    property_values: list[PluginPropertyValue] = field(default_factory=list)


@dataclass(slots=True)
class SwitchPackage:
    switch_id: int
    node_count: int = 0
    nodes: list[int] = field(default_factory=list)

    def get_references(self) -> list[tuple[str, int]]:
        return [(f"nodes:{i}", nid) for i, nid in enumerate(self.nodes)]


@dataclass(slots=True)
class SwitchNodeParams:
    node_id: int
    unk1: bool = False
    unk2: bool = False
    unk3: bool = False
    unk4: bool = False
    unk5: bool = False
    unk6: bool = False
    continue_playback: bool = False
    is_first_only: bool = False
    unk9: bool = False
    unk10: bool = False
    unk11: bool = False
    unk12: bool = False
    unk13: bool = False
    unk14: bool = False
    unk15: bool = False
    unk16: bool = False
    fade_out_time: int = 0
    fade_in_time: int = 0

    def get_references(self) -> list[tuple[str, int]]:
        return [("node_id", self.node_id)]


@dataclass(slots=True)
class MeterInfo:
    grid_period: float = 0.0
    grid_offset: float = 0.0
    tempo: float = 120.0
    time_signature_beat_count: int = 4
    time_signature_beat_value: int = 4
    meter_info_flag: int = 0


@dataclass(slots=True)
class Stinger:
    trigger_id: int = 0
    segment_id: int = 0
    sync_play_at: SyncType = SyncType.Immediate
    cue_filter_hash: int = 0
    dont_repeat_time: int = 0
    segment_look_head_count: int = 0

    def get_references(self) -> list[tuple[str, int]]:
        return [("segment_id", self.segment_id)]


@dataclass(slots=True)
class DecisionTreeNode:
    key: int = 0
    node_id: int = 0
    first_child_index: int = 0
    child_count: int = 0
    weight: int = 50
    probability: int = 100
    children: list[DecisionTreeNode] = field(default_factory=list)

    def validate(self) -> None:
        self.children.sort(key=lambda x: x.key)

    def get_references(self) -> list[tuple[str, int]]:
        return [("node_id", self.node_id)]


@dataclass(slots=True)
class AssociatedChildData:
    associated_child_id: int
    graph_point_count: int = 0
    graph_points: list[RTPCGraphPoint] = field(default_factory=list)

    def get_references(self) -> list[tuple[str, int]]:
        return [("associated_child_id", self.associated_child_id)]


@dataclass(slots=True)
class Layer:
    layer_id: int
    initial_rtpc: InitialRTPC = field(default_factory=InitialRTPC)
    rtpc_id: int = 0
    rtpc_type: RtpcType = RtpcType.GameParameter
    associated_childen_count: int = 0  # NOTE typo in rewwise
    associated_children: list[AssociatedChildData] = field(default_factory=list)


@dataclass(slots=True)
class PlaylistItem:
    play_id: int
    weight: int = 50000

    def get_references(self) -> list[tuple[str, int]]:
        return [("play_id", self.play_id)]


@dataclass(slots=True)
class Playlist:
    count: int = 0
    items: list[PlaylistItem] = field(default_factory=list)


@dataclass(slots=True)
class MusicNodeParams:
    flags: int = 0
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    children: Children = field(default_factory=Children)
    meter_info: MeterInfo = field(default_factory=MeterInfo)
    stinger_count: int = 0
    stingers: list[Stinger] = field(default_factory=list)


@dataclass(slots=True)
class MusicTransNodeParams:
    music_node_params: MusicNodeParams = field(default_factory=MusicNodeParams)
    transition_rule_count: int = 0
    transition_rules: list[MusicTransitionRule] = field(default_factory=list)


@dataclass(slots=True)
class MusicRanSeqPlaylistItem:
    segment_id: int
    playlist_item_id: int = 0
    child_count: int = 0
    ers_type: int = 0
    loop_base: int = 0
    loop_min: int = 0
    loop_max: int = 0
    weight: int = 50
    avoid_repeat_count: int = 0
    use_weight: int = 0
    shuffle: int = 0

    def get_references(self) -> list[tuple[str, int]]:
        return [("segment_id", self.segment_id)]


@dataclass(slots=True)
class MusicMarkerWwise:
    id: int
    position: float = 0.0
    string_length: int = 0
    string: str = ""

    def get_name(self, default: Any = None) -> str:
        return lookup_name(self.id, default)

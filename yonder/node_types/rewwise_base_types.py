from __future__ import annotations
from typing import Optional
from dataclasses import dataclass, field

from .rewwise_enums import (
    AkCurveInterpolation,
    AkPropID,
    AkParameterID,
    AkPathMode,
    Ak3DSpatializationMode,
    AkSpeakerPanningType,
    Ak3DPositionType,
    AkVirtualQueueBehavior,
    AkBelowThresholdBehavior,
    AkSyncType,
    AkSyncTypeU8,
    AkRtpcAccum,
    AkRtpcType,
    AkCurveScaling,
    AkClipAutomationType,
    SourceType,
    PluginId,
)


@dataclass
class AkGameSync:
    group_id: int


@dataclass
class AkDecisionTreeNode:
    key: int
    node_id: int
    first_child_index: int
    child_count: int = 0
    weight: int = 50
    probability: int = 100
    children: list[AkDecisionTreeNode] = field(default_factory=list)


@dataclass
class AkMusicFade:
    transition_time: int = 0
    curve: AkCurveInterpolation = AkCurveInterpolation.Constant
    offset: int = 0


@dataclass
class AkMusicTransitionObject:
    segment_id: int = 0
    fade_out: AkMusicFade = field(default_factory=AkMusicFade)
    fade_in: AkMusicFade = field(default_factory=AkMusicFade)
    play_pre_entry: int = 0
    play_post_exit: int = 0


@dataclass
class AkMusicTransSrcRule:
    transition_time: int = 0
    fade_curve: AkCurveInterpolation = AkCurveInterpolation.Constant
    fade_offet: int = 0
    sync_type: AkSyncType = AkSyncType.Immediate
    clue_filter_hash: int = 0
    play_post_exit: int = 0


@dataclass
class AkMusicTransDstRule:
    transition_time: int = 0
    fade_curve: AkCurveInterpolation = AkCurveInterpolation.Constant
    fade_offet: int = 0
    clue_filter_hash: int = 0
    jump_to_id: int = 0
    jump_to_type: int = 0
    entry_type: int = 0
    play_pre_entry: int = 0
    destination_match_source_cue_name: int = 0


@dataclass
class AkMusicTransitionRule:
    source_transition_rule_count: int = 0
    source_ids: list[int] = field(default_factory=list)
    destination_transition_rule_count: int = 0
    destination_ids: list[int] = field(default_factory=list)
    source_transition_rule: AkMusicTransSrcRule = field(
        default_factory=AkMusicTransSrcRule
    )
    destination_transition_rule: AkMusicTransDstRule = field(
        default_factory=AkMusicTransDstRule
    )
    alloc_trans_object_flag: int = 0
    transition_object: Optional[AkMusicTransitionObject] = None


@dataclass
class AkRTPCGraphPoint:
    from_: float
    to: float
    interpolation: AkCurveInterpolation = AkCurveInterpolation.Linear


@dataclass
class ObsOccCurve:
    curve_enabled: int = 0
    curve_scaling: int = 0
    point_count: int = 0
    points: list[AkRTPCGraphPoint] = field(default_factory=list)


@dataclass
class ConversionTable:
    curve_obs_vol: ObsOccCurve = field(default_factory=ObsOccCurve)
    curve_obs_lpf: ObsOccCurve = field(default_factory=ObsOccCurve)
    curve_obs_hpf: ObsOccCurve = field(default_factory=ObsOccCurve)
    curve_occ_vol: ObsOccCurve = field(default_factory=ObsOccCurve)
    curve_occ_lpf: ObsOccCurve = field(default_factory=ObsOccCurve)
    curve_occ_hpf: ObsOccCurve = field(default_factory=ObsOccCurve)


@dataclass
class IAkPlugin:
    plugin_id: PluginId
    dll_name_length: int = 0
    dll_name: str = ""


@dataclass
class AkStateTransition:
    from_state: int = 0
    to_state: int = 0
    transition_time: int = 0


@dataclass
class AkSwitchGraphPoint:
    rtpc_value: float
    switch: int
    curve_shape: int


@dataclass
class StateGroup:
    id: int
    default_transition_time: int = 0
    transition_count: int = 0
    transitions: list[AkStateTransition] = field(default_factory=list)


@dataclass
class SwitchGroup:
    id: int
    rtpc_id: int = 0
    rtpc_type: int = 0
    graph_point_count: int = 0
    graph_points: list[AkSwitchGraphPoint] = field(default_factory=list)


@dataclass
class RTPCRamping:
    rtpc_id: int
    value: int = 0
    ramp_type: int = 0
    ramp_up: float = 0.0
    ramp_down: float = 0.0
    bind_to_built_in_param: int = 0


@dataclass
class AkAcousticTexture:
    id: int
    absorption_offset: float = 0.0
    absorption_low: float = 0.0
    absorption_mid_low: float = 0.0
    absorption_mid_high: float = 0.0
    absorption_high: float = 0.0
    scattering: float = 0.0


@dataclass
class FXChunk:
    fx_index: int
    fx_id: int
    is_share_set: int = 0
    is_rendered: int = 0


@dataclass
class PropRangedModifier:
    prop_type: int
    min: float = 0.0
    max: float = 0.0


@dataclass
class PropRangedModifiers:
    count: int = 0
    entries: list[PropRangedModifier] = field(default_factory=list)


@dataclass
class AkPathVertex:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    duration: int = 0


@dataclass
class AkPathListItemOffset:
    vertices_offset: int
    vertices_count: int


@dataclass
class Ak3DAutomationParams:
    range_x: float = 0.0
    range_y: float = 0.0
    range_z: float = 0.0


@dataclass
class PositioningParams:
    unk1: bool = False
    three_dimensional_position_type: Ak3DPositionType = Ak3DPositionType.Emitter
    speaker_panning_type: AkSpeakerPanningType = (
        AkSpeakerPanningType.DirectSpeakerAssignment
    )
    listener_relative_routing: bool = False
    override_parent: bool = False
    unk2: bool = False
    enable_diffraction: bool = False
    hold_listener_orientation: bool = False
    hold_emitter_position_and_orientation: bool = False
    enable_attenuation: bool = False
    three_dimensional_spatialization_mode: Ak3DSpatializationMode = (
        Ak3DSpatializationMode.Nothing
    )
    path_mode: AkPathMode = AkPathMode.StepSequence
    transition_time: int = 0
    vertex_count: int = 0
    vertices: list[AkPathVertex] = field(default_factory=list)
    path_list_item_count: int = 0
    path_list_item_offsets: list[AkPathListItemOffset] = field(default_factory=list)
    three_dimensional_automation_params: list[Ak3DAutomationParams] = field(
        default_factory=list
    )


@dataclass
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


@dataclass
class AdvSettingsParams:
    unk1: bool = False
    unk2: bool = False
    unk3: bool = False
    is_virtual_voices_opt_override_parent: bool = False
    ignore_parent_maximum_instances: bool = False
    unk4: bool = False
    use_virtual_behavior: bool = False
    kill_newest: bool = False
    virtual_queue_behavior: AkVirtualQueueBehavior = (
        AkVirtualQueueBehavior.PlayFromBeginning
    )
    max_instance_count: int = 0
    below_threshold_behavior: AkBelowThresholdBehavior = (
        AkBelowThresholdBehavior.ContinueToPlay
    )
    unk5: bool = False
    unk6: bool = False
    unk7: bool = False
    unk8: bool = False
    enable_envelope: bool = False
    normalize_loudness: bool = False
    override_analysis: bool = False
    override_hdr_envelope: bool = False


@dataclass
class AkState:
    state_id: int
    state_instance_id: int


@dataclass
class AkStatePropertyInfo:
    property: AkPropID
    accum_type: AkRtpcAccum = AkRtpcAccum.Nothing
    in_db: int = 0


@dataclass
class AkStateGroupChunk:
    state_group_id: int
    sync_type: AkSyncTypeU8 = AkSyncTypeU8.Immediate
    state_count: int = 0
    states: list[AkState] = field(default_factory=list)


@dataclass
class StateChunk:
    state_property_count: int = 0
    state_property_info: list[AkStatePropertyInfo] = field(default_factory=list)
    state_group_count: int = 0
    state_group_chunks: list[AkStateGroupChunk] = field(default_factory=list)


@dataclass
class RTPC:
    id: int
    rtpc_type: AkRtpcType = AkRtpcType.GameParameter
    rtpc_accum: AkRtpcAccum = AkRtpcAccum.Nothing
    param_id: int = 0
    curve_id: int = 0
    curve_scaling: AkCurveScaling = AkCurveScaling.Nothing
    graph_point_count: int = 0
    graph_points: list[AkRTPCGraphPoint] = field(default_factory=list)


@dataclass
class InitialRTPC:
    count: int = 0
    rtpcs: list[RTPC] = field(default_factory=list)


@dataclass
class NodeInitialFxParams:
    is_override_parent_fx: int = 0
    fx_chunk_count: int = 0
    fx_bypass_bits: int = 0
    fx_chunks: list[FXChunk] = field(default_factory=list)


@dataclass
class PropBundle:
    prop_id: AkPropID
    value: float = 0.0


@dataclass
class NodeInitialParams:
    prop_initial_values: list[PropBundle] = field(default_factory=list)
    prop_ranged_modifiers: PropRangedModifiers = field(
        default_factory=PropRangedModifiers
    )


@dataclass
class AkPropBundleByte:
    count: int = 0
    types: list[AkPropID] = field(default_factory=list)
    values: list[float] = field(default_factory=list)


@dataclass
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


@dataclass
class AkMediaInformation:
    source_id: int
    in_memory_media_size: int = 0
    source_flags: int = 0


@dataclass
class AkBankSourceData:
    plugin: PluginId
    source_type: SourceType = SourceType.Embedded
    media_information: AkMediaInformation = field(
        default_factory=lambda: AkMediaInformation(source_id=0)
    )
    params_size: int = 0
    params: list[int] = field(default_factory=list)


@dataclass
class AkMediaMap:
    index: int
    source_id: int


@dataclass
class PluginPropertyValue:
    property: AkParameterID
    rtpc_accum: AkRtpcAccum = AkRtpcAccum.Nothing
    value: float = 0.0


@dataclass
class FxBaseInitialValues:
    fx_id: int
    params_size: int = 0
    params: list[int] = field(default_factory=list)
    media_count: int = 0
    media: list[AkMediaMap] = field(default_factory=list)
    initial_rtpc: InitialRTPC = field(default_factory=InitialRTPC)
    state_chunk: StateChunk = field(default_factory=StateChunk)
    property_value_count: int = 0
    property_values: list[PluginPropertyValue] = field(default_factory=list)


@dataclass
class AkDuckInfo:
    bus_id: int
    duck_volume: float = 0.0
    fade_out_time: int = 0
    fade_in_time: int = 0
    fade_curve: AkCurveInterpolation = AkCurveInterpolation.Linear
    target_prop: AkPropID = AkPropID.Volume


@dataclass
class BusInitialParams:
    prop_bundle: list[PropBundle] = field(default_factory=list)
    positioning_params: PositioningParams = field(default_factory=PositioningParams)
    aux_params: AuxParams = field(default_factory=AuxParams)
    flags: int = 0
    max_instance_count: int = 0
    channel_config: int = 0
    hdr_flags: int = 0


@dataclass
class BusInitialFxParams:
    fx_count: int = 0
    fx_bypass: int = 0
    fx: list[FXChunk] = field(default_factory=list)
    fx_id_0: int = 0
    is_share_set_0: int = 0


@dataclass
class BusInitialValues:
    override_bus_id: int = 0
    device_share_set_id: int = 0
    bus_initial_params: BusInitialParams = field(default_factory=BusInitialParams)
    recovery_time: int = 0
    max_duck_volume: float = 0.0
    duck_count: int = 0
    ducks: list[AkDuckInfo] = field(default_factory=list)
    bus_initial_fx_params: BusInitialFxParams = field(
        default_factory=BusInitialFxParams
    )
    override_attachment_params: int = 0
    initial_rtpc: InitialRTPC = field(default_factory=InitialRTPC)
    state_chunk: StateChunk = field(default_factory=StateChunk)


@dataclass
class SwitchPackage:
    switch_id: int
    node_count: int = 0
    nodes: list[int] = field(default_factory=list)


@dataclass
class AkSwitchNodeParams:
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


@dataclass
class Children:
    count: int = 0
    items: list[int] = field(default_factory=list)


@dataclass
class PlaylistItem:
    play_id: int
    weight: int = 50


@dataclass
class Playlist:
    count: int = 0
    items: list[PlaylistItem] = field(default_factory=list)


@dataclass
class ConeParams:
    inside_degrees: float = 0.0
    outside_degrees: float = 0.0
    outside_volume: float = 0.0
    low_pass: float = 0.0
    high_pass: float = 0.0


@dataclass
class AkConversionTable:
    curve_scaling: AkCurveScaling = AkCurveScaling.Nothing
    point_count: int = 0
    points: list[AkRTPCGraphPoint] = field(default_factory=list)


@dataclass
class AkMeterInfo:
    grid_period: float = 0.0
    grid_offset: float = 0.0
    tempo: float = 120.0
    time_signature_beat_count: int = 4
    time_signature_beat_value: int = 4
    meter_info_flag: int = 0


@dataclass
class Stinger:
    trigger_id: int
    segment_id: int
    sync_play_at: AkSyncType = AkSyncType.Immediate
    cue_filter_hash: int = 0
    dont_repeat_time: int = 0
    segment_look_head_count: int = 0


@dataclass
class MusicNodeParams:
    flags: int = 0
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    children: Children = field(default_factory=Children)
    meter_info: AkMeterInfo = field(default_factory=AkMeterInfo)
    stinger_count: int = 0
    stingers: list[Stinger] = field(default_factory=list)


@dataclass
class AkMusicMarkerWwise:
    id: int
    position: float = 0.0
    string_length: int = 0
    string: str = ""


@dataclass
class AkClipAutomation:
    clip_index: int
    auto_type: AkClipAutomationType = AkClipAutomationType.Volume
    graph_point_count: int = 0
    graph_points: list[AkRTPCGraphPoint] = field(default_factory=list)


@dataclass
class AkTrackSrcInfo:
    track_id: int
    source_id: int
    event_id: int = 0
    play_at: float = 0.0
    begin_trim_offset: float = 0.0
    end_trim_offset: float = 0.0
    source_duration: float = 0.0


@dataclass
class MusicTransNodeParams:
    music_node_params: MusicNodeParams = field(default_factory=MusicNodeParams)
    transition_rule_count: int = 0
    transition_rules: list[AkMusicTransitionRule] = field(default_factory=list)


@dataclass
class AkMusicRanSeqPlaylistItem:
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


@dataclass
class AssociatedChildData:
    associated_child_id: int
    graph_point_count: int = 0
    graph_points: list[AkRTPCGraphPoint] = field(default_factory=list)


@dataclass
class AkLayer:
    layer_id: int
    initial_rtpc: InitialRTPC = field(default_factory=InitialRTPC)
    rtpc_id: int = 0
    rtpc_type: AkRtpcType = AkRtpcType.GameParameter
    associated_childen_count: int = 0
    associated_children: list[AssociatedChildData] = field(default_factory=list)

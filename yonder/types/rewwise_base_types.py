from __future__ import annotations
from typing import Optional
from dataclasses import dataclass, field

from .rewwise_enums import (
    CurveInterpolation,
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


@dataclass
class GameSync:
    group_id: int


@dataclass
class DecisionTreeNode:
    key: int
    node_id: int
    first_child_index: int = 0
    child_count: int = 0
    weight: int = 50
    probability: int = 100
    children: list[DecisionTreeNode] = field(default_factory=list)

    def validate(self) -> None:
        self.children.sort(key=lambda x: x.key)


@dataclass
class MusicFade:
    transition_time: int = 0
    curve: CurveInterpolation = CurveInterpolation.Constant
    offset: int = 0


@dataclass
class MusicTransitionObject:
    segment_id: int = 0
    fade_out: MusicFade = field(default_factory=MusicFade)
    fade_in: MusicFade = field(default_factory=MusicFade)
    play_pre_entry: int = 0
    play_post_exit: int = 0


@dataclass
class MusicTransSrcRule:
    transition_time: int = 0
    fade_curve: CurveInterpolation = CurveInterpolation.Constant
    fade_offet: int = 0
    sync_type: SyncType = SyncType.Immediate
    clue_filter_hash: int = 0
    play_post_exit: int = 0


@dataclass
class MusicTransDstRule:
    transition_time: int = 0
    fade_curve: CurveInterpolation = CurveInterpolation.Constant
    fade_offet: int = 0
    clue_filter_hash: int = 0
    jump_to_id: int = 0
    jump_to_type: int = 0
    entry_type: int = 0
    play_pre_entry: int = 0
    destination_match_source_cue_name: int = 0


@dataclass
class MusicTransitionRule:
    source_transition_rule_count: int = 0
    source_ids: list[int] = field(default_factory=list)
    destination_transition_rule_count: int = 0
    destination_ids: list[int] = field(default_factory=list)
    source_transition_rule: MusicTransSrcRule = field(default_factory=MusicTransSrcRule)
    destination_transition_rule: MusicTransDstRule = field(
        default_factory=MusicTransDstRule
    )
    alloc_trans_object_flag: int = 0
    transition_object: Optional[MusicTransitionObject] = None


@dataclass
class RTPCGraphPoint:
    from_: float
    to: float
    interpolation: CurveInterpolation = CurveInterpolation.Linear


@dataclass
class ObsOccCurve:
    curve_enabled: int = 0
    curve_scaling: int = 0
    point_count: int = 0
    points: list[RTPCGraphPoint] = field(default_factory=list)


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
class StateTransition:
    from_state: int = 0
    to_state: int = 0
    transition_time: int = 0


@dataclass
class SwitchGraphPoint:
    rtpc_value: float
    switch: int
    curve_shape: int


@dataclass
class StateGroup:
    id: int
    default_transition_time: int = 0
    transition_count: int = 0
    transitions: list[StateTransition] = field(default_factory=list)


@dataclass
class SwitchGroup:
    id: int
    rtpc_id: int = 0
    rtpc_type: int = 0
    graph_point_count: int = 0
    graph_points: list[SwitchGraphPoint] = field(default_factory=list)


@dataclass
class RTPCRamping:
    rtpc_id: int
    value: int = 0
    ramp_type: int = 0
    ramp_up: float = 0.0
    ramp_down: float = 0.0
    bind_to_built_in_param: int = 0


@dataclass
class AcousticTexture:
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
class PathVertex:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    duration: int = 0


@dataclass
class PathListItemOffset:
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
        ThreeDSpatializationMode.Nothing
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


@dataclass
class AkState:
    state_id: int
    state_instance_id: int


@dataclass
class AkStatePropertyInfo:
    property: PropID
    accum_type: RtpcAccum = RtpcAccum.Nothing
    in_db: int = 0


@dataclass
class AkStateGroupChunk:
    state_group_id: int
    sync_type: SyncType = SyncType.Immediate
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
    rtpc_type: RtpcType = RtpcType.GameParameter
    rtpc_accum: RtpcAccum = RtpcAccum.Nothing
    param_id: int = 0
    curve_id: int = 0
    curve_scaling: CurveScaling = CurveScaling.Nothing
    graph_point_count: int = 0
    graph_points: list[RTPCGraphPoint] = field(default_factory=list)


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
    prop_id: PropID
    value: float = 0.0


@dataclass
class NodeInitialParams:
    prop_initial_values: list[PropBundle] = field(default_factory=list)
    prop_ranged_modifiers: PropRangedModifiers = field(
        default_factory=PropRangedModifiers
    )


@dataclass
class PropBundleByte:
    count: int = 0
    types: list[PropID] = field(default_factory=list)
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
class MediaInformation:
    source_id: int
    in_memory_media_size: int = 0
    source_flags: int = 0


@dataclass
class BankSourceData:
    plugin: PluginId
    source_type: SourceType = SourceType.Embedded
    media_information: MediaInformation = field(
        default_factory=lambda: MediaInformation(source_id=0)
    )
    params_size: int = 0
    params: list[int] = field(default_factory=list)


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
    ducks: list[DuckInfo] = field(default_factory=list)
    bus_initial_fx_params: BusInitialFxParams = field(
        default_factory=BusInitialFxParams
    )
    override_attachment_params: int = 0
    initial_rtpc: InitialRTPC = field(default_factory=InitialRTPC)
    state_chunk: StateChunk = field(default_factory=StateChunk)


@dataclass
class MediaMap:
    index: int
    source_id: int


@dataclass
class FxBaseInitialValues:
    fx_id: int
    params_size: int = 0
    params: list[int] = field(default_factory=list)
    media_count: int = 0
    media: list[MediaMap] = field(default_factory=list)
    initial_rtpc: InitialRTPC = field(default_factory=InitialRTPC)
    state_chunk: StateChunk = field(default_factory=StateChunk)
    property_value_count: int = 0
    property_values: list[PluginPropertyValue] = field(default_factory=list)


@dataclass
class PluginPropertyValue:
    property: ParameterID
    rtpc_accum: RtpcAccum = RtpcAccum.Nothing
    value: float = 0.0


@dataclass
class DuckInfo:
    bus_id: int
    duck_volume: float = 0.0
    fade_out_time: int = 0
    fade_in_time: int = 0
    fade_curve: CurveInterpolation = CurveInterpolation.Linear
    target_prop: PropID = PropID.Volume


@dataclass
class Children:
    count: int = 0
    items: list[int] = field(default_factory=list)

    def validate(self) -> None:
        self.items = sorted(set(self.items))
        self.count = len(self.items)


@dataclass
class MeterInfo:
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
    sync_play_at: SyncType = SyncType.Immediate
    cue_filter_hash: int = 0
    dont_repeat_time: int = 0
    segment_look_head_count: int = 0


@dataclass
class MusicNodeParams:
    flags: int = 0
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    children: Children = field(default_factory=Children)
    meter_info: MeterInfo = field(default_factory=MeterInfo)
    stinger_count: int = 0
    stingers: list[Stinger] = field(default_factory=list)


@dataclass
class MusicTransNodeParams:
    music_node_params: MusicNodeParams = field(default_factory=MusicNodeParams)
    transition_rule_count: int = 0
    transition_rules: list[MusicTransitionRule] = field(default_factory=list)

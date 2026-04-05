from __future__ import annotations
from dataclasses import dataclass, field
from field_properties import field_property

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


@dataclass
class GameSync:
    group_id: int


@dataclass
class DecisionTreeNode:
    key: int = 0
    node_id: int = 0
    first_child_index: int = 0
    child_count: int = field_property(init=False, raw=True)
    weight: int = 50
    probability: int = 100
    children: list[DecisionTreeNode] = field(default_factory=list)

    @field_property(child_count)
    def get_child_count(self) -> int:
        return len(self.children)

    def validate(self) -> None:
        self.children.sort(key=lambda x: x.key)

    def get_references(self) -> list[tuple[str, int]]:
        return [("node_id", self.node_id)]


@dataclass
class MusicFade:
    transition_time: int = 0
    curve: CurveInterpolation = CurveInterpolation.Log3
    offset: int = 0


@dataclass
class MusicTransitionObject:
    segment_id: int = 0
    fade_out: MusicFade = field(default_factory=MusicFade)
    fade_in: MusicFade = field(default_factory=MusicFade)
    play_pre_entry: int = 0
    play_post_exit: int = 0

    def get_references(self) -> list[tuple[str, int]]:
        return [("segment_id", self.segment_id)]


@dataclass
class MusicTransSrcRule:
    transition_time: int = 0
    fade_curve: CurveInterpolation = CurveInterpolation.Linear
    fade_offet: int = 0  # TODO typo in bnk2json
    sync_type: SyncType = SyncType.Immediate
    clue_filter_hash: int = 0
    play_post_exit: int = 0


@dataclass
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


@dataclass
class MusicTransitionRule:
    source_transition_rule_count: int = field_property(init=False, raw=True)
    source_ids: list[int] = field(default_factory=lambda: [-1])
    destination_transition_rule_count: int = field_property(init=False, raw=True)
    destination_ids: list[int] = field(default_factory=lambda: [-1])
    source_transition_rule: MusicTransSrcRule = field(default_factory=MusicTransSrcRule)
    destination_transition_rule: MusicTransDstRule = field(
        default_factory=MusicTransDstRule
    )
    alloc_trans_object_flag: int = 0
    transition_object: MusicTransitionObject = field(
        default_factory=MusicTransitionObject
    )

    @field_property(source_transition_rule_count)
    def get_source_transition_rule_count(self) -> int:
        return len(self.source_ids)

    @field_property(destination_transition_rule_count)
    def get_destination_transition_rule_count(self) -> int:
        return len(self.destination_ids)

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


@dataclass
class RTPCGraphPoint:
    from_: float = 0.0
    to: float = 0.0
    interpolation: CurveInterpolation = CurveInterpolation.Linear

    @property
    def coords(self) -> tuple[float, float]:
        return (self.from_, self.to)


@dataclass
class ConversionTable:
    curve_scaling: CurveScaling = CurveScaling.None_
    point_count: int = field_property(init=False, raw=True)
    points: list[RTPCGraphPoint] = field(default_factory=list)

    @field_property(point_count)
    def get_point_count(self) -> int:
        return len(self.points)


@dataclass
class ObsOccCurve:
    curve_enabled: int = 0
    curve_scaling: int = 0
    point_count: int = field_property(init=False, raw=True)
    points: list[RTPCGraphPoint] = field(default_factory=list)

    @field_property(point_count)
    def get_poin_count(self) -> int:
        return len(self.points)


@dataclass
class ObsConversionTable:
    curve_obs_vol: ObsOccCurve = field(default_factory=ObsOccCurve)
    curve_obs_lpf: ObsOccCurve = field(default_factory=ObsOccCurve)
    curve_obs_hpf: ObsOccCurve = field(default_factory=ObsOccCurve)
    curve_occ_vol: ObsOccCurve = field(default_factory=ObsOccCurve)
    curve_occ_lpf: ObsOccCurve = field(default_factory=ObsOccCurve)
    curve_occ_hpf: ObsOccCurve = field(default_factory=ObsOccCurve)


@dataclass
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


@dataclass
class ClipAutomation:
    clip_index: int = 0
    auto_type: ClipAutomationType = ClipAutomationType.Volume
    graph_point_count: int = field_property(init=False, raw=True)
    graph_points: list[RTPCGraphPoint] = field(default_factory=list)

    @field_property(graph_point_count)
    def get_graph_point_count(self) -> int:
        return len(self.graph_points)


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
    rtpc_value: float = 0.0
    switch: int = 0
    curve_shape: int = 0


@dataclass
class StateGroup:
    id: int = 0
    default_transition_time: int = 0
    transition_count: int = field_property(init=False, raw=True)
    transitions: list[StateTransition] = field(default_factory=list)

    @field_property(transition_count)
    def get_transition_count(self) -> int:
        return len(self.transitions)


@dataclass
class SwitchGroup:
    id: int = 0
    rtpc_id: int = 0
    rtpc_type: int = 0
    graph_point_count: int = field_property(init=False, raw=True)
    graph_points: list[SwitchGraphPoint] = field(default_factory=list)

    @field_property(graph_point_count)
    def get_graph_point_count(self) -> int:
        return len(self.graph_points)


@dataclass
class RTPCRamping:
    rtpc_id: int = 0
    value: int = 0
    ramp_type: int = 0
    ramp_up: float = 0.0
    ramp_down: float = 0.0
    bind_to_built_in_param: int = 0


@dataclass
class AcousticTexture:
    id: int = 0
    absorption_offset: float = 0.0
    absorption_low: float = 0.0
    absorption_mid_low: float = 0.0
    absorption_mid_high: float = 0.0
    absorption_high: float = 0.0
    scattering: float = 0.0


@dataclass
class FXChunk:
    fx_index: int = 0
    fx_id: int = 0
    is_share_set: int = 0
    is_rendered: int = 0

    def get_references(self) -> list[tuple[str, int]]:
        return [("fx_id", self.fx_id)]


@dataclass
class PropRangedModifier:
    prop_type: int = 0
    min: float = 0.0
    max: float = 0.0


@dataclass
class PropRangedModifiers:
    count: int = field_property(init=False, raw=True)
    entries: list[PropRangedModifier] = field(default_factory=list)

    @field_property(count)
    def get_count(self) -> int:
        return len(self.entries)


@dataclass
class PathVertex:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    duration: int = 0


@dataclass
class PathListItemOffset:
    vertices_offset: int = 0
    vertices_count: int = 0


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
        ThreeDSpatializationMode.None_
    )
    path_mode: PathMode = PathMode.StepSequence
    transition_time: int = 0
    vertex_count: int = field_property(init=False, raw=True)
    vertices: list[PathVertex] = field(default_factory=list)
    path_list_item_count: int = field_property(init=False, raw=True)
    path_list_item_offsets: list[PathListItemOffset] = field(default_factory=list)
    three_dimensional_automation_params: list[Ak3DAutomationParams] = field(
        default_factory=list
    )

    @field_property(vertex_count)
    def get_vertex_count(self) -> int:
        return len(self.vertices)

    @field_property(path_list_item_count)
    def get_path_list_item_count(self) -> int:
        return len(self.path_list_item_offsets)


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

    def get_references(self) -> list[tuple[str, int]]:
        return [
            ("aux1", self.aux1),
            ("aux2", self.aux2),
            ("aux3", self.aux3),
            ("aux4", self.aux4),
            ("reflection_aux_bus", self.reflection_aux_bus),
        ]


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
    state_id: int = 0
    state_instance_id: int = 0

    def get_references(self) -> list[tuple[str, int]]:
        # TODO not sure about this one
        return [("state_id", self.state_id)]


@dataclass
class StatePropertyInfo:
    property: PropID = PropID.Volume
    accum_type: RtpcAccum = RtpcAccum.None_
    in_db: int = 0


@dataclass
class StateGroupChunk:
    state_group_id: int = 0
    sync_type: SyncType = SyncType.Immediate
    state_count: int = field_property(init=False, raw=True)
    states: list[AkState] = field(default_factory=list)

    @field_property(state_count)
    def get_state_count(self) -> int:
        return len(self.states)


@dataclass
class StateChunk:
    state_property_count: int = field_property(init=False, raw=True)
    state_property_info: list[StatePropertyInfo] = field(default_factory=list)
    state_group_count: int = field_property(init=False, raw=True)
    state_group_chunks: list[StateGroupChunk] = field(default_factory=list)

    @field_property(state_property_count)
    def get_state_property_count(self) -> int:
        return len(self.state_property_info)

    @field_property(state_group_count)
    def get_state_group_count(self) -> int:
        return len(self.state_group_chunks)


@dataclass
class RTPC:
    id: int = 0
    rtpc_type: RtpcType = RtpcType.GameParameter
    rtpc_accum: RtpcAccum = RtpcAccum.None_
    param_id: int = 0
    curve_id: int = 0  # TODO seems to be a hash?
    curve_scaling: CurveScaling = CurveScaling.None_
    graph_point_count: int = field_property(init=False, raw=True)
    graph_points: list[RTPCGraphPoint] = field(default_factory=list)

    @field_property(graph_point_count)
    def get_graph_point_count(self) -> int:
        return len(self.graph_points)


@dataclass
class InitialRTPC:
    count: int = field_property(init=False, raw=True)
    rtpcs: list[RTPC] = field(default_factory=list)

    @field_property(count)
    def get_count(self) -> int:
        return len(self.rtpcs)


@dataclass
class NodeInitialFxParams:
    is_override_parent_fx: int = 0
    fx_chunk_count: int = field_property(init=False, raw=True)
    fx_bypass_bits: int = 0
    fx_chunks: list[FXChunk] = field(default_factory=list)

    @field_property(fx_chunk_count)
    def get_fx_chunk_count(self) -> int:
        return len(self.fx_chunks)


@dataclass
class PropBundle:
    prop_id: PropID = PropID.Volume
    value: float = 0.0

    def get_references(self) -> list[tuple[str, int]]:
        if self.prop_id in (PropID.AttachedPluginFXID, PropID.AttenuationID):
            return [("value", int(self.value))]


@dataclass
class NodeInitialParams:
    prop_initial_values: list[PropBundle] = field(default_factory=list)
    prop_ranged_modifiers: PropRangedModifiers = field(
        default_factory=PropRangedModifiers
    )

    # TODO might also use attenuation or FX but enum is not known atm


@dataclass
class PropBundleByte:
    count: int = field_property(init=False, raw=True)
    types: list[PropID] = field(default_factory=list)
    values: list[float] = field(default_factory=list)

    @field_property(count)
    def get_count(self) -> int:
        return len(self.values)

    def validate(self) -> None:
        if len(self.types) != len(self.values):
            raise ValueError("types and values must be the same length")


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

    def get_references(self) -> list[tuple[str, int]]:
        return [("override_bus_id", self.override_bus_id)]


@dataclass
class MediaInformation:
    source_id: int = 0
    in_memory_media_size: int = 0
    source_flags: int = 0

    def get_references(self) -> list[tuple[str, int]]:
        # May match an fx effect
        return [("source_id", self.source_id)]


@dataclass
class BankSourceData:
    plugin: PluginId = PluginId.VORBIS
    source_type: SourceType = SourceType.Embedded
    media_information: MediaInformation = field(
        default_factory=lambda: MediaInformation(source_id=0)
    )
    params_size: int = field_property(init=False, raw=True)
    params: list[int] = field(default_factory=list)

    @field_property(params_size)
    def get_params_size(self) -> int:
        return len(self.params)


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
    fx_count: int = field_property(init=False, raw=True)
    fx_bypass: int = 0
    fx: list[FXChunk] = field(default_factory=list)
    fx_id_0: int = 0
    is_share_set_0: int = 0

    @field_property(fx_count)
    def get_fx_count(self) -> int:
        return len(self.fx)

    def get_references(self) -> list[tuple[str, int]]:
        return [("fx_id_0", self.fx_id_0)]


@dataclass
class BusInitialValues:
    override_bus_id: int = 0
    device_share_set_id: int = 0
    bus_initial_params: BusInitialParams = field(default_factory=BusInitialParams)
    recovery_time: int = 0
    max_duck_volume: float = 0.0
    duck_count: int = field_property(init=False, raw=True)
    ducks: list[DuckInfo] = field(default_factory=list)
    bus_initial_fx_params: BusInitialFxParams = field(
        default_factory=BusInitialFxParams
    )
    override_attachment_params: int = 0
    initial_rtpc: InitialRTPC = field(default_factory=InitialRTPC)
    state_chunk: StateChunk = field(default_factory=StateChunk)

    @field_property(duck_count)
    def get_duck_count(self) -> int:
        return len(self.ducks)

    def get_references(self) -> list[tuple[str, int]]:
        return [
            ("override_bus_id", self.override_bus_id),
            ("device_share_set_id", self.device_share_set_id),
        ]


@dataclass
class MediaMap:
    index: int = 0
    source_id: int = 0

    def get_references(self) -> list[tuple[str, int]]:
        # Usually not a reference, but might be paired with an effect
        return [("source_id", self.source_id)]


@dataclass
class FxBaseInitialValues:
    fx_id: int = 0
    params_size: int = field_property(init=False, raw=True)
    params: list[int] = field(default_factory=list)
    media_count: int = field_property(init=False, raw=True)
    media: list[MediaMap] = field(default_factory=list)
    initial_rtpc: InitialRTPC = field(default_factory=InitialRTPC)
    state_chunk: StateChunk = field(default_factory=StateChunk)
    property_value_count: int = field_property(init=False, raw=True)
    property_values: list[PluginPropertyValue] = field(default_factory=list)

    @field_property(params_size)
    def get_params_size(self) -> int:
        return len(self.params)

    @field_property(media_count)
    def get_media_count(self) -> int:
        return len(self.media)

    @field_property(property_value_count)
    def get_property_value_count(self) -> int:
        return len(self.property_values)


@dataclass
class PluginPropertyValue:
    property: ParameterID = ParameterID.Volume
    rtpc_accum: RtpcAccum = RtpcAccum.None_
    value: float = 0.0


@dataclass
class DuckInfo:
    bus_id: int = 0
    duck_volume: float = 0.0
    fade_out_time: int = 0
    fade_in_time: int = 0
    fade_curve: CurveInterpolation = CurveInterpolation.Linear
    target_prop: PropID = PropID.Volume

    def get_references(self) -> list[tuple[str, int]]:
        return [("bus_id", self.bus_id)]


@dataclass
class Children:
    count: int = field_property(init=False, raw=True)
    items: list[int] = field(default_factory=list)

    @field_property(count)
    def get_count(self) -> int:
        return len(self.items)

    def validate(self) -> None:
        self.items = sorted(set(self.items))
        self.count = len(self.items)

    def get_references(self) -> list[tuple[str, int]]:
        return [("items", self.items)]


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
    trigger_id: int = 0
    segment_id: int = 0
    sync_play_at: SyncType = SyncType.Immediate
    cue_filter_hash: int = 0
    dont_repeat_time: int = 0
    segment_look_head_count: int = 0

    def get_references(self) -> list[tuple[str, int]]:
        return [("segment_id", self.segment_id)]


@dataclass
class MusicNodeParams:
    flags: int = 0
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    children: Children = field(default_factory=Children)
    meter_info: MeterInfo = field(default_factory=MeterInfo)
    stinger_count: int = field_property(init=False, raw=True)
    stingers: list[Stinger] = field(default_factory=list)

    @field_property(stinger_count)
    def get_stinger_count(self) -> int:
        return len(self.stingers)


@dataclass
class MusicTransNodeParams:
    music_node_params: MusicNodeParams = field(default_factory=MusicNodeParams)
    transition_rule_count: int = field_property(init=False, raw=True)
    transition_rules: list[MusicTransitionRule] = field(default_factory=list)

    @field_property(transition_rule_count)
    def get_transition_rule_count(self) -> int:
        return len(self.transition_rules)

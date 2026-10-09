from dearpygui import dearpygui as dpg

from yonder.util import resource_dir


class Icons:
    ambience = "tex_icon_ambience"
    autoplay = "tex_icon_autoplay"
    aux16 = "tex_icon_aux16"
    batch_sound_builder = "tex_icon_batch_sound_builder"
    blocks_add = "tex_icon_blocks_add"
    bus16 = "tex_icon_bus16"
    close = "tex_icon_close"
    copy = "tex_icon_copy"
    crop = "tex_icon_crop"
    cut = "tex_icon_cut"
    edit = "tex_icon_edit"
    enemy = "tex_icon_enemy"
    equalizer = "tex_icon_equalizer"
    error = "tex_icon_error"
    fast_forward = "tex_icon_fast_forward"
    fast_rewind = "tex_icon_fast_rewind"
    file_new = "tex_icon_file_new"
    file_new_bank = "tex_icon_file_new_bank"
    file_open = "tex_icon_file_open"
    file_save = "tex_icon_file_save"
    forward_10s = "tex_icon_forward_10s"
    forward_30s = "tex_icon_forward_30s"
    game_sync_auto = "tex_icon_game_sync_auto"
    game_sync_once = "tex_icon_game_sync_once"
    hash = "tex_icon_hash"
    help = "tex_icon_help"
    info = "tex_icon_info"
    jump16 = "tex_icon_jump16"
    keyframe = "tex_icon_keyframe"  # TODO size 18 seems good for in-line icons, organize
    link = "tex_icon_link"
    music = "tex_icon_music"
    mute = "tex_icon_mute"
    new_event = "tex_icon_new_event"
    next = "tex_icon_next"
    nothing = "tex_icon_nothing"
    object = "tex_icon_object"
    paste = "tex_icon_paste"
    pause = "tex_icon_pause"
    play = "tex_icon_play"
    play_pause = "tex_icon_play_pause"
    previous = "tex_icon_previous"
    properties16 = "tex_icon_properties16"
    random = "tex_icon_random"
    recording = "tex_icon_recording"
    repack = "tex_icon_repack"
    restore_file = "tex_icon_restore_file"
    rtpc16 = "tex_icon_rtpc16"
    select16 = "tex_icon_select16"
    select_empty = "tex_icon_select_empty"
    select_full = "tex_icon_select_full"
    seek_end = "tex_icon_seek_end"
    seek_zero = "tex_icon_seek_zero"
    settings = "tex_icon_settings"
    sliders = "tex_icon_sliders"
    skip = "tex_icon_skip"
    sound = "tex_icon_sound"
    sound_reset = "tex_icon_sound_reset"
    soundbank = "tex_icon_soundbank"
    spatial3d = "tex_icon_spatial3d"
    states = "tex_icon_states"
    states16 = "tex_icon_states16"
    stop = "tex_icon_stop"
    swap = "tex_icon_swap"
    swords = "tex_icon_swords"
    tool_convert = "tex_icon_tool_convert"
    tool_export_sounds = "tex_icon_tool_export_sounds"
    tool_mass_transfer = "tex_icon_tool_mass_transfer"
    trash = "tex_icon_trash"
    transition = "tex_icon_transition"
    type_Action = "tex_icon_type_action"
    type_ActorMixer = "tex_icon_type_actor_mixer"
    type_Attenuation = "tex_icon_type_attenuation"
    type_AudioDevice = "tex_icon_type_audio_device"
    type_AuxiliaryBus = "tex_icon_type_auxilliary_bus"
    type_Bus = "tex_icon_type_bus"
    type_DialogueEvent = "tex_icon_type_dialogue_event"
    type_EffectShareSet = "tex_icon_type_effect_share_set"
    type_EffectCustom = "tex_icon_type_effect_custom"
    type_Event = "tex_icon_type_event"
    type_LayerContainer = "tex_icon_type_layer_container"
    type_LFOModulator = "tex_icon_type_lfo_modulator"
    type_MusicRandomSequenceContainer = "tex_icon_type_music_random_sequence_container"
    type_MusicSwitchContainer = "tex_icon_type_music_switch_container"
    type_MusicSegment = "tex_icon_type_music_segment"
    type_MusicTrack = "tex_icon_type_music_track"
    type_RandomSequenceContainer = "tex_icon_type_random_sequence_container"
    type_Sound = "tex_icon_type_sound"
    type_State = "tex_icon_type_state"
    type_SwitchContainer = "tex_icon_type_switch_container"
    type_TimeModulator = "tex_icon_type_time_modulator"
    type_Unknown = "tex_icon_type_unknown"
    volume_down = "tex_icon_volume_down"
    volume_up = "tex_icon_volume_up"
    warning = "tex_icon_warning"
    wave = "tex_icon_wave"
    x = "tex_icon_x"

    @classmethod
    def get_type_icon_tag(cls, node_type: type | str) -> str:
        if isinstance(node_type, type):
            node_type = node_type.__name__

        return getattr(cls, f"type_{node_type}", cls.type_Unknown)


def load_icons():
    res = resource_dir()
    with dpg.texture_registry():
        for key, val in vars(Icons).items():
            if key.startswith("_") or not isinstance(val, str):
                continue

            if not dpg.does_item_exist(val):
                try:
                    filename = val.removeprefix("tex_icon_")
                    tw, th, _, tex = dpg.load_image(str(res / "icons" / f"{filename}.png"))
                    dpg.add_static_texture(tw, th, tex, tag=val)
                except Exception:
                    raise RuntimeError(f"Failed to load icon {key}")

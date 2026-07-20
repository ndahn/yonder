from dearpygui import dearpygui as dpg

from yonder.util import resource_dir


class Icons:
    ambience = "tex_icon_ambience"
    autoplay = "tex_icon_autoplay"
    batch_sound_builder = "tex_icon_batch_sound_builder"
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
    hash = "tex_icon_hash"
    help = "tex_icon_help"
    info = "tex_icon_info"
    music = "tex_icon_music"
    mute = "tex_icon_mute"
    new_event = "tex_icon_new_event"
    next = "tex_icon_next"
    paste = "tex_icon_paste"
    pause = "tex_icon_pause"
    play = "tex_icon_play"
    play_pause = "tex_icon_play_pause"
    previous = "tex_icon_previous"
    repack = "tex_icon_repack"
    seek_end = "tex_icon_seek_end"
    seek_zero = "tex_icon_seek_zero"
    settings = "tex_icon_settings"
    sliders = "tex_icon_sliders"
    sound = "tex_icon_sound"
    sound_reset = "tex_icon_sound_reset"
    soundbank = "tex_icon_soundbank"
    states = "tex_icon_states"
    stop = "tex_icon_stop"
    swap = "tex_icon_swap"
    swords = "tex_icon_swords"
    tool_convert = "tex_icon_tool_convert"
    tool_export_sounds = "tex_icon_tool_export_sounds"
    tool_mass_transfer = "tex_icon_tool_mass_transfer"
    transition = "tex_icon_transition"
    volume_down = "tex_icon_volume_down"
    volume_up = "tex_icon_volume_up"
    warning = "tex_icon_warning"
    wave = "tex_icon_wave"


def load_icons():
    res = resource_dir()
    with dpg.texture_registry():
        for key, val in vars(Icons).items():
            if key.startswith("_") or not isinstance(val, str):
                continue

            if not dpg.does_item_exist(val):
                try:
                    tw, th, _, tex = dpg.load_image(str(res / "icons" / f"{key}.png"))
                    dpg.add_static_texture(tw, th, tex, tag=val)
                except Exception:
                    raise RuntimeError(f"Failed to load icon {key}")

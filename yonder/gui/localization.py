from typing import Any
from dataclasses import dataclass, field


class Localization:
    active_lang: "Localization" = None

    language: str = "English"
    language_alt_name: str = None

    title: str = "Banks of Yonder"

    menu_language: str = "Language"
    language_english: str = "English"
    language_chinese: str = "Chinese"
    language_switched: str = "Language switched to English."
    language_restart_hint: str = "Some labels refresh after reopening windows."

    menu_file: str = "File"
    menu_recent_files: str = "Recent files"
    menu_open: str = "Open..."
    menu_save: str = "Save"
    menu_save_as: str = "Save As..."
    menu_repack: str = "Repack"
    menu_new_soundbank: str = "New Soundbank..."
    menu_bank: str = "Bank"
    menu_pin_orphans: str = "Pin Orphans"
    menu_solve_hirc: str = "Solve HIRC"
    menu_verify: str = "Verify"
    menu_advanced: str = "Advanced"
    menu_delete_unused_wems: str = "Delete unused wems"
    menu_delete_orphans: str = "Delete orphans"
    menu_create: str = "Create"
    menu_simple_sound: str = "Simple Sound"
    menu_batch_sound_builder: str = "Batch Sound Builder"
    menu_boss_track: str = "Boss Track"
    menu_ambience_track: str = "Ambience Track"
    menu_new_wwise_event: str = "New Wwise Event"
    menu_tools: str = "Tools"
    menu_calc_hash: str = "Calc Hash"
    menu_mass_transfer: str = "Mass Transfer"
    menu_export_sounds: str = "Export Sounds"
    menu_waves_to_wems: str = "Waves to Wems"
    menu_yonder: str = "Yonder"
    menu_dearpygui: str = "DearPyGui"
    menu_dpg_about: str = "About"
    menu_dpg_metrics: str = "Metrics"
    menu_dpg_docs: str = "Documentation"
    menu_dpg_debug: str = "Debug"
    menu_dpg_style_editor: str = "Style Editor"
    menu_dpg_font_manager: str = "Font Manager"
    menu_dpg_item_registry: str = "Item Registry"
    menu_dpg_stack_tool: str = "Stack Tool"
    menu_settings: str = "Settings"
    menu_about: str = "About"

    tab_events: str = "Events"
    tab_globals: str = "Globals"
    hint_search_on_enter: str = "Search on enter"
    showing_events: str = "Showing {shown}/{total} events"
    showing_globals: str = "Showing {shown}/{total} globals"
    table_node: str = "Node"
    pinned_nodes: str = "Pinned Nodes"
    json_apply: str = "Apply"
    json_reload: str = "Reload Json"
    json_reset: str = "Reset Node"

    context_new_child: str = "New child"
    context_add_action: str = "Add action"
    context_action_play: str = "Play"
    context_action_event: str = "Event"
    context_action_stop: str = "Stop"
    context_action_mute_bus: str = "Mute Bus"
    context_action_reset_bus_volume: str = "Reset Bus Volume"
    context_show_graph: str = "Show Graph"
    context_pin: str = "Pin"
    context_cut: str = "Cut"
    context_copy: str = "Copy"
    context_paste_child: str = "Paste child"
    context_delete: str = "Delete"
    context_unpin: str = "Unpin"
    context_unpin_all: str = "Unpin All"
    context_jump_to: str = "Jump To"

    open: str = "Open Soundbank"
    save_soundbank: str = "Save Soundbank"
    soundbank_files: str = "Soundbanks (.bnk)"
    json_files: str = "JSON (.json)"
    all_files: str = "All files"
    choose_empty_directory: str = "Choose Empty Directory"
    error_directory_not_empty: str = "Directory not empty"
    loading_saving_soundbank: str = "Saving soundbank..."
    loading_repacking: str = "Repacking..."
    loading_unpacking: str = "Unpacking..."
    loading_loading_soundbank: str = "Loading soundbank..."
    loading_solving: str = "Solving..."
    loading_verifying: str = "Verifying..."
    choice_unpacked_msg: str = (
        "Soundbank {name} was already unpacked. Open the json instead?"
    )
    choice_open_json: str = "Open json"
    choice_unpack_again: str = "Unpack again"
    choice_bnk_or_json: str = "Bnk or json?"
    choice_save_before_open: str = "Save soundbank {name} first?"
    choice_just_do_it: str = "Just do it"
    choice_continue: str = "Continue?"

    settings_window: str = "Settings"
    save: str = "Save"
    calc_hash_window: str = "Calc Hash"
    calc_hash_help: str = "Calculates an FNV-1a 32bit hash"
    mass_transfer_window: str = "Transfer Sounds"
    convert_wavs_window: str = "Convert Wave Files"
    export_sounds_window: str = "Export Soundbank Sounds"
    about_window: str = "About"

    source_bank_label: str = "Source Soundbank"
    dest_bank_label: str = "Destination Soundbank"
    source_ids_label: str = "Source Wwise IDs"
    dest_ids_label: str = "Destination Wwise IDs"
    select_ids_button: str = "Select IDs..."
    swap_banks_button: str = "Swap Banks"
    swap_ids_button: str = "Swap IDs"
    transfer_button: str = "Start Transfer"
    repack_button: str = "Repack"
    select_source_first: str = "Select source bank first"
    error_source_not_set: str = "No source bank selected"
    error_dest_not_set: str = "No destination bank selected"
    error_no_lines: str = "No source IDs selected"
    error_line_mismatch: str = "Source and destination IDs not balanced"
    error_dest_ids_no_hash: str = "Destination IDs cannot be hashes"
    error_explicit_implicit_mismatch: str = (
        "Cannot pair explicit with implicit event names"
    )
    error_source_id_not_found: str = "{line} not found in source bank"
    error_dest_id_exists: str = "{line} already exists in destination bank"
    transfer_successful: str = "Transfer successful"
    transfer_help_text: str = (
        "- Transfer sound structures between soundbanks\n"
        "- Specify by full name (Play_x123456789), hash (#102591249), or wwise name (x123456789)\n"
        "- Wwise names will be resolved to Play_ and Stop_ events\n"
        "- You cannot pair a name/hash with a wwise name"
    )
    error_bnk2json_required: str = "bnk2json is required for repacking"
    error_bnk2json_failed: str = "bnk2json failed, check logs!"

    convert_wave_files: str = "Wave files"
    convert_output_dir: str = "Output dir"
    convert_target_volume: str = "Target volume"
    convert_silence_threshold: str = "Silence threshold"
    convert_snippet_length: str = "Snippet length"
    convert_to_wem: str = "Convert to .wem"
    convert_no_wave_files: str = "No wave files selected"
    convert_invalid_output_dir: str = "Invalid output directory"
    convert_wwise_not_found: str = "Wwise exe not found"
    convert_loading: str = "Converting..."
    convert_loading_trim: str = "Trimming silence..."
    convert_loading_snippet: str = "Creating prefetch snippets..."
    convert_loading_volume: str = "Adjusting volume..."
    convert_loading_wem: str = "Converting waves..."
    convert_done: str = "Done!"
    convert_again: str = "Again?"
    convert_start_button: str = "Convert"

    export_soundbank_label: str = "Soundbank"
    export_output_dir: str = "Output dir"
    export_full_streamed: str = "Export full sounds for streamed"
    export_convert_wav: str = "Convert to wav"
    export_no_soundbank: str = "No soundbank loaded"
    export_invalid_output_dir: str = "Invalid output directory"
    export_loading: str = "Converting..."
    export_done: str = "Done!"
    export_again: str = "Again?"
    export_start_button: str = "Export"

    about_written_by: str = "Written by Nikolas Dahn"
    about_bug_report: str = "Bugs, questions, feature requests?"
    about_contact: str = "Find me on Discord @Managarm!"
    browse: str = "Browse"
    okay: str = "Okay"
    cancel: str = "Cancel"

    settings_external_tools: str = "External Tools"
    settings_data_sources: str = "Data Sources"
    settings_bnk2json_tooltip: str = "For unpacking and repacking soundbanks"
    settings_wwise_tooltip: str = "For converting wav to wem"
    settings_vgmstream_tooltip: str = "For converting wem to wav and playback"
    settings_soundbank_folders: str = "Soundbank folders"
    settings_soundbank_folders_tooltip: str = "Used to locate external sounds"
    settings_hash_dictionaries: str = "Hash dictionaries"
    settings_hash_dictionaries_tooltip: str = "Used for reversing hashes"

    new_event_name_label: str = "Name"
    new_event_allow_arbitrary: str = "Allow arbitrary names"
    new_event_target_node: str = "Target node ID"
    new_event_create_play: str = "Create play action"
    new_event_create_stop: str = "Create stop action"
    new_event_create_button: str = "Create"
    new_event_name_required: str = "Name not specified"
    new_event_name_invalid: str = "Name not matching pattern (x123456789)"
    new_event_none_created: str = "No events created"
    new_event_success: str = "Created successfully"
    new_event_again: str = "Again?"

    simple_sound_name_label: str = "Name"
    simple_sound_hash_label: str = "Hash"
    simple_sound_actor_mixer_label: str = "ActorMixer"
    simple_sound_avoid_repeats: str = "Avoid Repeats"
    simple_sound_sounds_label: str = "Sounds"
    simple_sound_add_sound: str = "+ Add Sound"
    simple_sound_source_row: str = "source #{index}"
    simple_sound_create_button: str = "Create"
    simple_sound_name_required: str = "Name not specified"
    simple_sound_name_exists: str = "An event with this name already exists"
    simple_sound_actor_mixer_required: str = "ActorMixer not specified"
    simple_sound_no_sounds: str = "No sounds specified"
    simple_sound_success: str = "Created successfully"
    simple_sound_again: str = "Again?"
    simple_sound_batch_mode: str = "Batch mode"
    simple_sound_type_label: str = "Type"
    simple_sound_import_folder: str = "Import Folder..."
    simple_sound_loaded_count: str = "Loaded {count} audio files"
    simple_sound_batch_success: str = "Batch created: {created}, skipped: {skipped}"
    simple_sound_batch_none_created: str = (
        "No events created (all names already exist?)"
    )
    simple_sound_batch_merge_label: str = "Merge"
    simple_sound_merge_single: str = "Single file per event"
    simple_sound_merge_by_playid: str = "Merge by PlayID"
    simple_sound_merge_by_size: str = "Merge by fixed count"
    simple_sound_merge_size_label: str = "Group size"
    simple_sound_merge_size_invalid: str = "Group size must be >= 1"
    batch_sound_window: str = "Batch Sound Builder"
    batch_sound_groups_label: str = "Groups"
    batch_sound_new_group: str = "+ New Group"
    batch_sound_delete_group: str = "Delete Group"
    batch_sound_group_name: str = "Event Name"
    batch_sound_group_type: str = "Type"
    batch_sound_add_files: str = "Add Files..."
    batch_sound_add_folder: str = "Add Folder..."
    batch_sound_clear_files: str = "Clear Files"
    batch_sound_remove_file: str = "Remove File"
    batch_sound_auto_name: str = "Auto Name"
    batch_sound_files_label: str = "Audio Files ({count})"
    batch_sound_preview_label: str = "Preview"
    batch_sound_create_button: str = "Create All"
    batch_sound_no_groups: str = "No groups configured"
    batch_sound_select_group: str = "Select a group first"
    batch_sound_group_name_required: str = "Group event name is required"
    batch_sound_group_name_exists: str = "Event already exists: {name}"
    batch_sound_group_name_duplicate: str = "Duplicate group event name: {name}"
    batch_sound_group_no_files: str = "Group has no audio files: {name}"
    batch_sound_created_summary: str = "Created {count} groups successfully"
    batch_sound_auto_name_hint: str = (
        "If name is empty, it will use type + first audio ID"
    )
    batch_sound_folder_mode: str = "Folder Import"
    batch_sound_folder_mode_current: str = "Add to current group"
    batch_sound_folder_mode_per_file: str = "One group per file"
    batch_sound_folder_mode_by_prefix: str = "Group by filename prefix"
    batch_sound_folder_import_manual: str = "Manual assignment"
    batch_sound_folder_import_per_file: str = "One group per audio"
    batch_sound_assign_window: str = "Assign Folder Files To Groups"
    batch_sound_assign_hint: str = "Choose a target group for each file, then confirm."
    batch_sound_assign_file_col: str = "File"
    batch_sound_assign_group_col: str = "Target Group"
    batch_sound_assign_confirm: str = "Confirm Import"
    batch_sound_assign_new_group: str = "New Group"
    batch_sound_bulk_type: str = "Bulk Type"
    batch_sound_apply_bulk_type: str = "Apply To All Groups"
    select_folder: str = "Select folder"

    create_node_id_label: str = "ID"
    create_node_window: str = "Create Node"
    create_node_create_button: str = "Create"

    state_path_leaf_not_set: str = "Leaf node ID not set"
    state_path_keys_empty: str = "Keys must not be empty"
    state_path_node_label: str = "Node"
    state_path_window: str = "New State Path"
    select_nodes_filter_hint: str = "Filter..."
    select_nodes_column: str = "Node (id)"
    select_nodes_multi_hint: str = (
        "Hold Ctrl or click multiple rows to select several nodes."
    )

    boss_phase_label_normal: str = "Normal"
    boss_phase_label_heatup: str = "Heatup {phase}"
    boss_no_soundbank: str = "No soundbank loaded"
    boss_not_music_switch_container: str = "Not a MusicSwitchContainer"
    boss_missing_enemy_type_arg: str = "MSC does not have a BgmEnemyType argument"
    boss_enemy_type_empty: str = "BgmEnemyType must not be empty"
    boss_select_msc_first: str = "Select MusicSwitchContainer first"
    boss_play_intro_before_loop_start: str = "Play intro before loop_start"
    boss_enemy_type_not_set: str = "BgmEnemyType not set"
    boss_need_one_track: str = "Must add at least one BGM track"
    boss_success: str = "Created successfully"
    boss_again: str = "Again?"
    boss_music_switch_container_label: str = "MusicSwitchContainer"
    boss_enemy_type_label: str = "BgmEnemyType"
    boss_state_path_button: str = "State Path"
    boss_help_text: str = (
        "- Boss tracks need to be added to cs_smain\n"
        "- Use the main MusicSwitchContainer (1001573296 in Elden Ring)\n"
        "- Additional tracks will be used for 'heatup' phases\n"
        "- BgmEnemyType corresponds to BgmBossChrIdConv in Smithbox\n"
        "- Only already existing BgmEnemyType strings can be used!\n"
        "- BgmBossChrIdConv params must be 6-digit for EMEVD"
    )
    boss_create_button: str = "Create Boss Track"
    loading_generic: str = "Loading..."
    error_create_widgets: str = "Error creating node widgets, check logs"
    curves_to_use: str = "Curves to use"
    decision_tree: str = "Decision Tree"
    add_state_path: str = "Add State Path"
    edit_on_track: str = "Edit on Track"
    segment_has_no_tracks: str = "Segment has no tracks"
    markers_label: str = "Markers"
    show_empty_switches: str = "Show empty switches"
    switches_label: str = "Switches"
    copy_window: str = "Copy?"
    copy_wems_prompt: str = "Copy WEMs to soundbank {name}?"
    yes: str = "Yes"
    no: str = "No"
    properties_title: str = "Properties"
    properties_column_property: str = "Property"
    properties_column_value: str = "Value"
    properties_add: str = "+ Add Property"
    table_column_value: str = "Value"
    table_add_paths: str = "+ Add Paths"
    table_add_files: str = "+ Add Files"
    tracks_label: str = "Tracks"
    add_track_label: str = "+ Add Track"
    track_row_label: str = "Track #{index}"
    select_audio_title: str = "Select Audio"
    curves_label: str = "Curves"
    add_curve_label: str = "+ Add Curve"
    add_marker_label: str = "+ Add Marker"
    clips_label: str = "Clips"
    curve_type_label: str = "Type"
    audio_not_found: str = "Audio not found"
    select_audio_file: str = "Select Audio File"
    loop_label: str = "Loop"
    test_label: str = "Test"
    markers_button: str = "Markers"
    edit_button: str = "Edit"
    popup_loop_start: str = "loop_start"
    popup_loop_end: str = "loop_end"
    popup_begin_trim: str = "begin_trim"
    popup_end_trim: str = "end_trim"
    field_plugin: str = "plugin"
    field_source_type: str = "source_type"
    field_enable_attenuation: str = "enable_attenuation"
    field_three_dimensional_spatialization_type: str = "3D spatialization"
    field_max_instances: str = "max_instances"
    field_virtual_queue_behavior: str = "virtual_queue_behavior"
    field_use_virtual_behavior: str = "use_virtual_behavior"
    field_target_id: str = "target_id"
    field_is_bus: str = "is_bus"
    field_transition_time: str = "transition_time"
    field_delay: str = "delay"
    field_fade_curve: str = "fade_curve"
    field_bank_id: str = "bank_id"
    field_loop_count: str = "loop_count"
    field_avoid_repeats: str = "avoid_repeats"
    field_avoid_repeat_count: str = "avoid_repeat_count"
    field_PlayFromElapsedTime: str = "PlayFromElapsedTime"
    desc_target_id: str = "Target node ID for this action."
    desc_is_bus: str = "Whether the target is a Bus."
    desc_transition_time: str = "Transition duration in milliseconds."
    desc_delay: str = "Action delay in milliseconds."
    desc_fade_curve: str = "Fade curve type/value."
    desc_bank_id: str = "Bank ID bound to this action."
    desc_loop_count: str = "How many times to loop."
    desc_avoid_repeats: str = "Avoid repeating recently played sounds."
    desc_avoid_repeat_count: str = "Number of recent entries excluded from repeat."
    desc_max_instances: str = "Maximum number of simultaneous instances."
    desc_virtual_queue_behavior: str = "Behavior when virtualized in voice queue."
    desc_use_virtual_behavior: str = "Enable virtual voice behavior."
    desc_source_type: str = "Source storage mode of this media."
    desc_plugin: str = "Audio decoding/processing plugin."
    field_Action: str = "Action"
    field_Event: str = "Event"
    field_Sound: str = "Sound"
    field_ActorMixer: str = "ActorMixer"
    field_Attenuation: str = "Attenuation"
    field_Bus: str = "Bus"
    field_LayerContainer: str = "LayerContainer"
    field_MusicTrack: str = "MusicTrack"
    field_MusicSegment: str = "MusicSegment"
    field_MusicSwitchContainer: str = "MusicSwitchContainer"
    field_MusicRandomSequenceContainer: str = "MusicRandomSequenceContainer"
    field_RandomSequenceContainer: str = "RandomSequenceContainer"
    field_SwitchContainer: str = "SwitchContainer"
    hash_string_label: str = "String"
    hash_hash_label: str = "Hash"
    dpg_glossary_window: str = "DearPyGui Glossary"
    dpg_glossary_notice: str = "Built-in DearPyGui tools are mostly English UI. Use this glossary for Chinese mapping."
    dpg_glossary_about: str = (
        "About: app info, backend, version, and build environment."
    )
    dpg_glossary_metrics: str = (
        "Metrics: frame stats, draw calls, item count, performance counters."
    )
    dpg_glossary_docs: str = (
        "Documentation: DearPyGui API reference and usage examples."
    )
    dpg_glossary_debug: str = "Debug: inspect runtime states and debug internals."
    dpg_glossary_style: str = (
        "Style Editor: theme colors, paddings, spacing, rounding and style vars."
    )
    dpg_glossary_font: str = (
        "Font Manager: loaded fonts, glyph ranges, and default font binding."
    )
    dpg_glossary_registry: str = (
        "Item Registry: inspect full item tree, tags, and parents/children."
    )
    dpg_glossary_stack: str = "Stack Tool: inspect container stack and last-item stack."

    @classmethod
    def get(cls, key: str, default: Any = None) -> str:
        try:
            return cls[key]
        except AttributeError:
            return default

    @classmethod
    def __contains__(cls, key: str) -> bool:
        if not isinstance(key, str):
            return False
        
        return hasattr(cls, key)

    @classmethod
    def __getitem__(cls, key: str) -> str:
        return getattr(cls, key)


class English(Localization):
    pass


class Chinese(English):
    language: str = "Chinese"
    language_alt_name: str = "中文"

    # Keep viewport title ASCII to avoid mojibake in Windows title bar on some setups.
    title: str = "Banks of Yonder"

    menu_language: str = "\u8bed\u8a00"
    language_chinese: str = "\u4e2d\u6587"
    language_switched: str = "\u5df2\u5207\u6362\u4e3a\u4e2d\u6587\u3002"
    language_restart_hint: str = "\u90e8\u5206\u6587\u672c\u9700\u8981\u91cd\u65b0\u6253\u5f00\u7a97\u53e3\u540e\u5237\u65b0\u3002"

    menu_file: str = "\u6587\u4ef6"
    menu_recent_files: str = "\u6700\u8fd1\u6587\u4ef6"
    menu_open: str = "\u6253\u5f00..."
    menu_save: str = "\u4fdd\u5b58"
    menu_save_as: str = "\u53e6\u5b58\u4e3a..."
    menu_repack: str = "\u91cd\u65b0\u6253\u5305"
    menu_new_soundbank: str = "\u65b0\u5efa Soundbank..."
    menu_bank: str = "\u97f3\u9891\u5e93"
    menu_pin_orphans: str = "\u56fa\u5b9a\u5b64\u7acb\u8282\u70b9"
    menu_solve_hirc: str = "\u89e3\u6790 HIRC"
    menu_verify: str = "\u6821\u9a8c"
    menu_advanced: str = "\u9ad8\u7ea7"
    menu_delete_unused_wems: str = "\u5220\u9664\u672a\u4f7f\u7528\u7684 WEM"
    menu_delete_orphans: str = "\u5220\u9664\u5b64\u7acb\u8282\u70b9"
    menu_create: str = "\u521b\u5efa"
    menu_simple_sound: str = "\u521b\u5efa\u97f3\u6548"
    menu_batch_sound_builder: str = "\u6279\u91cf\u521b\u5efa\u97f3\u6548"
    menu_boss_track: str = "\u521b\u5efaBoss\u97f3\u4e50"
    menu_ambience_track: str = "\u73af\u5883\u97f3\u8f68"
    menu_new_wwise_event: str = "\u65b0\u5efa Wwise \u4e8b\u4ef6"
    menu_tools: str = "\u5de5\u5177"
    menu_calc_hash: str = "\u8ba1\u7b97\u54c8\u5e0c"
    menu_mass_transfer: str = "\u6279\u91cf\u8f6c\u79fb"
    menu_export_sounds: str = "\u5bfc\u51fa\u97f3\u6548"
    menu_waves_to_wems: str = "WAV \u8f6c WEM"
    menu_yonder: str = "Yonder"
    menu_dearpygui: str = "\u754c\u9762\u8c03\u8bd5"
    menu_dpg_about: str = "\u5173\u4e8e"
    menu_dpg_metrics: str = "\u6027\u80fd\u7edf\u8ba1"
    menu_dpg_docs: str = "\u6587\u6863"
    menu_dpg_debug: str = "\u8c03\u8bd5"
    menu_dpg_style_editor: str = "\u6837\u5f0f\u7f16\u8f91\u5668"
    menu_dpg_font_manager: str = "\u5b57\u4f53\u7ba1\u7406"
    menu_dpg_item_registry: str = "\u63a7\u4ef6\u6ce8\u518c\u8868"
    menu_dpg_stack_tool: str = "\u5806\u6808\u5de5\u5177"
    menu_settings: str = "\u8bbe\u7f6e"
    menu_about: str = "\u5173\u4e8e"

    tab_events: str = "\u4e8b\u4ef6"
    tab_globals: str = "\u5168\u5c40"
    hint_search_on_enter: str = "\u56de\u8f66\u6267\u884c\u641c\u7d22"
    showing_events: str = "\u5df2\u663e\u793a {shown}/{total} \u4e2a\u4e8b\u4ef6"
    showing_globals: str = (
        "\u5df2\u663e\u793a {shown}/{total} \u4e2a\u5168\u5c40\u8282\u70b9"
    )
    table_node: str = "\u8282\u70b9"
    pinned_nodes: str = "\u5df2\u56fa\u5b9a\u8282\u70b9"
    json_apply: str = "\u5e94\u7528"
    json_reload: str = "\u91cd\u8f7d Json"
    json_reset: str = "\u91cd\u7f6e\u8282\u70b9"

    context_new_child: str = "\u65b0\u5efa\u5b50\u8282\u70b9"
    context_add_action: str = "\u6dfb\u52a0 Action"
    context_action_play: str = "Play"
    context_action_event: str = "Event"
    context_action_stop: str = "Stop"
    context_action_mute_bus: str = "\u9759\u97f3 Bus"
    context_action_reset_bus_volume: str = "\u91cd\u7f6e Bus \u97f3\u91cf"
    context_show_graph: str = "\u663e\u793a\u56fe"
    context_pin: str = "\u56fa\u5b9a"
    context_cut: str = "\u526a\u5207"
    context_copy: str = "\u590d\u5236"
    context_paste_child: str = "\u7c98\u8d34\u5b50\u8282\u70b9"
    context_delete: str = "\u5220\u9664"
    context_unpin: str = "\u53d6\u6d88\u56fa\u5b9a"
    context_unpin_all: str = "\u53d6\u6d88\u5168\u90e8\u56fa\u5b9a"
    context_jump_to: str = "\u8df3\u8f6c\u5230"

    open: str = "\u6253\u5f00 Soundbank"
    save_soundbank: str = "\u4fdd\u5b58 Soundbank"
    soundbank_files: str = "Soundbank \u6587\u4ef6 (.bnk)"
    json_files: str = "JSON \u6587\u4ef6 (.json)"
    all_files: str = "\u6240\u6709\u6587\u4ef6"
    choose_empty_directory: str = "\u9009\u62e9\u7a7a\u76ee\u5f55"
    error_directory_not_empty: str = "\u76ee\u5f55\u4e0d\u4e3a\u7a7a"
    loading_saving_soundbank: str = "\u6b63\u5728\u4fdd\u5b58 Soundbank..."
    loading_repacking: str = "\u6b63\u5728\u91cd\u65b0\u6253\u5305..."
    loading_unpacking: str = "\u6b63\u5728\u89e3\u5305..."
    loading_loading_soundbank: str = "\u6b63\u5728\u52a0\u8f7d Soundbank..."
    loading_solving: str = "\u6b63\u5728\u89e3\u6790..."
    loading_verifying: str = "\u6b63\u5728\u6821\u9a8c..."
    choice_unpacked_msg: str = "Soundbank {name} \u5df2\u89e3\u5305\uff0c\u662f\u5426\u76f4\u63a5\u6253\u5f00 json\uff1f"
    choice_open_json: str = "\u6253\u5f00 json"
    choice_unpack_again: str = "\u91cd\u65b0\u89e3\u5305"
    choice_bnk_or_json: str = "\u6253\u5f00 bnk \u8fd8\u662f json\uff1f"
    choice_save_before_open: str = "\u5148\u4fdd\u5b58 Soundbank {name} \u5417\uff1f"
    choice_just_do_it: str = "\u76f4\u63a5\u6253\u5f00"
    choice_continue: str = "\u7ee7\u7eed\uff1f"

    settings_window: str = "\u8bbe\u7f6e"
    save: str = "\u4fdd\u5b58"
    calc_hash_window: str = "\u8ba1\u7b97\u54c8\u5e0c"
    calc_hash_help: str = "\u8ba1\u7b97 FNV-1a 32 \u4f4d\u54c8\u5e0c\u503c"
    mass_transfer_window: str = "\u8f6c\u79fb\u97f3\u6548"
    convert_wavs_window: str = "\u8f6c\u6362 Wave \u6587\u4ef6"
    export_sounds_window: str = "\u5bfc\u51fa Soundbank \u97f3\u6548"
    about_window: str = "\u5173\u4e8e"

    source_bank_label: str = "\u6e90 Soundbank"
    dest_bank_label: str = "\u76ee\u6807 Soundbank"
    source_ids_label: str = "\u6e90 Wwise ID"
    dest_ids_label: str = "\u76ee\u6807 Wwise ID"
    select_ids_button: str = "\u9009\u62e9 ID..."
    swap_banks_button: str = "\u4ea4\u6362\u97f3\u9891\u5e93"
    swap_ids_button: str = "\u4ea4\u6362 ID"
    transfer_button: str = "\u5f00\u59cb\u8f6c\u79fb"
    repack_button: str = "\u91cd\u65b0\u6253\u5305"
    select_source_first: str = "\u8bf7\u5148\u9009\u62e9\u6e90\u97f3\u9891\u5e93"
    error_source_not_set: str = "\u672a\u9009\u62e9\u6e90\u97f3\u9891\u5e93"
    error_dest_not_set: str = "\u672a\u9009\u62e9\u76ee\u6807\u97f3\u9891\u5e93"
    error_no_lines: str = "\u672a\u9009\u62e9\u6e90 ID"
    error_line_mismatch: str = (
        "\u6e90 ID \u4e0e\u76ee\u6807 ID \u6570\u91cf\u4e0d\u4e00\u81f4"
    )
    error_dest_ids_no_hash: str = (
        "\u76ee\u6807 ID \u4e0d\u80fd\u4f7f\u7528\u54c8\u5e0c\u503c"
    )
    error_explicit_implicit_mismatch: str = "\u663e\u5f0f\u540d\u79f0/\u54c8\u5e0c\u4e0d\u80fd\u4e0e\u9690\u5f0f\u540d\u79f0\u914d\u5bf9"
    error_source_id_not_found: str = (
        "\u5728\u6e90\u97f3\u9891\u5e93\u4e2d\u627e\u4e0d\u5230 {line}"
    )
    error_dest_id_exists: str = (
        "{line} \u5728\u76ee\u6807\u97f3\u9891\u5e93\u4e2d\u5df2\u5b58\u5728"
    )
    transfer_successful: str = "\u8f6c\u79fb\u6210\u529f"
    transfer_help_text: str = (
        "- \u5728\u4e0d\u540c soundbank \u95f4\u8f6c\u79fb\u97f3\u6548\u7ed3\u6784\n"
        "- \u652f\u6301\u5b8c\u6574\u4e8b\u4ef6\u540d (Play_x123456789)\u3001\u54c8\u5e0c\u503c (#102591249) \u6216 Wwise \u540d (x123456789)\n"
        "- Wwise \u540d\u4f1a\u81ea\u52a8\u89e3\u6790\u4e3a Play_/Stop_ \u4e8b\u4ef6\n"
        "- \u540d\u79f0/\u54c8\u5e0c \u4e0e Wwise \u540d\u4e0d\u80fd\u6df7\u5408\u914d\u5bf9"
    )
    error_bnk2json_required: str = (
        "\u91cd\u65b0\u6253\u5305\u9700\u8981\u5148\u914d\u7f6e bnk2json"
    )
    error_bnk2json_failed: str = (
        "bnk2json \u6267\u884c\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u65e5\u5fd7"
    )

    convert_wave_files: str = "Wave \u6587\u4ef6"
    convert_output_dir: str = "\u8f93\u51fa\u76ee\u5f55"
    convert_target_volume: str = "\u76ee\u6807\u97f3\u91cf"
    convert_silence_threshold: str = "\u9759\u97f3\u9608\u503c"
    convert_snippet_length: str = "\u7247\u6bb5\u957f\u5ea6"
    convert_to_wem: str = "\u8f6c\u6362\u4e3a .wem"
    convert_no_wave_files: str = "\u672a\u9009\u62e9 Wave \u6587\u4ef6"
    convert_invalid_output_dir: str = "\u8f93\u51fa\u76ee\u5f55\u65e0\u6548"
    convert_wwise_not_found: str = (
        "\u672a\u627e\u5230 Wwise \u53ef\u6267\u884c\u6587\u4ef6"
    )
    convert_loading: str = "\u6b63\u5728\u8f6c\u6362..."
    convert_loading_trim: str = "\u6b63\u5728\u53bb\u9664\u9759\u97f3..."
    convert_loading_snippet: str = "\u6b63\u5728\u751f\u6210 Prefetch \u7247\u6bb5..."
    convert_loading_volume: str = "\u6b63\u5728\u8c03\u6574\u97f3\u91cf..."
    convert_loading_wem: str = "\u6b63\u5728\u8f6c\u6362 WEM..."
    convert_done: str = "\u5b8c\u6210\uff01"
    convert_again: str = "\u518d\u6765\u4e00\u6b21\uff1f"
    convert_start_button: str = "\u5f00\u59cb\u8f6c\u6362"

    export_soundbank_label: str = "Soundbank"
    export_output_dir: str = "\u8f93\u51fa\u76ee\u5f55"
    export_full_streamed: str = (
        "\u4e3a\u6d41\u5f0f\u97f3\u6548\u5bfc\u51fa\u5b8c\u6574\u6587\u4ef6"
    )
    export_convert_wav: str = "\u8f6c\u6362\u4e3a wav"
    export_no_soundbank: str = "\u672a\u52a0\u8f7d Soundbank"
    export_invalid_output_dir: str = "\u8f93\u51fa\u76ee\u5f55\u65e0\u6548"
    export_loading: str = "\u6b63\u5728\u8f6c\u6362..."
    export_done: str = "\u5b8c\u6210\uff01"
    export_again: str = "\u518d\u6765\u4e00\u6b21\uff1f"
    export_start_button: str = "\u5f00\u59cb\u5bfc\u51fa"

    about_written_by: str = "\u4f5c\u8005\uff1aNikolas Dahn"
    about_bug_report: str = (
        "\u53cd\u9988 Bug\u3001\u63d0\u95ee\u6216\u529f\u80fd\u5efa\u8bae\uff1f"
    )
    about_contact: str = "\u53ef\u5728 Discord \u8054\u7cfb @Managarm"
    browse: str = "\u6d4f\u89c8"
    okay: str = "\u786e\u5b9a"
    cancel: str = "\u53d6\u6d88"

    settings_external_tools: str = "\u5916\u90e8\u5de5\u5177"
    settings_data_sources: str = "\u6570\u636e\u6e90"
    settings_bnk2json_tooltip: str = (
        "\u7528\u4e8e\u89e3\u5305\u4e0e\u91cd\u65b0\u6253\u5305 soundbank"
    )
    settings_wwise_tooltip: str = "\u7528\u4e8e\u5c06 wav \u8f6c\u6362\u4e3a wem"
    settings_vgmstream_tooltip: str = (
        "\u7528\u4e8e\u5c06 wem \u8f6c\u4e3a wav \u5e76\u64ad\u653e"
    )
    settings_soundbank_folders: str = "Soundbank \u6587\u4ef6\u5939"
    settings_soundbank_folders_tooltip: str = (
        "\u7528\u4e8e\u5b9a\u4f4d\u5916\u90e8\u97f3\u6548"
    )
    settings_hash_dictionaries: str = "\u54c8\u5e0c\u5b57\u5178"
    settings_hash_dictionaries_tooltip: str = "\u7528\u4e8e\u53cd\u67e5\u54c8\u5e0c"

    new_event_name_label: str = "\u540d\u79f0"
    new_event_allow_arbitrary: str = "\u5141\u8bb8\u81ea\u5b9a\u4e49\u540d\u79f0"
    new_event_target_node: str = "\u76ee\u6807\u8282\u70b9 ID"
    new_event_create_play: str = "\u521b\u5efa Play \u4e8b\u4ef6"
    new_event_create_stop: str = "\u521b\u5efa Stop \u4e8b\u4ef6"
    new_event_create_button: str = "\u521b\u5efa"
    new_event_name_required: str = "\u672a\u586b\u5199\u540d\u79f0"
    new_event_name_invalid: str = (
        "\u540d\u79f0\u683c\u5f0f\u4e0d\u7b26\u5408 (x123456789)"
    )
    new_event_none_created: str = "\u6ca1\u6709\u521b\u5efa\u4efb\u4f55\u4e8b\u4ef6"
    new_event_success: str = "\u521b\u5efa\u6210\u529f"
    new_event_again: str = "\u518d\u6765\u4e00\u6b21\uff1f"

    simple_sound_name_label: str = "\u540d\u79f0"
    simple_sound_hash_label: str = "\u54c8\u5e0c"
    simple_sound_actor_mixer_label: str = "ActorMixer"
    simple_sound_avoid_repeats: str = "\u907f\u514d\u91cd\u590d"
    simple_sound_sounds_label: str = "\u97f3\u9891"
    simple_sound_add_sound: str = "+ \u6dfb\u52a0\u97f3\u9891"
    simple_sound_source_row: str = "\u97f3\u6e90 #{index}"
    simple_sound_create_button: str = "\u521b\u5efa"
    simple_sound_name_required: str = "\u672a\u586b\u5199\u540d\u79f0"
    simple_sound_name_exists: str = "\u540c\u540d\u4e8b\u4ef6\u5df2\u5b58\u5728"
    simple_sound_actor_mixer_required: str = "ActorMixer \u672a\u6307\u5b9a"
    simple_sound_no_sounds: str = "\u672a\u6dfb\u52a0\u97f3\u9891"
    simple_sound_success: str = "\u521b\u5efa\u6210\u529f"
    simple_sound_again: str = "\u518d\u6765\u4e00\u6b21\uff1f"
    simple_sound_batch_mode: str = "\u6279\u91cf\u6a21\u5f0f"
    simple_sound_type_label: str = "\u7c7b\u578b"
    simple_sound_import_folder: str = "\u5bfc\u5165\u6587\u4ef6\u5939..."
    simple_sound_loaded_count: str = (
        "\u5df2\u52a0\u8f7d {count} \u4e2a\u97f3\u9891\u6587\u4ef6"
    )
    simple_sound_batch_success: str = (
        "\u6279\u91cf\u521b\u5efa\uff1a{created}\uff0c\u8df3\u8fc7\uff1a{skipped}"
    )
    simple_sound_batch_none_created: str = "\u672a\u521b\u5efa\u4efb\u4f55\u4e8b\u4ef6\uff08\u53ef\u80fd\u540c\u540d\u5747\u5df2\u5b58\u5728\uff09"
    simple_sound_batch_merge_label: str = "\u5408\u5e76\u65b9\u5f0f"
    simple_sound_merge_single: str = "\u4e00\u4e2a\u6587\u4ef6\u4e00\u4e2a\u4e8b\u4ef6"
    simple_sound_merge_by_playid: str = "\u6309 PlayID \u5408\u5e76"
    simple_sound_merge_by_size: str = "\u6309\u56fa\u5b9a\u6570\u91cf\u5408\u5e76"
    simple_sound_merge_size_label: str = "\u6bcf\u7ec4\u6570\u91cf"
    simple_sound_merge_size_invalid: str = "\u6bcf\u7ec4\u6570\u91cf\u5fc5\u987b >= 1"
    batch_sound_window: str = "\u6279\u91cf\u97f3\u6548\u7f16\u6392"
    batch_sound_groups_label: str = "\u5206\u7ec4"
    batch_sound_new_group: str = "+ \u65b0\u5efa\u5206\u7ec4"
    batch_sound_delete_group: str = "\u5220\u9664\u5206\u7ec4"
    batch_sound_group_name: str = "\u4e8b\u4ef6\u540d"
    batch_sound_group_type: str = "\u7c7b\u578b"
    batch_sound_add_files: str = "\u6dfb\u52a0\u6587\u4ef6..."
    batch_sound_add_folder: str = "\u6dfb\u52a0\u6587\u4ef6\u5939..."
    batch_sound_clear_files: str = "\u6e05\u7a7a\u97f3\u9891"
    batch_sound_remove_file: str = "\u79fb\u9664\u97f3\u9891"
    batch_sound_auto_name: str = "\u81ea\u52a8\u547d\u540d"
    batch_sound_files_label: str = "\u97f3\u9891\u6587\u4ef6 ({count})"
    batch_sound_preview_label: str = "\u97f3\u9891\u9884\u89c8"
    batch_sound_create_button: str = "\u5168\u90e8\u521b\u5efa"
    batch_sound_no_groups: str = "\u5c1a\u672a\u914d\u7f6e\u5206\u7ec4"
    batch_sound_select_group: str = "\u8bf7\u5148\u9009\u62e9\u4e00\u4e2a\u5206\u7ec4"
    batch_sound_group_name_required: str = (
        "\u5206\u7ec4\u4e8b\u4ef6\u540d\u4e0d\u80fd\u4e3a\u7a7a"
    )
    batch_sound_group_name_exists: str = "\u4e8b\u4ef6\u5df2\u5b58\u5728\uff1a{name}"
    batch_sound_group_name_duplicate: str = (
        "\u5206\u7ec4\u4e8b\u4ef6\u540d\u91cd\u590d\uff1a{name}"
    )
    batch_sound_group_no_files: str = (
        "\u5206\u7ec4\u672a\u6dfb\u52a0\u97f3\u9891\uff1a{name}"
    )
    batch_sound_created_summary: str = (
        "\u6210\u529f\u521b\u5efa {count} \u4e2a\u5206\u7ec4"
    )
    batch_sound_auto_name_hint: str = "\u82e5\u4e8b\u4ef6\u540d\u4e3a\u7a7a\uff0c\u5c06\u81ea\u52a8\u4f7f\u7528\u300c\u7c7b\u578b+\u9996\u4e2a\u97f3\u9891ID\u300d"
    batch_sound_folder_mode: str = "\u6587\u4ef6\u5939\u5bfc\u5165"
    batch_sound_folder_mode_current: str = "\u6dfb\u52a0\u5230\u5f53\u524d\u5206\u7ec4"
    batch_sound_folder_mode_per_file: str = (
        "\u6bcf\u4e2a\u6587\u4ef6\u5355\u72ec\u5206\u7ec4"
    )
    batch_sound_folder_mode_by_prefix: str = (
        "\u6309\u6587\u4ef6\u540d\u524d\u7f00\u5206\u7ec4"
    )
    batch_sound_folder_import_manual: str = "\u624b\u52a8\u5206\u914d"
    batch_sound_folder_import_per_file: str = (
        "\u6bcf\u4e2a\u97f3\u9891\u5355\u72ec\u5efa\u7ec4"
    )
    batch_sound_assign_window: str = (
        "\u5c06\u6587\u4ef6\u5939\u97f3\u9891\u5206\u914d\u5230\u5206\u7ec4"
    )
    batch_sound_assign_hint: str = "\u4e3a\u6bcf\u4e2a\u6587\u4ef6\u9009\u62e9\u76ee\u6807\u5206\u7ec4\uff0c\u7136\u540e\u786e\u8ba4\u5bfc\u5165\u3002"
    batch_sound_assign_file_col: str = "\u6587\u4ef6"
    batch_sound_assign_group_col: str = "\u76ee\u6807\u5206\u7ec4"
    batch_sound_assign_confirm: str = "\u786e\u8ba4\u5bfc\u5165"
    batch_sound_assign_new_group: str = "\u65b0\u5efa\u5206\u7ec4"
    batch_sound_bulk_type: str = "\u6279\u91cf\u4fee\u6539\u7c7b\u578b"
    batch_sound_apply_bulk_type: str = "\u5e94\u7528\u5230\u5168\u90e8\u5206\u7ec4"
    select_folder: str = "\u9009\u62e9\u6587\u4ef6\u5939"

    create_node_id_label: str = "ID"
    create_node_window: str = "\u521b\u5efa\u8282\u70b9"
    create_node_create_button: str = "\u521b\u5efa"

    state_path_leaf_not_set: str = "\u672a\u8bbe\u7f6e\u53f6\u5b50\u8282\u70b9 ID"
    state_path_keys_empty: str = "\u72b6\u6001\u952e\u4e0d\u80fd\u4e3a\u7a7a"
    state_path_node_label: str = "\u8282\u70b9"
    state_path_window: str = "\u65b0\u5efa\u72b6\u6001\u8def\u5f84"
    select_nodes_filter_hint: str = "\u8f93\u5165\u5173\u952e\u8bcd\u7b5b\u9009..."
    select_nodes_column: str = "\u8282\u70b9 (id)"
    select_nodes_multi_hint: str = "\u6309\u4f4f Ctrl \u6216\u70b9\u51fb\u591a\u884c\u4ee5\u9009\u62e9\u591a\u4e2a\u8282\u70b9\u3002"

    boss_phase_label_normal: str = "\u5e38\u6001"
    boss_phase_label_heatup: str = "\u72c2\u66b4\u9636\u6bb5 {phase}"
    boss_no_soundbank: str = "\u672a\u52a0\u8f7d Soundbank"
    boss_not_music_switch_container: str = (
        "\u9009\u4e2d\u9879\u4e0d\u662f MusicSwitchContainer"
    )
    boss_missing_enemy_type_arg: str = "MSC \u4e0d\u542b BgmEnemyType \u53c2\u6570"
    boss_enemy_type_empty: str = "BgmEnemyType \u4e0d\u80fd\u4e3a\u7a7a"
    boss_select_msc_first: str = "\u8bf7\u5148\u9009\u62e9 MusicSwitchContainer"
    boss_play_intro_before_loop_start: str = (
        "\u5728 loop_start \u524d\u5148\u64ad\u653e intro"
    )
    boss_enemy_type_not_set: str = "BgmEnemyType \u672a\u8bbe\u7f6e"
    boss_need_one_track: str = "\u81f3\u5c11\u9700\u8981\u4e00\u6761 BGM \u97f3\u8f68"
    boss_success: str = "\u521b\u5efa\u6210\u529f"
    boss_again: str = "\u518d\u6765\u4e00\u6b21\uff1f"
    boss_music_switch_container_label: str = "MusicSwitchContainer"
    boss_enemy_type_label: str = "BgmEnemyType"
    boss_state_path_button: str = "\u72b6\u6001\u8def\u5f84"
    boss_help_text: str = (
        "- Boss \u97f3\u4e50\u9700\u52a0\u5230 cs_smain\n"
        "- \u4f7f\u7528\u4e3b MusicSwitchContainer\uff08\u827e\u5c14\u767b\u6cd5\u73af\u4e2d\u901a\u5e38\u662f 1001573296\uff09\n"
        "- \u989d\u5916\u97f3\u8f68\u4f1a\u88ab\u7528\u4f5c\u8f6c\u9636\u6bb5\n"
        "- BgmEnemyType \u5bf9\u5e94 Smithbox \u4e2d\u7684 BgmBossChrIdConv\n"
        "- \u53ea\u80fd\u4f7f\u7528\u5df2\u5b58\u5728\u7684 BgmEnemyType \u5b57\u7b26\u4e32\n"
        "- EMEVD \u4f7f\u7528\u65f6 BgmBossChrIdConv \u53c2\u6570\u9700\u4e3a 6 \u4f4d"
    )
    boss_create_button: str = "\u521b\u5efa Boss \u97f3\u4e50"
    loading_generic: str = "\u52a0\u8f7d\u4e2d..."
    error_create_widgets: str = "\u751f\u6210\u8282\u70b9\u63a7\u4ef6\u5931\u8d25\uff0c\u8bf7\u67e5\u770b\u65e5\u5fd7"
    curves_to_use: str = "\u66f2\u7ebf\u4f7f\u7528\u6620\u5c04"
    decision_tree: str = "\u51b3\u7b56\u6811"
    add_state_path: str = "\u6dfb\u52a0\u72b6\u6001\u8def\u5f84"
    edit_on_track: str = "\u5728\u97f3\u8f68\u4e0a\u7f16\u8f91"
    segment_has_no_tracks: str = "\u8be5 Segment \u6ca1\u6709\u97f3\u8f68"
    markers_label: str = "\u6807\u8bb0"
    show_empty_switches: str = "\u663e\u793a\u7a7a\u5206\u652f"
    switches_label: str = "\u5207\u6362\u6620\u5c04"
    copy_window: str = "\u590d\u5236\uff1f"
    copy_wems_prompt: str = (
        "\u8981\u5c06 WEM \u590d\u5236\u5230 soundbank {name} \u5417\uff1f"
    )
    yes: str = "\u662f"
    no: str = "\u5426"
    properties_title: str = "\u5c5e\u6027"
    properties_column_property: str = "\u5c5e\u6027\u540d"
    properties_column_value: str = "\u503c"
    properties_add: str = "+ \u6dfb\u52a0\u5c5e\u6027"
    table_column_value: str = "\u503c"
    table_add_paths: str = "+ \u6dfb\u52a0\u8def\u5f84"
    table_add_files: str = "+ \u6dfb\u52a0\u6587\u4ef6"
    tracks_label: str = "\u97f3\u8f68"
    add_track_label: str = "+ \u6dfb\u52a0\u97f3\u8f68"
    track_row_label: str = "\u97f3\u8f68 #{index}"
    select_audio_title: str = "\u9009\u62e9\u97f3\u9891"
    curves_label: str = "\u66f2\u7ebf"
    add_curve_label: str = "+ \u6dfb\u52a0\u66f2\u7ebf"
    add_marker_label: str = "+ \u6dfb\u52a0\u6807\u8bb0"
    clips_label: str = "\u7247\u6bb5"
    curve_type_label: str = "\u7c7b\u578b"
    audio_not_found: str = "\u672a\u627e\u5230\u97f3\u9891"
    select_audio_file: str = "\u9009\u62e9\u97f3\u9891\u6587\u4ef6"
    loop_label: str = "\u5faa\u73af"
    test_label: str = "\u6d4b\u8bd5"
    markers_button: str = "\u6807\u8bb0"
    edit_button: str = "\u7f16\u8f91"
    popup_loop_start: str = "\u5faa\u73af\u5f00\u59cb"
    popup_loop_end: str = "\u5faa\u73af\u7ed3\u675f"
    popup_begin_trim: str = "\u8d77\u59cb\u526a\u5207"
    popup_end_trim: str = "\u7ed3\u5c3e\u526a\u5207"
    field_plugin: str = "\u63d2\u4ef6"
    field_source_type: str = "\u97f3\u6e90\u7c7b\u578b"
    field_enable_attenuation: str = "\u542f\u7528\u8870\u51cf"
    field_three_dimensional_spatialization_type: str = (
        "\u4e09\u7ef4\u7a7a\u95f4\u5316\u65b9\u5f0f"
    )
    field_max_instances: str = "\u6700\u5927\u5b9e\u4f8b\u6570"
    field_virtual_queue_behavior: str = "\u865a\u62df\u961f\u5217\u884c\u4e3a"
    field_use_virtual_behavior: str = "\u542f\u7528\u865a\u62df\u884c\u4e3a"
    field_target_id: str = "\u76ee\u6807\u8282\u70b9 ID"
    field_is_bus: str = "\u662f\u5426\u4e3a Bus"
    field_transition_time: str = "\u8fc7\u6e21\u65f6\u95f4"
    field_delay: str = "\u5ef6\u8fdf"
    field_fade_curve: str = "\u6de1\u5165\u6de1\u51fa\u66f2\u7ebf"
    field_bank_id: str = "Bank ID"
    field_loop_count: str = "\u5faa\u73af\u6b21\u6570"
    field_avoid_repeats: str = "\u907f\u514d\u91cd\u590d"
    field_avoid_repeat_count: str = "\u907f\u91cd\u590d\u8ba1\u6570"
    field_PlayFromElapsedTime: str = "\u4ece\u5df2\u8fc7\u65f6\u95f4\u64ad\u653e"
    desc_target_id: str = "\u8be5 Action \u7684\u76ee\u6807\u8282\u70b9 ID\u3002"
    desc_is_bus: str = "\u76ee\u6807\u662f\u5426\u4e3a Bus\u3002"
    desc_transition_time: str = "\u8fc7\u6e21\u65f6\u957f\uff08\u6beb\u79d2\uff09\u3002"
    desc_delay: str = (
        "Action \u6267\u884c\u524d\u5ef6\u8fdf\uff08\u6beb\u79d2\uff09\u3002"
    )
    desc_fade_curve: str = (
        "\u6de1\u5165\u6de1\u51fa\u66f2\u7ebf\u7c7b\u578b/\u53c2\u6570\u3002"
    )
    desc_bank_id: str = "\u4e0e\u8be5 Action \u7ed1\u5b9a\u7684 Bank ID\u3002"
    desc_loop_count: str = "\u5faa\u73af\u64ad\u653e\u7684\u6b21\u6570\u3002"
    desc_avoid_repeats: str = (
        "\u63a7\u5236\u662f\u5426\u53ef\u4ee5\u91cd\u590d\u64ad\u653e\u3002"
    )
    desc_avoid_repeat_count: str = "\u6392\u9664\u91cd\u590d\u65f6\u53c2\u4e0e\u8ba1\u7b97\u7684\u6700\u8fd1\u6761\u76ee\u6570\u3002"
    desc_max_instances: str = (
        "\u5141\u8bb8\u540c\u65f6\u5b58\u5728\u7684\u6700\u5927\u5b9e\u4f8b\u6570\u3002"
    )
    desc_virtual_queue_behavior: str = (
        "\u58f0\u97f3\u865a\u62df\u5316\u65f6\u7684\u961f\u5217\u884c\u4e3a\u3002"
    )
    desc_use_virtual_behavior: str = (
        "\u662f\u5426\u542f\u7528\u865a\u62df\u58f0\u97f3\u884c\u4e3a\u3002"
    )
    desc_source_type: str = (
        "\u8be5\u97f3\u9891\u6e90\u7684\u5b58\u50a8\u65b9\u5f0f\u3002"
    )
    desc_plugin: str = (
        "\u89e3\u7801/\u5904\u7406\u8be5\u97f3\u9891\u7684\u63d2\u4ef6\u3002"
    )
    field_Action: str = "Action"
    field_Event: str = "\u4e8b\u4ef6"
    field_Sound: str = "\u97f3\u6548"
    field_ActorMixer: str = "\u6df7\u97f3\u8282\u70b9"
    field_Attenuation: str = "\u8870\u51cf"
    field_Bus: str = "\u603b\u7ebf"
    field_LayerContainer: str = "\u5206\u5c42\u5bb9\u5668"
    field_MusicTrack: str = "\u97f3\u4e50\u8f68"
    field_MusicSegment: str = "\u97f3\u4e50\u6bb5"
    field_MusicSwitchContainer: str = "\u97f3\u4e50\u5207\u6362\u5bb9\u5668"
    field_MusicRandomSequenceContainer: str = (
        "\u97f3\u4e50\u968f\u673a\u5e8f\u5217\u5bb9\u5668"
    )
    field_RandomSequenceContainer: str = "\u968f\u673a\u5e8f\u5217\u5bb9\u5668"
    field_SwitchContainer: str = "\u5207\u6362\u5bb9\u5668"
    hash_string_label: str = "\u540d\u79f0"
    hash_hash_label: str = "\u54c8\u5e0c"
    dpg_glossary_window: str = "DearPyGui \u672f\u8bed\u5bf9\u7167"
    dpg_glossary_notice: str = "DearPyGui \u5185\u7f6e\u5de5\u5177\u754c\u9762\u4e3b\u4f53\u4e3a\u82f1\u6587\uff0c\u53ef\u53c2\u8003\u4ee5\u4e0b\u4e2d\u6587\u5bf9\u7167\u3002"
    dpg_glossary_about: str = "\u5173\u4e8e\uff1a\u663e\u793a\u5e94\u7528\u3001\u540e\u7aef\u3001\u7248\u672c\u4e0e\u6784\u5efa\u73af\u5883\u4fe1\u606f\u3002"
    dpg_glossary_metrics: str = "\u6027\u80fd\u7edf\u8ba1\uff1a\u5e27\u7387/\u5e27\u8017\u65f6\u3001Draw Call\u3001\u63a7\u4ef6\u6570\u3001\u6027\u80fd\u8ba1\u6570\u5668\u3002"
    dpg_glossary_docs: str = "\u6587\u6863\uff1aDearPyGui API \u53c2\u8003\u4e0e\u4f7f\u7528\u793a\u4f8b\u3002"
    dpg_glossary_debug: str = "\u8c03\u8bd5\uff1a\u67e5\u770b\u8fd0\u884c\u65f6\u72b6\u6001\u548c\u8c03\u8bd5\u5185\u90e8\u4fe1\u606f\u3002"
    dpg_glossary_style: str = "\u6837\u5f0f\u7f16\u8f91\u5668\uff1a\u8c03\u6574\u4e3b\u9898\u989c\u8272\u3001\u95f4\u8ddd\u3001\u5706\u89d2\u7b49\u6837\u5f0f\u53c2\u6570\u3002"
    dpg_glossary_font: str = "\u5b57\u4f53\u7ba1\u7406\uff1a\u67e5\u770b\u5df2\u52a0\u8f7d\u5b57\u4f53\u3001\u5b57\u5f62\u8303\u56f4\u4e0e\u9ed8\u8ba4\u5b57\u4f53\u7ed1\u5b9a\u3002"
    dpg_glossary_registry: str = "\u63a7\u4ef6\u6ce8\u518c\u8868\uff1a\u67e5\u770b\u5b8c\u6574\u63a7\u4ef6\u6811\u3001tag\u3001\u7236\u5b50\u7ed3\u6784\u3002"
    dpg_glossary_stack: str = "\u5806\u6808\u5de5\u5177\uff1a\u67e5\u770b\u5bb9\u5668\u5806\u6808\u548c last-item \u5806\u6808\u3002"


LANGUAGE_MAP: dict[str, type[Localization]] = {}
for lang in Localization.__subclasses__():
    LANGUAGE_MAP[lang.language] = lang
    if lang.language_alt_name:
        LANGUAGE_MAP[lang.language_alt_name] = lang


Localization.active_lang = English


def translate(key: str, default: Any = None) -> str:
    return Localization.active_lang.get(key, default or key)

// Extended from https://github.com/Dasaav-dsv/wwise-state/, thank you Dasaav ~

// ?GetState@Query@SoundEngine@AK@@YA?AW4AKRESULT@@KAEAK@Z
// ?SetState@SoundEngine@AK@@YA?AW4AKRESULT@@KK@Z
// ?GetSwitch@Query@SoundEngine@AK@@YA?AW4AKRESULT@@K_KAEAK@Z
// ?GetRTPCValue@Query@SoundEngine@AK@@YA?AW4AKRESULT@@K_KKAEAMAEAW4RTPCValue_type@123@@Z

use std::{mem, sync::LazyLock};

use windows::{
    Win32::System::LibraryLoader::{GetModuleHandleW, GetProcAddress},
    core::{PCWSTR, s},
};

// io_valueType for GetRTPCValue: query the value at the game object level
const RTPC_VALUE_TYPE_GAME_OBJECT: u32 = 0;

pub fn get_state(state_group: u32) -> Option<u32> {
    let get_state = (*GET_STATE)?;
    let mut state = 0;
    let result = get_state(state_group, &mut state);
    (result == 1).then_some(state)
}

// currently active switch id of a switch group, for a given game object
pub fn get_switch(switch_group: u32, game_object_id: u64) -> Option<u32> {
    let get_switch = (*GET_SWITCH)?;
    let mut switch = 0;
    let result = get_switch(switch_group, game_object_id, &mut switch);
    (result == 1).then_some(switch)
}

// current rtpc value at a given game object
pub fn get_rtpc(rtpc_id: u32, game_object_id: u64) -> Option<f32> {
    let get_rtpc_value = (*GET_RTPC_VALUE)?;
    let mut value = 0.0;
    let mut value_type = RTPC_VALUE_TYPE_GAME_OBJECT;
    let result = get_rtpc_value(rtpc_id, game_object_id, 0, &mut value, &mut value_type);
    (result == 1).then_some(value)
}

static GET_STATE: LazyLock<Option<extern "system" fn(u32, &mut u32) -> u32>> =
    // See https://www.audiokinetic.com/en/public-library/2025.1.10_9233/?source=SDK&id=namespace_a_k_1_1_sound_engine_1_1_query_acf1d46072687826dbc1ff2116a4234c8.html
    LazyLock::new(|| unsafe {
        let module = GetModuleHandleW(PCWSTR::null()).ok()?;
        let export = GetProcAddress(
            module,
            s!("?GetState@Query@SoundEngine@AK@@YA?AW4AKRESULT@@KAEAK@Z"),
        )?;
        Some(mem::transmute(export))
    });

static GET_SWITCH: LazyLock<Option<extern "system" fn(u32, u64, &mut u32) -> u32>> =
    // See https://www.audiokinetic.com/en/public-library/2025.1.10_9233/?source=SDK&id=namespace_a_k_1_1_sound_engine_1_1_query_a936ecebe49d276b0f05f0c6cb2ee7369.html
    LazyLock::new(|| unsafe {
        let module = GetModuleHandleW(PCWSTR::null()).ok()?;
        let export = GetProcAddress(
            module,
            s!("?GetSwitch@Query@SoundEngine@AK@@YA?AW4AKRESULT@@K_KAEAK@Z"),
        )?;
        Some(mem::transmute(export))
    });

static GET_RTPC_VALUE: LazyLock<Option<extern "system" fn(u32, u64, u32, &mut f32, &mut u32) -> u32>> =
    // See https://www.audiokinetic.com/en/public-library/2025.1.10_9233/?source=SDK&id=namespace_a_k_1_1_sound_engine_1_1_query_a1149dfe866412f53644e3236639ba951.html
    LazyLock::new(|| unsafe {
        let module = GetModuleHandleW(PCWSTR::null()).ok()?;
        let export = GetProcAddress(
            module,
            s!("?GetRTPCValue@Query@SoundEngine@AK@@YA?AW4AKRESULT@@K_KKAEAMAEAW4RTPCValue_type@123@@Z"),
        )?;
        Some(mem::transmute(export))
    });
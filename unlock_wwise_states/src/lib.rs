//! Elden Ring has two arrays defining allowed BGM state strings. This dll will patch
//! these with whatever state the caller wants to set, effectively disabling
//! verification and allowing for arbitrary strings.
//!
//! - SetBossBgm    -> CSSoundBgmController+0x238 (BgmEnemyType validation)
//! - FUN_140dae090 -> CSSoundBgmController+0xf58 (BgmPlaceType validation)
//! - ??? -> (Set_State_EnvPlaceType validation)

#![allow(non_snake_case)]

use pelite::pe64::Pe;
use retour::static_detour;
use std::ffi::c_void;
use std::time::Duration;

use eldenring::cs::*;
use eldenring::util::system::wait_for_system_init;
use shared::program::Program;
use shared::{arxan, FromStatic};

// TODO use AOBs instead
// https://github.com/vswarte/fromsoftware-rs/tree/main/tools/binary-mapper
const GLOBAL_FIELD_AREA_RVA: u32 = 0x3d691d8;
const GLOBAL_WORLDSOUNDMAN_RVA: u32 = 0x3d6f708;
const SETBOSSBGM_RVA: u32 = 0xdb2f70;
const AREA_BGM_UPDATE_RVA: u32 = 0xdae090;
const UPDATE_BGM_STATE_RVA: u32 = 0xdb55e0;
const BOSS_BGM_STATE_IDX: u8 = 1; // 0 is "None" and not checked
const AREA_BGM_STATE_IDX: u8 = 1;

static_detour! {
    static SetBossBgmHook: unsafe extern "C" fn(usize, u32, i32) -> ();
    static AreaBgmUpdateHook: unsafe extern "C" fn(usize, f32) -> ();
    static UpdateBgmStateHook: unsafe extern "C" fn(usize, usize, f32) -> ();
}

/// Write up to 31 bytes of `param_str` into a 32-byte slot, null-terminated.
unsafe fn write_param_str(slot: *mut u8, param_str: &str) {
    std::ptr::write_bytes(slot, 0, 32);
    std::ptr::copy_nonoverlapping(param_str.as_ptr(), slot, param_str.len().min(31));
}

/// Reimplement the area_param_id (sVar6) resolution from FUN_140dae090.
/// Returns None if FieldArea is null (original uses 0 in that case).
unsafe fn resolve_area_param_id(cssound: usize, program: &Program) -> i16 {
    // --- FieldArea branch ---
    let field_area_ptr =
        *(program.rva_to_va(GLOBAL_FIELD_AREA_RVA).unwrap() as *const *const FieldArea);
    let mut area_param_id: i16 = if field_area_ptr.is_null() {
        0
    } else {
        let mut s = *((field_area_ptr as usize + 0xb6) as *const i16);

        let area_id = *((field_area_ptr as usize + 0x2c) as *const u32);
        if area_id == 61 {
            if s == 999 {
                s = 50;
            }
            let f8 = *((field_area_ptr as usize + 0xf8) as *const i16);
            if f8 != 999 {
                s = f8;
            }
        }
        s
    };

    // --- WorldSoundMan branch ---
    let wsm_ptr = *(program.rva_to_va(GLOBAL_WORLDSOUNDMAN_RVA).unwrap() as *const usize);
    if wsm_ptr != 0 {
        let inner = *((wsm_ptr + 0x5c28) as *const usize);
        if inner != 0 {
            let s1 = *((inner + 0x364) as *const i16);
            if s1 >= 0 {
                area_param_id = s1;
            }
        }
    }

    // --- cssound override ---
    if *((cssound + 0x435) as *const u8) != 0 {
        area_param_id = *((cssound + 0x436) as *const i16);
    }

    area_param_id
}

unsafe fn setbossbgm_detour(bgmctrl: usize, bgm_boss_conv_param_id: u32, boss_bgm_state: i32) {
    let repo = match SoloParamRepository::instance() {
        Ok(r) => r,
        Err(_) => {
            SetBossBgmHook.call(bgmctrl, bgm_boss_conv_param_id, boss_bgm_state);
            return;
        }
    };

    let row = match repo.get::<WwiseValueToStrParam_BgmBossChrIdConv>(bgm_boss_conv_param_id) {
        Some(r) => r,
        None => {
            SetBossBgmHook.call(bgmctrl, bgm_boss_conv_param_id, boss_bgm_state);
            return;
        }
    };

    if let Ok(param_str) = std::str::from_utf8(row.param_str()) {
        let slot = (bgmctrl + 0x238 + BOSS_BGM_STATE_IDX as usize * 32) as *mut u8;
        //let old_str = unsafe { CStr::from_ptr(slot as *const i8).to_str().unwrap() };
        println!("[unlock_wwise_states] unlocking boss bgm {param_str}");
        write_param_str(slot, param_str);
    }

    SetBossBgmHook.call(bgmctrl, bgm_boss_conv_param_id, boss_bgm_state)
}

unsafe fn area_bgm_update_detour(cssound: usize, delta: f32) {
    let program = Program::current();
    let area_param_id = resolve_area_param_id(cssound, &program);
    let current = *((cssound + 0x2f0) as *const i16);

    if current != 0 {
        let controller_ptr = *((cssound + 0x328) as *const usize);
        if controller_ptr == 0 {
            AreaBgmUpdateHook.call(cssound, delta);
            return;
        }

        let repo = match SoloParamRepository::instance() {
            Ok(r) => r,
            Err(_) => {
                eprintln!("[unlock_wwise_states] failed to acquire param repository instance");
                AreaBgmUpdateHook.call(cssound, delta);
                return;
            }
        };

        let row = match repo.get::<WwiseValueToStrParam_EnvPlaceType>(area_param_id as u32) {
            Some(r) => r,
            None => {
                eprintln!("[unlock_wwise_states] failed to lookup area param {area_param_id}");
                AreaBgmUpdateHook.call(cssound, delta);
                return;
            }
        };

        if let Ok(param_str) = std::str::from_utf8(row.param_str()) {
            // TODO this is NOT the correct array, 0xf58 is for BgmPlaceType!
            let slot = (controller_ptr + 0xf58 + AREA_BGM_STATE_IDX as usize * 32) as *mut u8;
            //write_param_str(slot, param_str);
            write_param_str(slot, "Bgm_600_TombstoneCrater");

            // NOTE This happens quite frequently, so, keep it quiet
            //println!("[unlock_wwise_states] unlocking area bgm {param_str}");
            //let old_str = unsafe { CStr::from_ptr(slot as *const i8).to_str().unwrap() };
        } else {
            eprintln!("[unlock_wwise_states] area param {area_param_id} not found");
        }
    }

    AreaBgmUpdateHook.call(cssound, delta)
}

// TODO hook into _UpdateBgmState and fix BgmPlaceType, maybe Set_State_EnvPlaceType is tied to it?
// TODO test with cheat engine
// TODO check where the BgmAreaContext fields are accessed
unsafe fn updatebgmstate_detour(bgmctrl: usize, bgmctx: usize, delta: f32) {
    UpdateBgmStateHook.call(bgmctrl, bgmctx, delta);

    // Somehow this resulted in FieldBattleState Invalid when inside a SoundRegion
    //let slot = (bgmctrl + 0xf58 + AREA_BGM_STATE_IDX as usize * 32) as *mut u8;
    //write_param_str(slot, "Bgm_600_TombstoneCrater");
    //unsafe { *(bgmctx as *mut i8).add(0x18).cast::<i16>() = 120; }
    //unsafe { *(bgmctx as *mut i8).add(0x1a).cast::<i16>() = 120 >> 10; }
}

#[no_mangle]
pub unsafe extern "system" fn DllMain(
    _hinstance: *mut c_void,
    reason: u32,
    _reserved: *mut c_void,
) -> bool {
    if reason != 1 {
        return true;
    }

    std::thread::spawn(|| {
        if let Err(e) = wait_for_system_init(&Program::current(), Duration::MAX) {
            eprintln!("[unlock_wwise_states] failed to wait for system init: {e}");
            return;
        }

        unsafe {
            let program = Program::current();
            arxan::disable_code_restoration(&program)
                .expect("Could not disable arxan code restoration");

            let resolve = |rva, label| -> Option<u64> {
                let va = program.rva_to_va(rva).ok();
                if va.is_none() {
                    eprintln!("[unlock_wwise_states] failed to resolve RVA for {label}");
                }
                va
            };

            let Some(boss_va) = resolve(SETBOSSBGM_RVA, "SetBossBgm") else {
                return;
            };
            let Some(area_va) = resolve(AREA_BGM_UPDATE_RVA, "AreaBgmUpdate") else {
                return;
            };
            let Some(bgm_state_va) = resolve(UPDATE_BGM_STATE_RVA, "UpdateBgmState") else {
                return;
            };

            let boss_fn =
                std::mem::transmute::<u64, unsafe extern "C" fn(usize, u32, i32) -> ()>(boss_va);
            let area_fn =
                std::mem::transmute::<u64, unsafe extern "C" fn(usize, f32) -> ()>(area_va);
            let bgm_state_fn = std::mem::transmute::<
                u64,
                unsafe extern "C" fn(usize, usize, f32) -> (),
            >(bgm_state_va);

            if let Err(e) = SetBossBgmHook.initialize(boss_fn, |bgmctrl, param, state| {
                setbossbgm_detour(bgmctrl, param, state)
            }) {
                eprintln!("[unlock_wwise_states] failed to initialize SetBossBgm detour: {e}");
                return;
            }
            if let Err(e) = SetBossBgmHook.enable() {
                eprintln!("[unlock_wwise_states] failed to enable SetBossBgm detour: {e}");
                return;
            }

            if let Err(e) = AreaBgmUpdateHook.initialize(area_fn, |cssound, delta| {
                area_bgm_update_detour(cssound, delta)
            }) {
                eprintln!("[unlock_wwise_states] failed to initialize AreaBgmUpdate detour: {e}");
                return;
            }
            if let Err(e) = AreaBgmUpdateHook.enable() {
                eprintln!("[unlock_wwise_states] failed to enable AreaBgmUpdate detour: {e}");
            }

            if let Err(e) = UpdateBgmStateHook.initialize(bgm_state_fn, |bgmctrl, bgmctx, delta| {
                updatebgmstate_detour(bgmctrl, bgmctx, delta)
            }) {
                eprintln!("[unlock_wwise_states] failed to initialize UpdateBgmState detour: {e}");
            }
            if let Err(e) = UpdateBgmStateHook.enable() {
                eprintln!("[unlock_wwise_states] failed to enable UpdateBgmState detour: {e}");
            }
        }

        println!("[unlock_wwise_states] is now active!");
    });

    true
}

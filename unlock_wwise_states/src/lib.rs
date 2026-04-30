//! Elden Ring has two arrays defining allowed BGM state strings. This dll will patch 
//! these with whatever state the caller wants to set, effectively disabling 
//! verification and allowing for arbitrary strings.
//!
//! - SetBossBgm    -> CSSoundBgmController+0x238 (WwiseValueToStrParam_BgmBossChrIdConv)
//! - FUN_140dae090 -> CSSoundBgmController+0xf58 (WwiseValueToStrParam_EnvPlaceType)

#![allow(non_snake_case)]

use eldenring::cs::*;
use eldenring::sprj::*;
use retour::static_detour;
use rva::RVA_GLOBAL_FIELD_AREA;
use std::ffi::c_void;
use std::time::Duration;

use eldenring_util::system::wait_for_system_init;
use shared::program::Program;


const SETBOSSBGM_RVA: u32 = 0xdb2f70;
const AREA_BGM_UPDATE_RVA: u32 = 0xdae090;
const GLOBAL_WORLDSOUNDMAN_RVA: u32 = 0x3d6f708;
const BOSS_BGM_STATE_IDX: u8 = 0;
const AREA_BGM_STATE_IDX: u8 = 0;


static_detour! {
    static SetBossBgmHook: unsafe extern "C" fn(usize, u32, i32) -> ();
    static AreaBgmUpdateHook: unsafe extern "C" fn(usize, f32) -> ();
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
    let field_area_ptr = *(program.rva_to_va(RVA_GLOBAL_FIELD_AREA).unwrap()
        as *const *const FieldArea);
    let mut area_param_id: i16 = if field_area_ptr.is_null() {
        0
    } else {
        let field_area = &*field_area_ptr;

        // field_0xb6 - current area bgm id
        let mut s = *((field_area_ptr as usize + 0xb6) as *const i16);

        // GetCurrentBlockId result is at FieldArea+0x2c
        let area_id = *((field_area_ptr as usize + 0x2c) as *const u32);
        if area_id == 61 {
            if s == 999 {
                s = 50;
            }
            // field_0xf8
            let f8 = *((field_area_ptr as usize + 0xf8) as *const i16);
            if f8 != 999 {
                s = f8;
            }
        }
        s
    };

    // --- WorldSoundMan branch ---
    // Need to use the RVA, not mapped in fromsoft-rs yet
    let wsm_ptr = *(program.rva_to_va(GLOBAL_WORLDSOUNDMAN_RVA).unwrap()
        as *const usize);
    if wsm_ptr != 0 {
        // field38_0x5c28
        let inner = *((wsm_ptr + 0x5c28) as *const usize);
        if inner != 0 {
            // +0x364
            let s1 = *((inner + 0x364) as *const i16);
            if s1 >= 0 {
                area_param_id = s1;
            }
        }
    }

    // --- cssound override ---
    // field_0x435 (char, non-zero means override active)
    if *((cssound + 0x435) as *const u8) != 0 {
        area_param_id = *((cssound + 0x436) as *const i16);
    }

    area_param_id
}

// bgmctrl: CSSoundBgmController
unsafe fn setbossbgm_detour(bgmctrl: usize, bgm_boss_conv_param_id: u32, boss_bgm_state: i32) {
    if let Ok(repo) = SoloParamRepository::instance()
        && let Some(row) = repo.get::<WwiseValueToStrParam_BgmBossChrIdConv>(bgm_boss_conv_param_id)
        && let Ok(param_str) = std::str::from_utf8(row.param_str())
    {
        // allowed values array at 0x238
        let slot = (bgmctrl + 0x238 + BOSS_BGM_STATE_IDX * 32) as *mut u8;
        write_param_str(slot, param_str);
    }

    SetBossBgmHook.call(bgmctrl, bgm_boss_conv_param_id, boss_bgm_state)
}

unsafe fn area_bgm_update_detour(cssound: usize, delta: f32) {
    let program = Program::current();

    let area_param_id = resolve_area_param_id(cssound, &program);

    // Mirror the original's early-out: only act when the value changed
    let current = *((cssound + 0x2f0) as *const i16);
    if current != area_param_id {
        // Acquire CSSoundBgmController from CSSoundImp+0x328
        let controller_ptr = *((cssound + 0x328) as *const usize);

        if controller_ptr != 0 {
            if let Ok(repo) = SoloParamRepository::instance()
                && let Some(row) = repo.get::<WwiseValueToStrParam_EnvPlaceType>(area_param_id as u32)
                && let Ok(param_str) = std::str::from_utf8(row.param_str())
            {
                // allowed values array at +0xf58
                let slot = (controller_ptr + 0xf58 + AREA_BGM_STATE_IDX * 32) as *mut u8;
                write_param_str(slot, param_str);
            }
        }
    }

    // Original proceeds: writes field_0x2f0, calls SetEnvPlaceTypeId, etc.
    AreaBgmUpdateHook.call(cssound, delta)
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
            eprintln!("[bgm_hooks] failed to wait for system init: {e}");
            return;
        }

        unsafe {
            let program = Program::current();

            let resolve = |rva, label| -> Option<u64> {
                program.rva_to_va(rva).or_else(|| {
                    eprintln!("[bgm_hooks] failed to resolve RVA for {label}");
                    None
                })
            };

            let Some(boss_va) = resolve(SETBOSSBGM_RVA, "SetBossBgm") else { return };
            let Some(area_va) = resolve(AREA_BGM_UPDATE_RVA, "AreaBgmUpdate") else { return };

            let boss_fn =
                std::mem::transmute::<u64, unsafe extern "C" fn(usize, u32, i32) -> ()>(boss_va);
            let area_fn =
                std::mem::transmute::<u64, unsafe extern "C" fn(usize, f32) -> ()>(area_va);

            if let Err(e) = SetBossBgmHook.initialize(boss_fn, |bgmctrl, param, state| {
                setbossbgm_detour(bgmctrl, param, state)
            }) {
                eprintln!("[bgm_hooks] failed to initialize SetBossBgm detour: {e}");
                return;
            }
            if let Err(e) = SetBossBgmHook.enable() {
                eprintln!("[bgm_hooks] failed to enable SetBossBgm detour: {e}");
                return;
            }

            if let Err(e) = AreaBgmUpdateHook.initialize(area_fn, |cssound, delta| {
                area_bgm_update_detour(cssound, delta)
            }) {
                eprintln!("[bgm_hooks] failed to initialize AreaBgmUpdate detour: {e}");
                return;
            }
            if let Err(e) = AreaBgmUpdateHook.enable() {
                eprintln!("[bgm_hooks] failed to enable AreaBgmUpdate detour: {e}");
            }
        }
    });

    true
}
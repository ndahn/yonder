//! Elden Ring BGM state unlocker.
//!
//! CSSoundBgmController owns two fixed-size string allowlists. When the BGM
//! system resolves a Wwise state name from a param row, it checks the result
//! against the relevant list and rejects anything missing — preventing custom
//! Wwise states from being set.
//!
//! Allow lists in CSSoundBgmController:
//! - +0x238  (105 slots, BgmEnemyType)
//! - +0xf58  ( 53 slots, BgmPlaceType)

#![allow(non_snake_case)]

use pelite::pe64::Pe;
use retour::static_detour;
use std::ffi::c_void;
use std::mem;
use std::time::Duration;

use eldenring::cs::*;
use eldenring::util::system::wait_for_system_init;
use shared::program::Program;
use shared::{arxan, FromStatic};

const SETBOSSBGM_RVA: u32 = 0xdb2f70;
const UPDATEBGMSTATE_RVA: u32 = 0xdb55e0;

// Allowlists CSSoundBgmController.
const BOSS_BGM_OFFSET: usize = 0x238;
const PLACE_TYPE_OFFSET: usize = 0xf58;
// Slot 0 is "None" and not validated, so we use slot 1 as our scratch slot.
const SCRATCH_SLOT: usize = 1;

// Resolved BgmPlaceType id lives in the low 16 bits of areaVariation on
// BgmControllerContext, written by _UpdateBgmState's priority chain.
const CTX_AREA_VARIATION: usize = 0x1c;

static_detour! {
    static SetBossBgmHook: unsafe extern "C" fn(usize, u32, i32) -> ();
    static UpdateBgmStateHook: unsafe extern "C" fn(usize, usize, f32) -> ();
}

/// True once the game has written content into slot 0 of an allowlist.
/// Used as a gate to avoid touching the array during early-tick init.
unsafe fn allowlist_ready(controller: usize, base: usize) -> bool {
    controller != 0 && *((controller + base) as *const u8) != 0
}

/// Overwrite a 32-byte allowlist slot with a null-terminated string.
unsafe fn write_slot(controller: usize, base: usize, idx: usize, s: &str) {
    let slot = (controller + base + idx * 32) as *mut u8;
    std::ptr::write_bytes(slot, 0, 32);
    let n = s.len().min(31);
    std::ptr::copy_nonoverlapping(s.as_ptr(), slot, n);
}

unsafe fn setbossbgm_detour(controller: usize, param_id: u32, state: i32) {
    if !allowlist_ready(controller, BOSS_BGM_OFFSET) {
        return;
    }

    if let Ok(repo) = SoloParamRepository::instance() {
        if let Some(row) = repo.get::<WwiseValueToStrParam_BgmBossChrIdConv>(param_id) {
            if let Ok(name) = std::str::from_utf8(row.param_str()) {
                println!("[unlock_wwise_states] BgmEnemyType -> {name}");
                write_slot(controller, BOSS_BGM_OFFSET, SCRATCH_SLOT, name);
            }
        }
    }
    SetBossBgmHook.call(controller, param_id, state);
}

unsafe fn updatebgmstate_detour(controller: usize, context: usize, delta: f32) {
    UpdateBgmStateHook.call(controller, context, delta);

    // Gate everything on the controller's allowlist being populated. Early
    // ticks during sound-system init can fire before that happens.
    if context == 0 || !allowlist_ready(controller, PLACE_TYPE_OFFSET) {
        return;
    }

    // Resolved param id from the priority chain (field420/421/418/419/422).
    let param_id = *((context + CTX_AREA_VARIATION) as *const i32) as i16;
    if param_id < 0 || param_id == 999 {
        return; // unset/sentinel — let vanilla handle the default
    }

    let Ok(repo) = SoloParamRepository::instance() else {
        return;
    };
    let Some(row) = repo.get::<WwiseValueToStrParam_EnvPlaceType>(param_id as u32) else {
        return;
    };
    let Ok(name) = std::str::from_utf8(row.param_str()) else {
        return;
    };

    // TODO always reports for some reason
    // if name.chars().count() > 31 {
    //     println!("[unlock_wwise_states] {name} is longer than 31 characters and will be truncated");
    // }

    write_slot(controller, PLACE_TYPE_OFFSET, SCRATCH_SLOT, name);
}

fn install_hooks() -> Result<(), String> {
    let program = Program::current();
    unsafe {
        arxan::disable_code_restoration(&program).map_err(|e| format!("disable arxan: {e:?}"))?;
    }

    let boss_va = program
        .rva_to_va(SETBOSSBGM_RVA)
        .map_err(|_| "resolve SetBossBgm RVA".to_string())?;
    let update_va = program
        .rva_to_va(UPDATEBGMSTATE_RVA)
        .map_err(|_| "resolve _UpdateBgmState RVA".to_string())?;

    unsafe {
        let boss_fn: unsafe extern "C" fn(usize, u32, i32) = mem::transmute(boss_va);
        let update_fn: unsafe extern "C" fn(usize, usize, f32) = mem::transmute(update_va);

        SetBossBgmHook
            .initialize(boss_fn, |c, p, s| setbossbgm_detour(c, p, s))
            .map_err(|e| format!("init SetBossBgm: {e}"))?;
        SetBossBgmHook
            .enable()
            .map_err(|e| format!("enable SetBossBgm: {e}"))?;

        UpdateBgmStateHook
            .initialize(update_fn, |c, x, d| updatebgmstate_detour(c, x, d))
            .map_err(|e| format!("init _UpdateBgmState: {e}"))?;
        UpdateBgmStateHook
            .enable()
            .map_err(|e| format!("enable _UpdateBgmState: {e}"))?;
    }

    Ok(())
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
            eprintln!("[unlock_wwise_states] wait_for_system_init: {e}");
            return;
        }
        match install_hooks() {
            Ok(()) => println!("[unlock_wwise_states] is now active!"),
            Err(e) => eprintln!("[unlock_wwise_states] {e}"),
        }
    });

    true
}

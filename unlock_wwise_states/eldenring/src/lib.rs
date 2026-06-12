//! Elden Ring BGM state unlocker.
//!
//! CSSoundBgmController owns two fixed-size string allowlists. When the BGM
//! system resolves a Wwise state name from a param row, it checks the result
//! against the relevant list and rejects anything missing -- preventing custom
//! Wwise states from being set.
//!
//! Allow lists in CSSoundBgmController:
//! - +0x238  (105 slots, BgmEnemyType)
//! - +0xf58  ( 53 slots, BgmPlaceType)
//!
//! RVAs are hardcoded as global constants below.

#![allow(non_snake_case)]

use pelite::pe64::Pe;
use retour::static_detour;
use std::ffi::c_void;
use std::mem;
use std::time::Duration;

use windows::Win32::Foundation::HINSTANCE;

use eldenring::cs::*;
use eldenring::util::system::wait_for_system_init;
use shared::program::Program;
use shared::{arxan, FromStatic};

// Functions we want to hook
const SETBOSSBGM_RVA: u32 = 0xdb2ec0;
const UPDATEBGMSTATE_RVA: u32 = 0xdb5530;
// Allowlist offsets inside CSSoundBgmController.
const BOSS_BGM_OFFSET: usize = 0x238;
const PLACE_TYPE_OFFSET: usize = 0xf58;
// 0: None, not used, 1: _BgmSilent, important for ending bgm music, 52: Reserved15
// See WwiseValueToStrParam_BgmBossChrIdConv, rows 1000000+
const SCRATCH_SLOT: usize = 52;

static_detour! {
    static SetBossBgmHook: unsafe extern "C" fn(usize, u32, i32) -> ();
    static UpdateBgmStateHook: unsafe extern "C" fn(usize, usize, f32) -> ();
}

// -- helpers -----------------------------------------------------------------

/// Returns true once the game has written content into slot 0 of an allowlist.
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

// -- detours -----------------------------------------------------------------

unsafe fn setbossbgm_detour(controller: usize, param_id: u32, state: i32) {
    if !allowlist_ready(controller, BOSS_BGM_OFFSET) {
        SetBossBgmHook.call(controller, param_id, state);
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
    resolve_place_type(controller, context);
    UpdateBgmStateHook.call(controller, context, delta);
}

unsafe fn resolve_place_type(controller: usize, context: usize) -> Option<()> {
    // Guard against early ticks before the allowlist is populated.
    if !allowlist_ready(controller, PLACE_TYPE_OFFSET) {
        return None;
    }

    // TODO for testing
    //let param_id = 600;
    let param_id = *((context + 0x0) as *const i32) as i16;
    if param_id < 0 || param_id == 999 {
        return None;
    }

    let repo = SoloParamRepository::instance().ok()?;
    let row = repo.get::<WwiseValueToStrParam_EnvPlaceType>(param_id as u32)?;
    let name = std::str::from_utf8(row.param_str()).ok()?;

    write_slot(controller, PLACE_TYPE_OFFSET, SCRATCH_SLOT, name);
    println!("[unlock_wwise_states] PLACE TYPE {name}");
    Some(())
}

// -- setup -------------------------------------------------------------------

fn install_hooks() -> Result<(), String> {
    let program = Program::current();
    unsafe {
        arxan::disable_code_restoration(&program).map_err(|e| format!("disable arxan: {e:?}"))?;
    }

    match program.rva_to_va(SETBOSSBGM_RVA) {
        Err(_) => {
            eprintln!("[unlock_wwise_states] could not resolve SETBOSSBGM_RVA, skipping hook")
        }
        Ok(va) => unsafe {
            let f: unsafe extern "C" fn(usize, u32, i32) = mem::transmute(va);
            SetBossBgmHook
                .initialize(f, |c, p, s| setbossbgm_detour(c, p, s))
                .map_err(|e| format!("init SetBossBgm: {e}"))?;
            SetBossBgmHook
                .enable()
                .map_err(|e| format!("enable SetBossBgm: {e}"))?;
        },
    }

    // TODO not working yet
    // match program.rva_to_va(UPDATEBGMSTATE_RVA) {
    //     Err(_) => {
    //         eprintln!("[unlock_wwise_states] could not resolve UPDATEBGMSTATE_RVA, skipping hook")
    //     }
    //     Ok(va) => unsafe {
    //         let f: unsafe extern "C" fn(usize, usize, f32) = mem::transmute(va);
    //         UpdateBgmStateHook
    //             .initialize(f, |c, x, d| updatebgmstate_detour(c, x, d))
    //             .map_err(|e| format!("init _UpdateBgmState: {e}"))?;
    //         UpdateBgmStateHook
    //             .enable()
    //             .map_err(|e| format!("enable _UpdateBgmState: {e}"))?;
    //     },
    // }

    Ok(())
}

#[no_mangle]
pub unsafe extern "system" fn DllMain(
    _hinstance: HINSTANCE,
    reason: u32,
    _reserved: *mut c_void,
) -> bool {
    if reason != 1 {
        return true;
    }

    std::thread::spawn(|| {
        if let Err(e) = wait_for_system_init(&Program::current(), Duration::from_secs(5)) {
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

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

// Functions and singletons
const SETBOSSBGM_RVA: u32 = 0xdb2ec0;
const SETAREABGM_RVA: u32 = 0xdadfe0;
const GLOBAL_FIELDAREA_RVA: u32 = 0x3d691d8;
const GLOBAL_WORLDSOUNDMAN_RVA: u32 = 0x3d6f708;
// Allowlist offsets inside CSSoundBgmController.
const BOSS_BGM_OFFSET: usize = 0x238;
const PLACE_TYPE_OFFSET: usize = 0xf58;
// 0: None, not used, 1: _BgmSilent, important for ending bgm music, 52: Reserved15
// See WwiseValueToStrParam_BgmBossChrIdConv, rows 1000000+
const BOSSBGM_SCRATCH_SLOT: usize = 52;
const PLACEBGM_SCRATCH_SLOT: usize = 2;

static_detour! {
    static SetBossBgmHook: unsafe extern "C" fn(usize, u32, i32) -> ();
    static SetAreaBgmHook: unsafe extern "C" fn(usize, f32) -> ();
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
                write_slot(controller, BOSS_BGM_OFFSET, BOSSBGM_SCRATCH_SLOT, name);
                println!("[unlock_wwise_states] unlocked BgmEnemyType {name}");
            }
        }
    }
    SetBossBgmHook.call(controller, param_id, state);
}

/// Reimplement the area_param_id (sVar6) resolution from FUN_140dae090
/// (the caller of the actual SetEnvPlaceTypeId function).
unsafe fn resolve_area_param_id(cssound: usize, program: &Program) -> i16 {
    // --- FieldArea branch ---
    let field_area_ptr =
        *(program.rva_to_va(GLOBAL_FIELDAREA_RVA).unwrap() as *const *const FieldArea);
    
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

/// TODO this works, but still doesn't allow for custom BgmPlaceTypes
unsafe fn setareabgm_detour(cssound: usize, delta: f32) {
    let program = Program::current();
    let area_param_id = resolve_area_param_id(cssound, &program);
    let current = *((cssound + 0x2f0) as *const i16);

    if current != area_param_id {
        (|| -> Option<()> {
            let controller = *((cssound + 0x328) as *const usize);
            if controller == 0 || !allowlist_ready(controller, PLACE_TYPE_OFFSET) {
                return None;
            }

            // The param ID is for EnvPlaceType, but the allowlist is for BgmPlaceType. The 
            // vanilla entries have some mysterious correspondence with each other (probably 
            // hardcoded ID-pairs, see notes). However, all corresponding rows in BgmPlaceType 
            // are at 11000000+, so we can just get something corresponding. To prevent 
            // interfering with vanilla stuff we require custom areas to be at 600+.
            // Note that we allow param_ids >999, but this is untested and might cause problems.
            if area_param_id < 600 || area_param_id == 999 {
                return None;
            }

            let repo = SoloParamRepository::instance().ok()?;
            let row = repo.get::<WwiseValueToStrParam_BgmBossChrIdConv>(area_param_id as u32 + 11000000)?;
            let name = std::str::from_utf8(row.param_str()).ok()?;

            write_slot(controller, PLACE_TYPE_OFFSET, PLACEBGM_SCRATCH_SLOT, name);
            println!("[unlock_wwise_states] unlocked BgmPlaceType {name}");
            Some(())
        })();
    }

    SetAreaBgmHook.call(cssound, delta);
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

    match program.rva_to_va(SETAREABGM_RVA) {
        Err(_) => {
            eprintln!("[unlock_wwise_states] could not resolve SETAREABGM_RVA, skipping hook")
        }
        Ok(va) => unsafe {
            let f: unsafe extern "C" fn(usize, f32) = mem::transmute(va);
            SetAreaBgmHook
                .initialize(f, |s, d| setareabgm_detour(s, d))
                .map_err(|e| format!("init SetEnvPlaceType: {e}"))?;
            SetAreaBgmHook
                .enable()
                .map_err(|e| format!("enable SetEnvPlaceType: {e}"))?;
        },
    }

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

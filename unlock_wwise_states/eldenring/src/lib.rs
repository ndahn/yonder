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
//! RVAs are loaded at runtime from `unlock_wwise_states.yaml`
//! located next to the DLL.

#![allow(non_snake_case)]

use pelite::pe64::Pe;
use retour::static_detour;
use std::ffi::c_void;
use std::mem;
use std::path::PathBuf;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Duration;

use windows::Win32::Foundation::{HINSTANCE, HMODULE};
use windows::Win32::System::LibraryLoader::GetModuleFileNameW;

use eldenring::cs::*;
use eldenring::util::system::wait_for_system_init;
use shared::program::Program;
use shared::{arxan, FromStatic};

// Allowlist offsets inside CSSoundBgmController.
const BOSS_BGM_OFFSET: usize = 0x238;
const PLACE_TYPE_OFFSET: usize = 0xf58;
// Slot 0 is "None" (not validated); slot 1 is our scratch slot.
const SCRATCH_SLOT: usize = 1;

// Stored as usize because AtomicPtr requires Sync, and *mut c_void is not Sync.
static DLL_HINSTANCE: AtomicUsize = AtomicUsize::new(0);

static_detour! {
    static SetBossBgmHook: unsafe extern "C" fn(usize, u32, i32) -> ();
    static UpdateBgmStateHook: unsafe extern "C" fn(usize, usize, f32) -> ();
}

/// RVAs deserialised from `unlock_wwise_states.yaml`.
/// Unknown keys are silently ignored; missing keys warn and skip that hook.
#[derive(serde::Deserialize)]
struct Config {
    #[serde(rename = "SETBOSSBGM_RVA")]
    setbossbgm_rva: Option<u32>,
    #[serde(rename = "UPDATEBGMSTATE_RVA")]
    updatebgmstate_rva: Option<u32>,
}

/// Resolve the config path as `<dll_dir>/unlock_wwise_states.yaml`.
fn config_path() -> Result<PathBuf, String> {
    let raw = DLL_HINSTANCE.load(Ordering::Relaxed);
    if raw == 0 {
        return Err("HINSTANCE not set".into());
    }

    // HINSTANCE -> HMODULE via From; both wrap *mut c_void in windows 0.61.
    let hmodule: HMODULE = HINSTANCE(raw as *mut c_void).into();
    let mut buf = vec![0u16; 260];
    let len = unsafe { GetModuleFileNameW(Some(hmodule), &mut buf) };
    if len == 0 {
        return Err("GetModuleFileNameW failed".into());
    }

    let path = PathBuf::from(String::from_utf16_lossy(&buf[..len as usize]));
    Ok(path
        .parent()
        .ok_or("DLL path has no parent")?
        .join("rvas.yaml"))
}

fn load_config() -> Result<Config, String> {
    let path = config_path()?;
    let text =
        std::fs::read_to_string(&path).map_err(|e| format!("read {}: {e}", path.display()))?;
    serde_yaml::from_str(&text).map_err(|e| format!("parse {}: {e}", path.display()))
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
    // Gate everything on the controller's allowlist being populated. Early
    // ticks during sound-system init can fire before that happens.
    if !allowlist_ready(controller, PLACE_TYPE_OFFSET) {
        return;
    }

    // TODO test
    let param_id = 600;
    // Resolved param id from the priority chain (field420/421/418/419/422).
    //let param_id = *((context + CTX_AREA_VARIATION) as *const i32) as i16;
    if param_id < 0 || param_id == 999 {
        return; // unset / sentinel -- let vanilla handle the default
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

    write_slot(controller, PLACE_TYPE_OFFSET, SCRATCH_SLOT, name);
    println!("[unlock_wwise_states] PLACE TYPE {name}");

    UpdateBgmStateHook.call(controller, context, delta);

    // TODO always reports for some reason
    // if name.chars().count() > 31 {
    //     println!("[unlock_wwise_states] {name} is longer than 31 characters and will be truncated");
    // }
}

// -- setup -------------------------------------------------------------------

fn install_hooks(cfg: &Config) -> Result<(), String> {
    let program = Program::current();
    unsafe {
        arxan::disable_code_restoration(&program).map_err(|e| format!("disable arxan: {e:?}"))?;
    }

    match cfg.setbossbgm_rva {
        None => {
            eprintln!("[unlock_wwise_states] SETBOSSBGM_RVA not found in config, skipping hook")
        }
        Some(rva) => match program.rva_to_va(rva) {
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
        },
    }

    match cfg.updatebgmstate_rva {
        None => {
            eprintln!("[unlock_wwise_states] UPDATEBGMSTATE_RVA not found in config, skipping hook")
        }
        Some(rva) => match program.rva_to_va(rva) {
            Err(_) => eprintln!(
                "[unlock_wwise_states] could not resolve UPDATEBGMSTATE_RVA, skipping hook"
            ),
            Ok(va) => unsafe {
                let f: unsafe extern "C" fn(usize, usize, f32) = mem::transmute(va);
                UpdateBgmStateHook
                    .initialize(f, |c, x, d| updatebgmstate_detour(c, x, d))
                    .map_err(|e| format!("init _UpdateBgmState: {e}"))?;
                UpdateBgmStateHook
                    .enable()
                    .map_err(|e| format!("enable _UpdateBgmState: {e}"))?;
            },
        },
    }

    Ok(())
}

#[no_mangle]
pub unsafe extern "system" fn DllMain(
    hinstance: HINSTANCE,
    reason: u32,
    _reserved: *mut c_void,
) -> bool {
    if reason != 1 {
        return true;
    }

    // Store before spawning - the thread may not start until later.
    DLL_HINSTANCE.store(hinstance.0 as usize, Ordering::Relaxed);

    std::thread::spawn(|| {
        if let Err(e) = wait_for_system_init(&Program::current(), Duration::from_secs(5)) {
            eprintln!("[unlock_wwise_states] wait_for_system_init: {e}");
            return;
        }
        let cfg = match load_config() {
            Ok(c) => c,
            Err(e) => {
                eprintln!("[unlock_wwise_states] config: {e}");
                return;
            }
        };
        match install_hooks(&cfg) {
            Ok(()) => println!("[unlock_wwise_states] is now active!"),
            Err(e) => eprintln!("[unlock_wwise_states] {e}"),
        }
    });

    true
}

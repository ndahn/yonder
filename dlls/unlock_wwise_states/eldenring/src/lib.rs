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

#![allow(non_snake_case)]

use pelite::pe64::Pe;
use retour::static_detour;
use serde::Deserialize;
use std::ffi::c_void;
use std::mem;
use std::path::PathBuf;
use std::sync::OnceLock;
use std::time::Duration;

use windows::Win32::Foundation::{HINSTANCE, HMODULE};
use windows::Win32::System::LibraryLoader::GetModuleFileNameW;

use eldenring::cs::*;
use eldenring::util::system::wait_for_system_init;
use shared::program::Program;
use shared::{arxan, FromStatic};

// Defaults, used when mana.yaml is absent or a field is missing.
const SETBOSSBGM_RVA: u32 = 0xdb4c90;
const BOSS_BGM_OFFSET: usize = 0x238;
// 0: None, not used, 1: _BgmSilent, important for ending bgm music, 52: Reserved15
// See WwiseValueToStrParam_BgmBossChrIdConv, rows 1000000+
const BOSSBGM_SCRATCH_SLOT: usize = 52;

static_detour! {
    static SetBossBgmHook: unsafe extern "C" fn(usize, u32, i32) -> ();
}

// -- config --------------------------------------------------------------

#[derive(Deserialize, Default)]
#[serde(default)]
struct RvaConfig {
    set_boss_bgm: Option<u32>,
}

#[derive(Deserialize, Default)]
#[serde(default)]
struct WwiseConfig {
    bossbgm_allowlist_offset: Option<usize>,
    bossbgm_scratch_slot: Option<usize>,
}

#[derive(Deserialize, Default)]
#[serde(default)]
struct ManaConfig {
    rvas: RvaConfig,
    unlock_wwise_states: WwiseConfig,
}

static CONFIG: OnceLock<ManaConfig> = OnceLock::new();

/// directory containing this dll, resolved from its module handle.
unsafe fn dll_directory(hinstance: HINSTANCE) -> Option<PathBuf> {
    let mut buf = [0u16; 260];
    let module = HMODULE(hinstance.0);
    let len = GetModuleFileNameW(Some(module), &mut buf);
    if len == 0 {
        return None;
    }
    PathBuf::from(String::from_utf16_lossy(&buf[..len as usize]))
        .parent()
        .map(|p| p.to_path_buf())
}

/// load mana.yaml next to the dll, falling back to defaults on any error.
unsafe fn load_config(hinstance: HINSTANCE) -> ManaConfig {
    let Some(dir) = dll_directory(hinstance) else {
        return ManaConfig::default();
    };
    match std::fs::read_to_string(dir.join("mana.yaml")) {
        Ok(text) => serde_yaml::from_str(&text).unwrap_or_default(),
        Err(_) => ManaConfig::default(),
    }
}

fn config() -> &'static ManaConfig {
    CONFIG.get_or_init(ManaConfig::default)
}

fn set_boss_bgm_rva() -> u32 {
    config().rvas.set_boss_bgm.unwrap_or(SETBOSSBGM_RVA)
}

fn boss_bgm_offset() -> usize {
    config()
        .unlock_wwise_states
        .bossbgm_allowlist_offset
        .unwrap_or(BOSS_BGM_OFFSET)
}

fn bossbgm_scratch_slot() -> usize {
    config()
        .unlock_wwise_states
        .bossbgm_scratch_slot
        .unwrap_or(BOSSBGM_SCRATCH_SLOT)
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
    let offset = boss_bgm_offset();
    if !allowlist_ready(controller, offset) {
        SetBossBgmHook.call(controller, param_id, state);
        return;
    }

    if let Ok(repo) = SoloParamRepository::instance() {
        if let Some(row) = repo.get::<WwiseValueToStrParam_BgmBossChrIdConv>(param_id) {
            if let Ok(name) = std::str::from_utf8(row.param_str()) {
                write_slot(controller, offset, bossbgm_scratch_slot(), name);
                println!("[unlock_wwise_states] unlocked BgmEnemyType {name}");
            }
        }
    }
    SetBossBgmHook.call(controller, param_id, state);
}

// -- setup -------------------------------------------------------------------

fn install_hooks() -> Result<(), String> {
    let program = Program::current();
    unsafe {
        arxan::disable_code_restoration(&program).map_err(|e| format!("disable arxan: {e:?}"))?;
    }

    match program.rva_to_va(set_boss_bgm_rva()) {
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

    // read mana.yaml before anything else uses config()
    CONFIG.set(load_config(hinstance)).ok();

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

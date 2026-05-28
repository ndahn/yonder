//! Elden Ring BGM state unlocker.
//! Hooks SetBossBgm and AreaBgmUpdate, resolves param strings from the param
//! repository, and calls AK::SoundEngine::SetState directly — bypassing the
//! internal string-array validation entirely.

#![allow(non_snake_case)]

use pelite::pe64::Pe;
use retour::static_detour;
use std::ffi::c_void;
use std::mem;
use std::num::Wrapping;
use std::sync::LazyLock;
use std::time::Duration;
use windows::core::{s, PCWSTR};
use windows::Win32::System::LibraryLoader::{GetModuleHandleW, GetProcAddress};

use eldenring::cs::*;
use eldenring::util::system::wait_for_system_init;
use shared::program::Program;
use shared::{arxan, FromStatic};

const SETBOSSBGM_RVA: u32 = 0xdb2f70;
const UPDATEBGMSTATE_RVA: u32 = 0xdb55e0;

static_detour! {
    static SetBossBgmHook: unsafe extern "C" fn(usize, u32, i32) -> ();
}

static_detour! {
    static UpdateBgmStateHook: unsafe extern "C" fn(usize, usize, f32) -> ();
}

// --- Wwise AK::SoundEngine::SetState ---

static SET_STATE: LazyLock<Option<extern "system" fn(u32, u32) -> u32>> =
    LazyLock::new(|| unsafe {
        let module = GetModuleHandleW(PCWSTR::null()).ok()?;
        let export = GetProcAddress(module, s!("?SetState@SoundEngine@AK@@YA?AW4AKRESULT@@KK@Z"))?;
        Some(mem::transmute(export))
    });

fn set_state(state_group: u32, state: u32) {
    if let Some(f) = *SET_STATE {
        f(state_group, state);
    }
}

/// FNV-1 hash (lowercase) matching the Wwise string-ID convention.
fn wwise_hash(s: &str) -> u32 {
    const BASE: Wrapping<u32> = Wrapping(2166136261);
    const PRIME: Wrapping<u32> = Wrapping(16777619);
    let mut h = BASE;
    for b in s.to_ascii_lowercase().bytes() {
        h *= PRIME;
        h ^= b as u32;
    }
    h.0
}

#[repr(C)]
pub struct CSSoundBgmController {
    unk0: [u8; 0x1ce],
    // @0x1ce set from SoundRegion; 999 if not set, but not changed if string is rejected
    pub active_env_place_type: u16,
    unk1: [u8; 0x30],
    // @0x200 set if a valid ambience bgm is active
    pub ambience_valid: u16,
    unk2: [u8; 0x36],
    // @0x238 allowlist for BgmEnemyType
    pub allowed_boss_bgm: [[u8; 0x20]; 105],
    // @0xf58 allowlist for BgmPlaceType
    pub allowed_env_bgm: [[u8; 0x20]; 53],
}

// --- Detours ---

unsafe fn setbossbgm_detour(bgmctrl: usize, bgm_boss_conv_param_id: u32, boss_bgm_state: i32) {
    SetBossBgmHook.call(bgmctrl, bgm_boss_conv_param_id, boss_bgm_state);

    let repo = match SoloParamRepository::instance() {
        Ok(r) => r,
        Err(_) => return,
    };

    let row = match repo.get::<WwiseValueToStrParam_BgmBossChrIdConv>(bgm_boss_conv_param_id) {
        Some(r) => r,
        None => return,
    };

    if let Ok(param_str) = std::str::from_utf8(row.param_str()) {
        let group = wwise_hash("BgmEnemyType");
        let state = wwise_hash(param_str);
        println!("[unlock_wwise_states] BgmEnemyType {param_str}");
        set_state(group, state);
    }
}

unsafe fn updatebgmstate_detour(soundbgmctrl: usize, bgmctrlctx: usize, delta: f32) {
    UpdateBgmStateHook.call(soundbgmctrl, bgmctrlctx, delta);

    let controller = unsafe { &mut *(soundbgmctrl as *mut CSSoundBgmController) };
    let env_place_type = controller.active_env_place_type as u32;

    if env_place_type != 999 {
        let repo = match SoloParamRepository::instance() {
            Ok(r) => r,
            Err(_) => return,
        };

        let row = match repo.get::<WwiseValueToStrParam_EnvPlaceType>(env_place_type) {
            Some(r) => r,
            None => return,
        };

        if let Ok(param_str) = std::str::from_utf8(row.param_str()) {
            let group = wwise_hash("Set_State_EnvPlaceType");
            let state = wwise_hash(param_str);
            // Called every frame, keep it quiet
            //println!("[unlock_wwise_states] Set_State_EnvPlaceType {param_str}");
            set_state(group, state);
            controller.ambience_valid = 1;
        }
    }
}

// --- DllMain ---

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
                .expect("could not disable arxan code restoration");

            let resolve = |rva, label| -> Option<u64> {
                let va = program.rva_to_va(rva).ok();
                if va.is_none() {
                    eprintln!("[unlock_wwise_states] failed to resolve RVA for {label}");
                }
                va
            };

            // Boss BGM
            let Some(boss_va) = resolve(SETBOSSBGM_RVA, "SetBossBgm") else {
                return;
            };

            let boss_fn = mem::transmute::<u64, unsafe extern "C" fn(usize, u32, i32)>(boss_va);

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

            // Sound regions
            let Some(updatebgm_va) = resolve(UPDATEBGMSTATE_RVA, "UpdateBgmState") else {
                return;
            };

            let updatebgm_fn = mem::transmute::<u64, unsafe extern "C" fn(usize, usize, f32)>(updatebgm_va);

            if let Err(e) = UpdateBgmStateHook.initialize(updatebgm_fn, |soundbgmctrl, bgmctrlctx, delta| {
                updatebgmstate_detour(soundbgmctrl, bgmctrlctx, delta)
            }) {
                eprintln!("[unlock_wwise_states] failed to initialize UpdateBgmState detour: {e}");
                return;
            }
            if let Err(e) = UpdateBgmStateHook.enable() {
                eprintln!("[unlock_wwise_states] failed to enable UpdateBgmState detour: {e}");
                return;
            }
        }

        println!("[unlock_wwise_states] is now active!");
    });

    true
}

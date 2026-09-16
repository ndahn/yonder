# Summary
- the wwise decision tree for music is 
    - LoopCheck
    - BgmEnemyType
    - BgmPlaceType
    - BossBattleState
    - TimeZone
    - #1807931947 (unknown)
    - CommonPlaceType
- for ambience it is
    - LoopCheck
    - BgmEnemyType
    - BossBattleState
    - FallenLeaves
    - BgmPlaceType
    - StateWeatherType
    - Set_State_EnvPlaceType
- BgmPlaceType and Set_State_EnvPlaceType are set in MapDefaultInfoParam (BgmPlaceInfo and EnvPlaceInfo)
- 


- a SoundRegion references an EnvPlaceType row, but modifies BgmPlaceType
- the string for BgmPlaceType is taken from WwiseValueToStrParam_BgmBossChrIdConv
- updating the string in-game does not change it even if it has not been used yet
- the strings are all read only once at game startup
- rows are in different orders and there are different numbers of them
- changing a string in BgmBossChrIdConv *will* result in the game setting a different BgmPlaceType
- this means they are not matched by index or value -> hardcoded index map
- seems to be hidden *really* deep inside arxan (see below)


# Hook

```rs
/// From 1.16.2
const SETAREABGM_RVA: u32 = 0xdafdb0;
const GLOBAL_FIELDAREA_RVA: u32 = 0x3d691d8;
const GLOBAL_WORLDSOUNDMAN_RVA: u32 = 0x3d6f708;
const PLACE_TYPE_OFFSET: usize = 0xf58;
const PLACEBGM_SCRATCH_SLOT: usize = 2;

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

fn install_hooks() -> Result<(), String> {
    let program = Program::current();
    unsafe {
        arxan::disable_code_restoration(&program).map_err(|e| format!("disable arxan: {e:?}"))?;
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
```



# Overview
I couldn't find any pattern other than that regions affecting sound start at 7500 and regions affecting rendering start at 8500. I don't think the region ID has any relation to the other parameters. as long as it's within the correct range. 

There are two params relevant to SoundRegions: `WwiseValueToStrParam_BgmBossChrIdConv` and `WwiseValueToStrParam_EnvPlaceType`. The former contains the boss bgm strings AND the BgmPlaceType strings (all starting with Bgm). The thing is, the SoundRegions refer to the EnvPlaceType param, where the strings start with Env.

In Limgrave, the values for BgmPlaceType and EnvPlaceType default to `Bgm_000_Green` and `Env_000_Green`. I set my region env param to 100, which is Env_100_Castle. And then I changed the corresponding Bgm_100_Castle string in BgmBossChrIdConv (!) to something else. Lo and behold, when I enter the region the EnvPlaceType stays at Env_000_Green and the BgmPlaceType is updated! And I'm left scratching my brain =_=

There is seemingly no relation between the two params whatsoever. Their order is different, the row IDs are unrelated, and the string I put in didn't even have the same number in the middle anymore. 


# Results after several long debug sessions with claude

## RVAs (relative to eldenring.exe base 1.16.2):
- 0x225C130 — CAkStateMgr::SetStateInternal (applies a state value; +0x14C/0x225C27C writes
AkStateGroupChunk.m_ulActualState)
- 0x2366720 — BGM-place commit (FUN_142366710): reads {group@+0x38, value@+0x3C} from its arg record and calls
SetStateInternal; dispatched via fn-ptr table (xref region ~0x315B558)
- 0x23D4240 — Wwise node SetValue+notify (store mov [rdi+8],ebx @ 0x23D42D2, then or [owner+0xC8],1)
- 0x25B8B0 — GetState (out-param); reads current value at 0x25B8E5; group-not-found default = 0x2CA33BDB
- 0x4C5947B — Bgm name-table construction (string-copy inside the loader); Arxan code-virtualized (VM)
- 0x4850430 — g_pStateMgr global pointer
- ~0xE14862 / ~0xE174xx — game-side BGM-place manager funclets on the set path

## Key hashes / IDs:
- BgmPlaceType state group = 0x8F9DABF2
- Bgm_999_None = 0xFD3297AC; Bgm_000_Green = 0x57DB6AD4
- Wwise value hash = FNV‑1 32-bit of the lowercased name (verified)

## Mechanisms:
- BgmPlaceType is a Wwise State Group; setting it goes game → SetStateInternal → AkStateGroupChunk. The "request"
record and the AkStateGroupChunk both carry {group@+0x38, value@+0x3C}.
- The custom value isn't rejected by Wwise — the game resolves a Bgm value upstream and feeds it to SetState; a failed
resolution yields Bgm_999_None.
- Env→Bgm tables store name strings, keyed by param row id; the Wwise hash is computed on demand only at SetState.
- The Env→Bgm correspondence is pre-baked by row/index, not by name (renaming the Bgm entry to a different suffix does
not break resolution). It is built once at process start (Env table/strings persist across area reloads; only the Bgm
runtime is rebuilt on area load and reads the existing correspondence).
- Env_180 ↔ Bgm idx 13 / param row 11000013 / global index 175 (a row→global-index table exists: a 0x10000000-series
table occupies low globals, Bgm 0x11000000-series starts at global 162). Table sizes: 45 Env entries, 52(+1) Bgm.
- The correspondence is not a resident flat lookup array (no encoding found in heap or image); it lives in pre-baked
data consumed by the virtualized loader.
- Wwise state value registry per group is a sorted-by-hash list of {key, 50, 100, hash} 12-byte records; the custom
value is a valid registered member.

## Tooling facts:
- CE scan_all (any protection) only scans heap/pool; aob_scan reaches the eldenring.exe image.
- Hardware breakpoints that fire during a region transition crash the game under normal Arxan; an anti-Arxan DLL prevents the crashes but does not de-virtualize the loader code.


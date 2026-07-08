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


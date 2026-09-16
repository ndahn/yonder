#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <cstdint>
#include <cstring>
#include <filesystem>
#include <optional>
#include <thread>
#include <unordered_map>

#include <spdlog/sinks/daily_file_sink.h>
#include <spdlog/sinks/stdout_color_sinks.h>
#include <spdlog/spdlog.h>
#include <yaml-cpp/yaml.h>

#include <elden-x/params.hpp>
#include <elden-x/singletons.hpp>
#include <elden-x/utils/modutils.hpp>

namespace unlock_wwise_states
{

static std::filesystem::path dll_folder;

static constexpr uintptr_t setbossbgm_rva = 0xefd0e0;
static constexpr size_t bossbgm_list_offset = 0x1b0;
static constexpr size_t scratch_slot = 29;  // _CL_Reserved07
static constexpr size_t item_stride = 32;
static constexpr size_t num_bossbgm = 106;
static constexpr size_t num_bgmplace = 48;

static constexpr const char *config_filename = "unlock_wwise_states_nr.yaml";

// rowid -> custom bgm state name, loaded from config_filename
static std::unordered_map<uint32_t, std::string> bossbgm_overrides;

// BgmEnemyType "reset-to-None" write neutralizer.
//
// The game clears controller+0x124 (BgmEnemyType, 0 = None) via
//     mov [rbx+0x124], eax        ; 89 83 24 01 00 00   (eax = 0)
// This is in arxan territory, but we can still NOP those 6 bytes so the 
// custom value survives and custom boss music keeps playing.
//
// There are ~15 stores to +0x124 across the module, so we can't key on the
// store alone. We anchor on the game-logic guard that precedes THIS store:
//     movzx ebp,[rdi+0x0A]
//     cmp ebp, 05                 ; 83 FD 05
//     jmp <arxan rel32>           ; E9 ?? ?? ?? ??
//     mov [rbx+0x124], eax        ; 89 83 24 01 00 00   <-- NOP these 6
// We deliberately do NOT key on the call/jmp that follows the store: that
// tail is emitted by Arxan and its bytes (E8 vs E9) flip between game builds.
struct sig_byte { uint8_t value; bool wild; };

constexpr sig_byte bgm_clear_sig[] = {
    {0x83, false}, {0xFD, false}, {0x05, false},                    // cmp ebp,05
    {0xE9, false}, {0, true}, {0, true}, {0, true}, {0, true},      // jmp <rel32>
    {0x89, false}, {0x83, false}, {0x24, false},                    // mov [rbx+0x124],eax
    {0x01, false}, {0x00, false}, {0x00, false},
};
constexpr size_t bgm_clear_store_offset = 8;  // store begins here within a match
constexpr size_t bgm_clear_patch_len    = 6;  // bytes of the store to NOP

bool sig_match_at(const uint8_t* p) {
    for (const auto& b : bgm_clear_sig) {
        if (!b.wild && *p != b.value) return false;
        ++p;
    }
    return true;
}

// Scan every executable section of the host module (nightreign.exe) for the
// signature. Returns the address of the STORE instruction, or nullptr unless
// there is EXACTLY one match (0 or >1 -> fail-safe, patch nothing).
uint8_t* find_bgm_clear_store() {
    auto base = reinterpret_cast<uint8_t*>(GetModuleHandleW(nullptr));
    if (!base) return nullptr;

    auto dos = reinterpret_cast<IMAGE_DOS_HEADER*>(base);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) return nullptr;
    auto nt = reinterpret_cast<IMAGE_NT_HEADERS*>(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) return nullptr;

    constexpr size_t siglen = sizeof(bgm_clear_sig) / sizeof(bgm_clear_sig[0]);
    auto sec = IMAGE_FIRST_SECTION(nt);
    uint8_t* hit = nullptr;

    for (unsigned i = 0; i < nt->FileHeader.NumberOfSections; ++i) {
        if (!(sec[i].Characteristics & IMAGE_SCN_MEM_EXECUTE)) continue;
        uint8_t* start = base + sec[i].VirtualAddress;
        size_t   size  = sec[i].Misc.VirtualSize;
        if (size < siglen) continue;
        for (uint8_t* p = start; p <= start + size - siglen; ++p) {
            if (sig_match_at(p)) {
                if (hit) return nullptr;   // >1 match -> ambiguous, bail out
                hit = p;
            }
        }
    }
    return hit ? hit + bgm_clear_store_offset : nullptr;
}

bool apply_nop(uint8_t* addr, size_t len) {
    DWORD old_prot = 0;
    if (!VirtualProtect(addr, len, PAGE_EXECUTE_READWRITE, &old_prot)) return false;
    std::memset(addr, 0x90, len);
    VirtualProtect(addr, len, old_prot, &old_prot);
    FlushInstructionCache(GetCurrentProcess(), addr, len);
    return true;
}

// Arxan can decrypt/relocate late, so retry for a while after startup.
void patch_bgm_clear_worker() {
    for (int attempt = 0; attempt < 120; ++attempt) {
        if (uint8_t* store = find_bgm_clear_store()) {
            if (apply_nop(store, bgm_clear_patch_len))
                spdlog::info("[unlock_wwise_states] clear-write neutralized at {}", static_cast<void*>(store));
            else
                spdlog::error("[unlock_wwise_states] patch failed (VirtualProtect) at {}", static_cast<void*>(store));
            return;
        }
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
    spdlog::warn("[unlock_wwise_states] clear-write signature not found (0 or >1 matches) after retries; gate not patched");
}

// ============================================

using setbossbgm_fn = void(uintptr_t, uint32_t, int32_t);
static setbossbgm_fn *setbossbgm_original = nullptr;

static void write_slot(uintptr_t base, size_t slot_idx, const char *s)
{
    auto slot = reinterpret_cast<char *>(base + slot_idx * item_stride);
    std::memset(slot, 0, item_stride);
    std::strncpy(slot, s, item_stride - 1); // slot[31] stays null
}

// loads rowid -> bgm state name overrides from config_filename next to the dll
static void load_bossbgm_overrides()
{
    auto path = dll_folder / config_filename;
    if (!std::filesystem::exists(path))
    {
        spdlog::warn("[unlock_wwise_states] config not found: {}", path.string());
        return;
    }

    YAML::Node root;
    try
    {
        root = YAML::LoadFile(path.string());
    }
    catch (const YAML::Exception &e)
    {
        spdlog::error("[unlock_wwise_states] failed to parse config: {}", e.what());
        return;
    }

    for (const auto &entry : root)
    {
        auto rowid = entry.first.as<uint32_t>();
        auto value = entry.second.as<std::string>();
        if (value.size() > item_stride - 1)
        {
            spdlog::warn("[unlock_wwise_states] value for rowid {} exceeds {} chars, truncating",
                        rowid, item_stride - 1);
            value.resize(item_stride - 1);
        }
        bossbgm_overrides[rowid] = std::move(value);
    }

    spdlog::info("[unlock_wwise_states] loaded {} bgm override(s) from config", bossbgm_overrides.size());
}

static void setbossbgm_detour(uintptr_t bgmctrl, uint32_t rowid, int32_t x)
{
    auto it = bossbgm_overrides.find(rowid);
    if (it != bossbgm_overrides.end())
    {
        auto ptr = bgmctrl + bossbgm_list_offset;
        write_slot(ptr, scratch_slot, it->second.c_str());
        spdlog::info("[unlock_wwise_states] unlocked BgmEnemyType {} ({})", rowid, it->second);
    }

    return setbossbgm_original(bgmctrl, rowid, x);
}

static std::optional<uintptr_t> rva_to_va(uint32_t rva)
{
    auto base = reinterpret_cast<uintptr_t>(GetModuleHandleW(L"nightreign.exe"));
    if (base == 0)
        return std::nullopt;
    return base + rva;
}

static void install_hooks()
{
    auto va = rva_to_va(setbossbgm_rva);
    if (!va)
    {
        spdlog::warn("[unlock_wwise_states] could not resolve SETBOSSBGM_RVA, skipping hook");
        return;
    }

    modutils::hook<setbossbgm_fn>({.address = reinterpret_cast<void *>(*va)}, setbossbgm_detour,
                                  setbossbgm_original);
}

static void setup_logger()
{
    // elden-x builds spdlog with the default logger disabled, so install one.
    auto logger = std::make_shared<spdlog::logger>("unlock_wwise_states");
    logger->set_pattern("[%Y-%m-%d %H:%M:%S.%e] %^[%l]%$ %v");
    logger->sinks().push_back(std::make_shared<spdlog::sinks::daily_file_sink_st>(
        (dll_folder / "logs" / "unlock_wwise_states.log").string(), 0, 0, false, 5));
    logger->sinks().push_back(std::make_shared<spdlog::sinks::stdout_color_sink_st>());
    logger->flush_on(spdlog::level::info);
    spdlog::set_default_logger(logger);
}

static void setup()
{
    modutils::initialize();
    er::FD4::find_singletons();

    load_bossbgm_overrides();
    install_hooks();
    modutils::enable_hooks();

    std::thread(patch_bgm_clear_worker).detach();

    spdlog::info("[unlock_wwise_states] is now active!");
}

}

bool WINAPI DllMain(HINSTANCE dll_instance, unsigned int reason, void *reserved)
{
    using namespace unlock_wwise_states;

    if (reason == DLL_PROCESS_ATTACH)
    {
        wchar_t dll_filename[MAX_PATH] = {0};
        GetModuleFileNameW(dll_instance, dll_filename, MAX_PATH);
        dll_folder = std::filesystem::path(dll_filename).parent_path();

        setup_logger();

        std::thread([] {
            try
            {
                setup();
            }
            catch (const std::exception &e)
            {
                spdlog::error("[unlock_wwise_states] {}", e.what());
                modutils::deinitialize();
            }
        }).detach();
    }

    return true;
}

// Register a no-op ModEngine2 extension so ME2 doesn't warn about a non-extension DLL.
static struct dummy_modengine_extension
{
    virtual ~dummy_modengine_extension() = default;
    virtual void on_attach() {}
    virtual void on_detach() {}
    virtual const char *id() { return "unlock_wwise_states"; }
} modengine_extension;

extern "C" __declspec(dllexport) bool modengine_ext_init(void *, void **extension)
{
    *extension = &modengine_extension;
    return true;
}
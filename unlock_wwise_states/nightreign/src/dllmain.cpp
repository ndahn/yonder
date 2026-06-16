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

// --- BgmEnemyType clear-validation NOP ------------------------------------
// The boss-bgm controller runs an (Arxan-obfuscated) validation that, for
// values it doesn't recognise, stores 0 into CSSoundBgmController+0x124, which
// resets BgmEnemyType to None. NOPing that single 6-byte store lets custom
// values play. We locate it by a unique signature so it survives base ASLR:
//
//   89 83 24 01 00 00      mov [rbx+0x124], eax   <- store to NOP
//   48 8B 0D ?? ?? ?? ??   mov rcx, [rip+disp]
//   E9                     jmp ...                <- E9 (not E8) distinguishes
//                                                    it from the *active* writer
// Reference build RVA: 0x230B4BF.  EXPECT TO RE-VALIDATE THIS PER GAME PATCH.
static constexpr uintptr_t bgm_clear_rva = 0x230B4BF;
static constexpr size_t bgm_clear_patch_len = 6;

struct pattern_elem
{
    uint8_t byte;
    bool wildcard;
};
static constexpr pattern_elem bgm_clear_sig[] = {
    {0x89, false}, {0x83, false}, {0x24, false}, {0x01, false}, {0x00, false}, {0x00, false},
    {0x48, false}, {0x8B, false}, {0x0D, false},
    {0x00, true},  {0x00, true},  {0x00, true},  {0x00, true},
    {0xe9, false},
};
static constexpr size_t bgm_clear_sig_len = sizeof(bgm_clear_sig) / sizeof(bgm_clear_sig[0]);

static bool sig_matches(const uint8_t *p)
{
    for (size_t i = 0; i < bgm_clear_sig_len; ++i)
        if (!bgm_clear_sig[i].wildcard && p[i] != bgm_clear_sig[i].byte)
            return false;
    return true;
}

static bool apply_nop(uint8_t *target)
{
    DWORD old_protect;
    if (!VirtualProtect(target, bgm_clear_patch_len, PAGE_EXECUTE_READWRITE, &old_protect))
    {
        spdlog::error("[unlock_wwise_states] VirtualProtect failed for bgm-clear patch");
        return false;
    }
    std::memset(target, 0x90, bgm_clear_patch_len);
    VirtualProtect(target, bgm_clear_patch_len, old_protect, &old_protect);
    FlushInstructionCache(GetCurrentProcess(), target, bgm_clear_patch_len);
    return true;
}

// true => done (patched, or ambiguous/impossible so stop). false => not found yet.
static bool try_patch_bgm_clear()
{
    auto base = reinterpret_cast<uint8_t *>(GetModuleHandleW(L"nightreign.exe"));
    if (!base)
        return false;

    auto dos = reinterpret_cast<const IMAGE_DOS_HEADER *>(base);
    auto nt = reinterpret_cast<const IMAGE_NT_HEADERS *>(base + dos->e_lfanew);

    // Fast path: known RVA for this build, but verify the bytes before touching them.
    if (bgm_clear_rva + bgm_clear_sig_len <= nt->OptionalHeader.SizeOfImage)
    {
        uint8_t *rva_target = base + bgm_clear_rva;
        if (sig_matches(rva_target))
        {
            if (apply_nop(rva_target))
                spdlog::info("[unlock_wwise_states] NOPed bgm-clear validation at rva 0x{:x}",
                            bgm_clear_rva);
            return true;
        }
    }

    // Resilient path: unique signature scan over executable sections.
    auto sections = IMAGE_FIRST_SECTION(nt);
    std::vector<uint8_t *> matches;
    for (WORD i = 0; i < nt->FileHeader.NumberOfSections; ++i)
    {
        auto const &sec = sections[i];
        if (!(sec.Characteristics & IMAGE_SCN_MEM_EXECUTE))
            continue;
        size_t size = sec.Misc.VirtualSize ? sec.Misc.VirtualSize : sec.SizeOfRawData;
        if (size < bgm_clear_sig_len)
            continue;
        uint8_t *start = base + sec.VirtualAddress;
        for (uint8_t *p = start, *last = start + size - bgm_clear_sig_len; p <= last; ++p)
            if (sig_matches(p))
                matches.push_back(p);
    }

    if (matches.size() == 1)
    {
        auto target = matches.front();
        if (apply_nop(target))
            spdlog::info("[unlock_wwise_states] NOPed bgm-clear validation at rva 0x{:x} (signature)",
                        static_cast<uintptr_t>(target - base));
        return true;
    }
    if (matches.size() > 1)
    {
        spdlog::warn("[unlock_wwise_states] bgm-clear signature matched {} sites; skipping to avoid "
                    "corrupting the wrong code (re-validate the AOB for this build)",
                    matches.size());
        return true; // ambiguous -> fail safe, stop retrying
    }
    return false; // not resolved yet
}

static void patch_bgm_clear_worker()
{
    for (int attempt = 0; attempt < 120; ++attempt)
    {
        if (try_patch_bgm_clear())
            return;
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
    spdlog::warn("[unlock_wwise_states] bgm-clear signature never resolved; custom boss bgm will be "
                "reset to None. The AOB likely needs updating for this game build.");
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
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <cstdint>
#include <cstring>
#include <filesystem>
#include <optional>
#include <thread>

#include <spdlog/sinks/daily_file_sink.h>
#include <spdlog/sinks/stdout_color_sinks.h>
#include <spdlog/spdlog.h>

#include <elden-x/params.hpp>
#include <elden-x/singletons.hpp>
#include <elden-x/utils/modutils.hpp>

namespace unlock_wwise_states
{

static std::filesystem::path dll_folder;

static constexpr uintptr_t verify_state_rva = 0x255fa90;
static constexpr size_t h_bgmenemytype = 0x8934ec8f;  // fnv1 hash of "BgmEnemyType"
static constexpr size_t pointer_chain[2] = {0x10, 0x80};
static constexpr size_t bossbgm_offset = 0x574;
static constexpr size_t item_stride = 12;  // [value 4b, ??? 4b, constant 4b]
static constexpr size_t num_bossbgm = 106;  // can also be read from +0x14
static constexpr size_t num_bgmplace = 48;

using verify_state_fn = void(uintptr_t, uint32_t);
static verify_state_fn *verify_state_original = nullptr;

static void verify_state_detour(uintptr_t manager_obj, uint32_t hash)
{
    // TODO state_group lives in RBP at this point
    // if (state_group != h_bgmenemytype) {
    //     return verify_state_original(manager_obj, hash, state_group);
    // }

    auto ptr = manager_obj;
    for (const size_t &offset : pointer_chain) {
        ptr = *reinterpret_cast<uintptr_t*>(ptr + offset);
    }

    // Beginning of the allowlist
    ptr += bossbgm_offset;

    // The list is ordered, place the hash in the correct location
    // Skip the first element, it's always 0
    for (size_t i = 1; i < num_bossbgm; i++) {
        uintptr_t slot = ptr + i * item_stride;
        uint32_t &val = *reinterpret_cast<uint32_t*>(slot);

        if (val >= hash || i == num_bossbgm - 1) {
            val = hash;
            spdlog::info("[unlock_wwise_states] placed BgmEnemyType hash {} at index {}", hash, i);
            break;
        }
    }

    return verify_state_original(manager_obj, hash);
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
    auto va = rva_to_va(verify_state_rva);
    if (!va)
    {
        spdlog::warn("[unlock_wwise_states] could not resolve SETBOSSBGM_RVA, skipping hook");
        return;
    }

    modutils::hook<verify_state_fn>({.address = reinterpret_cast<void *>(*va)}, verify_state_detour,
                                  verify_state_original);
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

    install_hooks();
    modutils::enable_hooks();
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

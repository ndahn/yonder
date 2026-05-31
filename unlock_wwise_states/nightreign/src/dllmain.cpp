// Elden Ring BGM state unlocker.
//
// CSSoundBgmController owns a fixed-size string allowlist for boss BGM
// (BgmEnemyType, +0x238, 105 slots of 32 bytes). When the BGM system resolves a
// Wwise state name from a param row it rejects anything missing from the list,
// blocking custom states. We hook SetBossBgm and copy the resolved name into a
// scratch slot so it passes validation.
//
// The function RVA is loaded at runtime from `rvas.yaml` next to the DLL.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <cstdint>
#include <cstring>
#include <filesystem>
#include <optional>
#include <thread>

#include <spdlog/sinks/daily_file_sink.h>
#include <spdlog/spdlog.h>

#include <elden-x/params.hpp>
#include <elden-x/singletons.hpp>
#include <elden-x/utils/modutils.hpp>

#include "config.hpp"

namespace unlock_wwise_states
{

// Allowlist layout inside CSSoundBgmController.
static constexpr uintptr_t boss_bgm_offset = 0x1b0; // BgmEnemyType list
static constexpr size_t slot_size = 32;
static constexpr size_t scratch_slot = 1; // slot 0 is "None"; slot 1 is ours

// SetBossBgm(controller, param_id, state).
using setbossbgm_fn = void(uintptr_t, uint32_t, int32_t);
static setbossbgm_fn *setbossbgm_original = nullptr;

static std::filesystem::path dll_folder;

// True once the game has written content into slot 0 of the allowlist. Early
// ticks during sound-system init can fire before that happens.
static bool allowlist_ready(uintptr_t controller, uintptr_t base)
{
    return controller != 0 && *reinterpret_cast<const uint8_t *>(controller + base) != 0;
}

// Overwrite a 32-byte allowlist slot with a null-terminated string (truncated).
static void write_slot(uintptr_t controller, uintptr_t base, size_t idx, const char *s)
{
    auto slot = reinterpret_cast<char *>(controller + base + idx * slot_size);
    std::memset(slot, 0, slot_size);
    std::strncpy(slot, s, slot_size - 1); // slot[31] stays null
}

static void setbossbgm_detour(uintptr_t controller, uint32_t param_id, int32_t state)
{
    if (allowlist_ready(controller, boss_bgm_offset))
    {
        auto [row, row_exists] = er::param::WwiseValueToStrParam_BgmBossChrIdConv[param_id];
        if (row_exists)
        {
            spdlog::info("[unlock_wwise_states] BgmEnemyType -> {}", row.ParamStr);
            write_slot(controller, boss_bgm_offset, scratch_slot, row.ParamStr);
        }

        setbossbgm_original(controller, param_id, state);
    }
}

// Resolve an eldenring.exe RVA to a runtime address (the module base is its VA).
static std::optional<uintptr_t> rva_to_va(uint32_t rva)
{
    auto base = reinterpret_cast<uintptr_t>(GetModuleHandleW(L"eldenring.exe"));
    if (base == 0)
        return std::nullopt;
    return base + rva;
}

static void install_hooks(const config::rvas &cfg)
{
    if (!cfg.setbossbgm)
    {
        spdlog::warn("[unlock_wwise_states] SETBOSSBGM_RVA not found in config, skipping hook");
        return;
    }

    auto va = rva_to_va(*cfg.setbossbgm);
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
    logger->flush_on(spdlog::level::info);
    spdlog::set_default_logger(logger);
}

static void setup()
{
    modutils::initialize();
    er::FD4::find_singletons();
    er::CS::SoloParamRepository::wait_for_params(); // block until params are loaded

    config::rvas cfg;
    try
    {
        cfg = config::load(dll_folder / "rvas.yaml");
    }
    catch (const std::exception &e)
    {
        spdlog::error("[unlock_wwise_states] config: {}", e.what());
        return;
    }

    install_hooks(cfg);
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

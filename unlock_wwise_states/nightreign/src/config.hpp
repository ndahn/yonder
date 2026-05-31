#pragma once

#include <cstdint>
#include <filesystem>
#include <optional>

namespace unlock_wwise_states::config
{

// RVAs deserialised from rvas.yaml. A missing key leaves the field empty,
// mirroring the original's Option<u32>.
struct rvas
{
    std::optional<uint32_t> setbossbgm;
};

// Read and parse the config at `path`. Throws on unreadable/invalid YAML;
// unknown keys are ignored and a missing key leaves its field empty.
rvas load(const std::filesystem::path &path);

}

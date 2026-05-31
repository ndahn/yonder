#include "config.hpp"

#include <yaml-cpp/yaml.h>

namespace uws = unlock_wwise_states;

uws::config::rvas uws::config::load(const std::filesystem::path &path)
{
    rvas out;
    auto root = YAML::LoadFile(path.string()); // throws if the file is missing/malformed

    if (auto node = root["SETBOSSBGM_RVA"]; node && !node.IsNull())
        out.setbossbgm = node.as<uint32_t>();

    return out;
}

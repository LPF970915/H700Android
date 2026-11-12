// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <string>

// Controller identity, never MMC enumeration order or a hard-coded minor.
inline bool rocTf2Path(const std::string& path) {
    return path.find("/devices/platform/soc/sdc2/mmc_host/") != std::string::npos &&
           path.find("/block/mmcblk") != std::string::npos &&
           path.find("/../") == std::string::npos;
}

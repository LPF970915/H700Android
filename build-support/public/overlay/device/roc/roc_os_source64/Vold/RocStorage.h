#pragma once
#include "RocStoragePolicy.h"
#include <android-base/properties.h>
#include <limits.h>
#include <stdlib.h>
#include <sys/sysmacros.h>
#include <string>
inline bool rocUnified() {
    return android::base::GetProperty("ro.roc.storage.layout", "") == "unified-v1";
}
inline bool rocProtectedMmc(dev_t device) {
    if (!rocUnified() || major(device) != 179) return false;
    char resolved[PATH_MAX];
    std::string sys = "/sys/dev/block/" + std::to_string(major(device)) + ":" + std::to_string(minor(device));
    return !realpath(sys.c_str(), resolved) || !rocTf2Path(resolved);
}

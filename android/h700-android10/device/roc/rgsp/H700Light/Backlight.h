// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <cstdint>
#include <mutex>

namespace h700 {

constexpr unsigned long kSetBrightness = 0x102;

// Kept injectable so error handling and the four-word driver ABI can be
// exercised without opening a display or changing real brightness.
class DisplayIo {
public:
    virtual ~DisplayIo() = default;
    virtual int set(int fd, unsigned long command, unsigned long* args) = 0;
};

class Backlight {
public:
    Backlight(int fd, DisplayIo& io) : fd_(fd), io_(io) {}
    static unsigned int brightness(uint32_t argb);
    int setColor(uint32_t argb);

private:
    int fd_;
    DisplayIo& io_;
    std::mutex mutex_;
};

}  // namespace h700

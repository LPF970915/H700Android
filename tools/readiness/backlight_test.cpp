// SPDX-License-Identifier: Apache-2.0
#include "Backlight.h"
#include <cassert>
#include <cerrno>
#include <cstdio>

class FakeIo final : public h700::DisplayIo {
public:
    int calls = 0;
    int result = 0;
    unsigned long value = 0;
    int set(int fd, unsigned long command, unsigned long* args) override {
        assert(fd == 17);
        assert(command == 0x102);
        assert(args[0] == 0 && args[2] == 0 && args[3] == 0);
        assert(args[1] <= 255);
        value = args[1];
        ++calls;
        return result;
    }
};

int main() {
    FakeIo io;
    h700::Backlight backlight(17, io);
    // Every grayscale setting reaches the driver exactly, including true off.
    for (unsigned int level = 0; level < 256; ++level) {
        uint32_t rgb = level * 0x010101;
        assert(backlight.setColor(rgb | 0xff000000) == 0);
        assert(io.value == level);
        assert(h700::Backlight::brightness(rgb) == level);
    }
    assert(h700::Backlight::brightness(0x00ff0000) == 76);
    assert(h700::Backlight::brightness(0x0000ff00) == 149);
    assert(h700::Backlight::brightness(0x000000ff) == 28);
    io.result = -EIO;
    assert(backlight.setColor(0xffffffff) == -EIO);
    io.result = -EACCES;
    assert(backlight.setColor(0) == -EACCES);
    int calls = io.calls;
    h700::Backlight unavailable(-1, io);
    assert(unavailable.setColor(0xffffffff) == -ENODEV);
    assert(io.calls == calls);
    std::puts("BACKLIGHT_256_LEVELS_DRIVER_ABI_AND_ERRORS_PASS");
}

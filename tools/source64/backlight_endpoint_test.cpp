// SPDX-License-Identifier: Apache-2.0
#include "Backlight.h"
#include <cassert>
#include <cerrno>
#include <cstdio>

class FakeIo final : public h700::DisplayIo {
public:
    unsigned long value = 0;
    int calls = 0;
    int result = 0;
    int set(int fd, unsigned long command, unsigned long* args) override {
        assert(fd == 17 && command == 0x102);
        assert(args[0] == 0 && args[2] == 0 && args[3] == 0);
        assert(args[1] <= 254);
        value = args[1];
        ++calls;
        return result;
    }
};

int main() {
    FakeIo io;
    h700::Backlight light(17, io);
    unsigned long previous = 0;
    for (unsigned int level = 0; level < 256; ++level) {
        const uint32_t rgb = level * 0x010101;
        // The standard RGB conversion remains exact; compatibility is at IO.
        assert(h700::Backlight::brightness(rgb) == level);
        assert(light.setColor(0xff000000 | rgb) == 0);
        assert(io.value == (level == 255 ? 254 : level));
        assert(io.value >= previous);
        previous = io.value;
    }
    assert(light.setColor(0) == 0 && io.value == 0);
    assert(light.setColor(0x00ffffff) == 0 && io.value == 254);
    assert(light.setColor(0xffff0000) == 0 && io.value == 76);
    assert(light.setColor(0xff00ff00) == 0 && io.value == 149);
    assert(light.setColor(0xff0000ff) == 0 && io.value == 28);
    io.result = -EIO;
    assert(light.setColor(0xffffffff) == -EIO);
    io.result = -EACCES;
    assert(light.setColor(0) == -EACCES);
    int calls = io.calls;
    h700::Backlight unavailable(-1, io);
    assert(unavailable.setColor(0xffffffff) == -ENODEV && io.calls == calls);
    std::puts("SOURCE64_BACKLIGHT_MONOTONIC_ENDPOINT_ABI_ERRORS_PASS");
}

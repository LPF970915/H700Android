// SPDX-License-Identifier: Apache-2.0
#include "Backlight.h"

#include <cerrno>

namespace h700 {

unsigned int Backlight::brightness(uint32_t argb) {
    // Same RGB conversion as Android's legacy lights implementation. Alpha
    // does not affect the requested backlight. The hardware range is 0..255.
    return (77 * ((argb >> 16) & 255) + 150 * ((argb >> 8) & 255)
            + 29 * (argb & 255)) >> 8;
}

int Backlight::setColor(uint32_t argb) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (fd_ < 0) return -ENODEV;
    // Sunxi disp2 copies four unsigned-long words, including on AArch64.
    // Screen 0 is the internal LCD. Do not use the vendor battery sysfs knob.
    // The retained RG34XXSP display stack reads back 200 at ioctl value
    // 255, while 248/250/254 remain exact. Keep the logical endpoint
    // monotonic using the highest validated driver value; true off stays 0.
    // This is a private product compatibility rule, not a kernel fix.
    const unsigned int requested = brightness(argb);
    const unsigned int driver = requested == 255 ? 254 : requested;
    unsigned long args[4] = {0, driver, 0, 0};
    return io_.set(fd_, kSetBrightness, args);
}

}  // namespace h700

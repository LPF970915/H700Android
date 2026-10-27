#ifndef RGSP_FRAME_PERIOD_H
#define RGSP_FRAME_PERIOD_H
#include <stdint.h>

// fb_var_screeninfo pixel clock is picoseconds. Preserve fractional refresh Hz.
static inline int32_t rgspFramePeriodNs(uint64_t ht, uint64_t vt, uint32_t pixelPs) {
    if (!ht || !vt || !pixelPs || ht > 65536 || vt > 65536 || pixelPs > 1000000000U)
        return 16666667;
    const uint64_t period = (ht * vt * pixelPs + 500) / 1000;
    return period >= 1000000 && period <= 100000000 ? (int32_t)period : 16666667;
}
#endif

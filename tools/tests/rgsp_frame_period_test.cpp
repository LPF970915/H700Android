#include <cassert>
#include "../../android/h700-android10/device/roc/rgsp/graphics/RgspFramePeriod.h"
int main() {
    // Fractional refresh must survive the conversion, rather than becoming 59 Hz.
    assert(rgspFramePeriodNs(820, 536, 38461) == 16904379);
    assert(rgspFramePeriodNs(800, 525, 40000) == 16800000);
    assert(rgspFramePeriodNs(0, 525, 40000) == 16666667);
    assert(rgspFramePeriodNs(800, 0, 40000) == 16666667);
    assert(rgspFramePeriodNs(800, 525, 0) == 16666667);
    assert(rgspFramePeriodNs(UINT64_MAX, UINT64_MAX, UINT32_MAX) == 16666667);
    assert(rgspFramePeriodNs(65536, 65536, 1000000000) == 16666667);
    assert(rgspFramePeriodNs(1, 1, 1) == 16666667);
    return 0;
}

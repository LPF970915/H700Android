#include <assert.h>
#include <stdio.h>
#include "../../android/h700-android10/device/roc/rgsp/input/axis_math.h"
int main(void)
{
    int centers[] = {1024, 2004, 2048, 2088, 3072};
    unsigned int index;
    for (index = 0; index < sizeof(centers) / sizeof(centers[0]); index++) {
        int middle = centers[index], raw, previous = 32767;
        assert(h700_axis_value(0, middle) == 32767);
        assert(h700_axis_value(4095, middle) == -32767);
        for (raw = 0; raw < 4096; raw++) {
            int value = h700_axis_value(raw, middle);
            assert(value >= -32767 && value <= 32767 && value <= previous);
            if (raw >= middle - 32 && raw <= middle + 32) assert(value == 0);
            previous = value;
        }
    }
    assert(h700_mux_mask(0) == 0 && h700_mux_mask(1) == 0xf);
    assert(h700_mux_mask(2) == 0xff && h700_mux_mask(3) == 0xfff);
    assert(h700_mux_mask(5) == 0xfff);
    assert(h700_click_mask(3) == 0 && h700_click_mask(4) == 0xf && h700_click_mask(5) == 0xff);
    assert(h700_click_pull_mask(3) == 0 && h700_click_pull_mask(4) == 0x30000 && h700_click_pull_mask(5) == 0xf0000);
    puts("PASS: 20480 axis monotonicity/range cases, center dead zones and partial GPIO ownership masks");
    return 0;
}

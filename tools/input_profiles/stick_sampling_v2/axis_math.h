/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef H700_AXIS_MATH_H
#define H700_AXIS_MATH_H
static inline int h700_axis_value(int raw, int middle)
{
    int delta = middle - raw;
    int limit, result;
    if (delta >= -32 && delta <= 32) return 0;
    limit = delta > 0 ? middle - 32 : 4095 - middle - 32;
    delta += delta > 0 ? -32 : 32;
    result = delta * 32767 / (limit > 0 ? limit : 1);
    return result < -32767 ? -32767 : result > 32767 ? 32767 : result;
}
static inline unsigned int h700_mux_mask(unsigned int requested)
{
    unsigned int count = requested < 3 ? requested : 3;
    return (1u << (count * 4)) - 1;
}
static inline unsigned int h700_click_mask(unsigned int requested)
{
    unsigned int count = requested > 3 ? requested - 3 : 0;
    return (1u << (count * 4)) - 1;
}
static inline unsigned int h700_click_pull_mask(unsigned int requested)
{
    unsigned int count = requested > 3 ? requested - 3 : 0;
    return ((1u << (count * 2)) - 1) << 16;
}
#endif

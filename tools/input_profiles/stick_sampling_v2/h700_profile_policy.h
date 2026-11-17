/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef H700_PROFILE_POLICY_H
#define H700_PROFILE_POLICY_H

enum h700_stick_wiring {
    H700_WIRING_NONE,
    H700_WIRING_PI_MUX,
    H700_WIRING_UNVERIFIED
};

struct h700_stick_profile {
    const char *model;
    unsigned int sticks;
    enum h700_stick_wiring wiring;
    unsigned int invert_mask;
    unsigned int click_mask;
};

#include "h700_profile_table.h"

static inline int h700_model_equal(const char *left, const char *right)
{
    if (!left || !right) return 0;
    while (*left && *left == *right) { left++; right++; }
    return *left == *right;
}

static inline const struct h700_stick_profile *h700_profile_lookup(const char *model)
{
    unsigned int i;
    for (i = 0; i < sizeof(h700_stick_profiles) / sizeof(h700_stick_profiles[0]); i++)
        if (h700_model_equal(model, h700_stick_profiles[i].model))
            return &h700_stick_profiles[i];
    return 0;
}

static inline unsigned int h700_profile_axis_count(const struct h700_stick_profile *p)
{
    return p ? p->sticks * 2 : 0;
}

static inline unsigned int h700_profile_gpio_count(const struct h700_stick_profile *p)
{
    unsigned int count;
    if (!p || !p->sticks || p->wiring != H700_WIRING_PI_MUX) return 0;
    count = 3;
    if (p->click_mask & 1) count++;
    if (p->click_mask & 2) count++;
    return count;
}

static inline int h700_profile_needs_hardware(const struct h700_stick_profile *p)
{
    return p && p->sticks && p->wiring == H700_WIRING_PI_MUX;
}

/* h700_axis_value is negative as raw increases. Apply the explicit sign once. */
static inline int h700_profile_axis_sign(const struct h700_stick_profile *p,
                                        unsigned int axis, int inverted_value)
{
    return (p->invert_mask & (1u << axis)) ? inverted_value : -inverted_value;
}

#define H700_NEUTRAL_FLAT 4096
#define H700_NEUTRAL_SAMPLES 3
struct h700_neutral_gate {
    unsigned int consecutive[2];
    unsigned int released_consecutive[2];
    unsigned int armed_mask;
    unsigned int click_released_mask;
};

static inline void h700_reset_neutral_gate(struct h700_neutral_gate *gate)
{
    gate->consecutive[0] = gate->consecutive[1] = 0;
    gate->released_consecutive[0] = gate->released_consecutive[1] = 0;
    gate->armed_mask = 0;
    gate->click_released_mask = 0;
}

/* One held or noisy stick must not disable its independent partner. The flat
 * is the same normalized tolerance already advertised to Android. Clicks have
 * a separate release gate; a held L3/R3 never blocks analog movement. */
static inline unsigned int h700_observe_neutral(struct h700_neutral_gate *gate,
                                               const int *values,
                                               unsigned int count,
                                               unsigned int clicks,
                                               unsigned int click_mask)
{
    unsigned int stick;
    for (stick = 0; stick < 2; stick++) {
        unsigned int bit = 1u << stick;
        if (!(click_mask & bit) || (gate->click_released_mask & bit)) continue;
        if (clicks & bit) {
            gate->released_consecutive[stick] = 0;
        } else if (++gate->released_consecutive[stick] >= H700_NEUTRAL_SAMPLES) {
            gate->click_released_mask |= bit;
        }
    }
    for (stick = 0; stick < count / 2 && stick < 2; stick++) {
        int x = values[stick * 2], y = values[stick * 2 + 1];
        if (gate->armed_mask & (1u << stick)) continue;
        if (x < -H700_NEUTRAL_FLAT || x > H700_NEUTRAL_FLAT ||
            y < -H700_NEUTRAL_FLAT || y > H700_NEUTRAL_FLAT) {
            gate->consecutive[stick] = 0;
            continue;
        }
        if (++gate->consecutive[stick] >= H700_NEUTRAL_SAMPLES)
            gate->armed_mask |= 1u << stick;
    }
    return gate->armed_mask;
}
#endif

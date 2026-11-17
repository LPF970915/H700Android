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

struct h700_neutral_gate { unsigned int consecutive; unsigned int armed; };

static inline void h700_reset_neutral_gate(struct h700_neutral_gate *gate)
{
    gate->consecutive = 0;
    gate->armed = 0;
}

/* A resumed or freshly attached stick must physically return to neutral.
 * Require three complete 10ms samples, including released stick clicks. */
static inline int h700_observe_neutral(struct h700_neutral_gate *gate,
                                     const int *values, unsigned int count,
                                     unsigned int clicks)
{
    unsigned int i;
    if (gate->armed) return 1;
    if (clicks) { gate->consecutive = 0; return 0; }
    for (i = 0; i < count; i++)
        if (values[i]) { gate->consecutive = 0; return 0; }
    if (++gate->consecutive >= 3) gate->armed = 1;
    return gate->armed;
}
#endif

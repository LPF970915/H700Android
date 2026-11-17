// SPDX-License-Identifier: GPL-2.0-only
/* Candidate: model-selected sticks on the existing BSP controller.
 * Wiring reference: saved ROCKNIX/Knulli H700 DTS, see README.md.
 * Register definitions: Allwinner H616 BSP sunxi_gpadc.h, clk-sun50iw9.h.
 */
#ifdef H700_HOST_TEST
#include "test_kernel_shim.h"
#else
#include <linux/module.h>
#include <linux/input.h>
#include <linux/gpio.h>
#include <linux/gpio/driver.h>
#include <linux/io.h>
#include <linux/of.h>
#include <linux/delay.h>
#include <linux/workqueue.h>
#include <linux/suspend.h>
#include <linux/jiffies.h>
#endif
#include "axis_math.h"
#include "h700_profile_policy.h"

static char *profile;
module_param(profile, charp, 0444);
static bool probe_only;
module_param(probe_only, bool, 0444);
MODULE_PARM_DESC(profile, "Canonical manually selected model; no RAM identity heuristic");
static const struct h700_stick_profile *selected;

/* BSP reserves ABS_RX/RY/RZ for three ternary legacy signals. Use four free
 * Linux axes and map Z/RUDDER to Android's standard right-stick Z/RZ in .kl. */
static const unsigned int axes[4] = {ABS_X, ABS_Y, ABS_Z, ABS_RUDDER};
static const unsigned int channels[4] = {3, 2, 1, 0};
static const unsigned int registers[7] = {0, 4, 8, 0xc, 0x20, 0x24, 0x28};
static const unsigned int pins[5] = {256, 257, 258, 136, 137};
static struct input_handle handle;
static struct delayed_work poll_work;
static void __iomem *adc, *pio, *ccu;
static u32 saved_adc[7], saved_pi_cfg, saved_pi_data, saved_pe_cfg, saved_pe_pull;
static struct input_absinfo old_abs[4];
static unsigned long old_abs_bits, old_key_bits;
static int gpio_base, requested, center[4];
static bool prepared, active, suspended, hardware_blocked, needs_reconfigure;
static bool handler_registered, notifier_registered;
static struct h700_neutral_gate neutral_gate;
static int click_candidate[2], click_count[2], click_state[2];
static int last_raw[4];
static unsigned int last_clicks;
static u32 last_ctrl, last_ccu, last_select;
static unsigned long poll_count, raw_jiffies, next_diagnostic, last_diagnostic;
static unsigned long next_recovery;
static unsigned int recovery_attempts, recovery_successes, recovery_failures;
static unsigned int recovery_budget_used;
static unsigned long recovery_healthy_since;
static bool recovery_healthy_tracking;
#define H700_RECOVERY_FAILURE_LIMIT 3
static bool recovery_started;
static bool raw_valid, diagnostic_started, diagnostic_gated;
static bool diagnostic_ever_logged, diagnostic_recovery_pending;
static const char *hardware_reason = "not-sampled";
static const char *recovery_reason = "not-needed";
static bool recovery_still_owned(void);

static int chip_match(struct gpio_chip *chip, void *unused)
{
    (void)unused;
    return chip->ngpio > 258 && (!strcmp(chip->label, "pio")
            || strstr(chip->label, "0300b000"));
}

static int read_channel(unsigned int channel)
{
    gpio_set_value(gpio_base + 257, channel & 1);
    gpio_set_value(gpio_base + 258, (channel >> 1) & 1);
    usleep_range(200, 300);
    return readl(adc + 0x80) & 0xfff;
}

static bool clock_ready(void)
{
    if (!ccu) return false;
    last_ccu = readl(ccu + 0x9ec);
    return (last_ccu & 0x10001) == 0x10001;
}

/* Initial setup and owned-state recovery deliberately use the same seven
 * register writes as the physically exercised RG34XXSP implementation. No
 * clock/reset register is written and calibration centers are not resampled. */
static bool configure_managed_adc(void)
{
    if (!prepared || !adc || !clock_ready()) return false;
    writel(saved_adc[1] & ~BIT(16), adc + 4);
    writel((saved_adc[0] & 0xffff) | (479u << 16), adc);
    writel(1, adc + 8);
    writel(0, adc + 0xc); writel(0, adc + 0x20);
    writel(0, adc + 0x24); writel(0, adc + 0x28);
    writel((saved_adc[1] & ~0x300u) | 0x10200, adc + 4);
    msleep(10);
    return true;
}

static void restore_hardware(void)
{
    int i;
    if (prepared && adc && clock_ready() && recovery_still_owned() &&
            !(readl(adc + 8) & ~1u)) {
        writel(readl(adc + 4) & ~BIT(16), adc + 4);
        for (i = 0; i < 7; i++) writel(saved_adc[i], adc + registers[i]);
    } else if (prepared) {
        pr_err("h700_stick_axes: ADC unavailable or other owner present; skipped register restore\n");
    }
    for (i = 0; i < requested && i < 3; i++)
        gpio_set_value(gpio_base + pins[i], (saved_pi_data >> i) & 1);
    if (pio && requested) {
        u32 mux = h700_mux_mask(requested), clicks = h700_click_mask(requested);
        u32 pull = h700_click_pull_mask(requested);
        writel((readl(pio + 0x120) & ~mux) | (saved_pi_cfg & mux), pio + 0x120);
        if (clicks) writel((readl(pio + 0x94) & ~clicks) | (saved_pe_cfg & clicks), pio + 0x94);
        if (pull) writel((readl(pio + 0xac) & ~pull) | (saved_pe_pull & pull), pio + 0xac);
    }
    /* Restore only owned bitfields before releasing the GPIO claims. */
    for (i = requested - 1; i >= 0; i--) gpio_free(gpio_base + pins[i]);
    if (adc) iounmap(adc);
    if (pio) iounmap(pio);
    if (ccu) iounmap(ccu);
    adc = pio = ccu = NULL;
    requested = 0; prepared = false;
}

static int prepare_hardware(void)
{
    struct gpio_chip *chip;
    int i, sample, total[4] = {0};
    chip = gpiochip_find(NULL, chip_match);
    if (!chip) return -ENODEV;
    gpio_base = chip->base;
    adc = ioremap(0x05070000, 4096);
    pio = ioremap(0x0300b000, 4096);
    ccu = ioremap(0x03001000, 4096);
    if (!adc || !pio || !ccu) return -ENOMEM;
    /* This BSP leaves the boot GPADC clock/reset ready. Refuse other states
     * rather than competing with the clock/reset controller or an ADC driver. */
    if (!clock_ready()) return -ENODEV;
    saved_pi_cfg = readl(pio + 0x120); saved_pi_data = readl(pio + 0x130);
    saved_pe_cfg = readl(pio + 0x94); saved_pe_pull = readl(pio + 0xac);
    for (i = 0; i < h700_profile_gpio_count(selected); i++) {
        int result = gpio_request_one(gpio_base + pins[i],
                i < 3 ? GPIOF_OUT_INIT_LOW : GPIOF_IN, "h700-model-sticks");
        if (result) return result;
        requested++;
    }
    {
        u32 pull = h700_click_pull_mask(requested);
        writel((saved_pe_pull & ~pull) | (0x50000u & pull), pio + 0xac);
    }
    for (i = 0; i < 7; i++) saved_adc[i] = readl(adc + registers[i]);
    prepared = true;
    if (!configure_managed_adc()) return -ENODEV;
    for (sample = 0; sample < 24; sample++)
        for (i = 0; i < h700_profile_axis_count(selected); i++)
            total[i] += read_channel(channels[i]);
    for (i = 0; i < h700_profile_axis_count(selected); i++) {
        center[i] = total[i] / 24;
        if (center[i] < 1024 || center[i] > 3072) {
            pr_err("h700_stick_axes: axis %d is not centered (%d)\n", i, center[i]);
            return -EINVAL;
        }
    }
    pr_info("h700_stick_axes: model=%s axes=%u centers=%d/%d/%d/%d invert=0x%x\n",
            selected->model, h700_profile_axis_count(selected),
            center[0], center[1], center[2], center[3], selected->invert_mask);
    return 0;
}

static void neutralize_axes(void)
{
    struct input_dev *input = READ_ONCE(handle.dev);
    int i;
    if (!input) return;
    for (i = 0; i < h700_profile_axis_count(selected); i++)
        input_report_abs(input, axes[i], 0);
    input_sync(input);
}

static void neutralize_input(void)
{
    struct input_dev *input = READ_ONCE(handle.dev);
    int i;
    if (!input) return;
    neutralize_axes();
    for (i = 0; i < 2; i++) {
        click_candidate[i] = click_count[i] = click_state[i] = 0;
        if (selected->click_mask & BIT(i))
            input_report_key(input, i ? BTN_THUMBR : BTN_THUMBL, 0);
    }
    input_sync(input);
}

static bool hardware_still_ready(void)
{
    if (!prepared || !adc || !ccu) {
        hardware_reason = "not-prepared";
        return false;
    }
    /* Do not access a clock-gated peripheral merely to print diagnostics. */
    if (!clock_ready()) {
        last_ctrl = last_select = 0xffffffffu;
        hardware_reason = "clock-reset";
        return false;
    }
    last_ctrl = readl(adc + 4);
    last_select = readl(adc + 8);
    if (needs_reconfigure) {
        hardware_reason = "resume-reconfigure";
        return false;
    }
    if ((last_ctrl & 0x10300) != 0x10200) {
        hardware_reason = "adc-control";
        return false;
    }
    if (last_select != 1) {
        hardware_reason = "adc-selection";
        return false;
    }
    hardware_reason = "ready";
    return true;
}

static bool recovery_still_owned(void)
{
    struct device_node *node;
    bool available;
    if (!prepared || !adc || !pio || !ccu ||
            requested != h700_profile_gpio_count(selected)) {
        recovery_reason = "ownership-lost";
        return false;
    }
    node = of_find_node_by_path("/soc@03000000/gpadc");
    if (!node) {
        recovery_reason = "adc-node-missing";
        return false;
    }
    available = of_device_is_available(node);
    of_node_put(node);
    if (available) {
        recovery_reason = "adc-driver-active";
        return false;
    }
    return true;
}

static bool recover_managed_adc(void)
{
    if (recovery_budget_used >= H700_RECOVERY_FAILURE_LIMIT) {
        recovery_reason = "recovery-budget";
        return false;
    }
    if (recovery_started && time_before(jiffies, next_recovery)) return false;
    recovery_started = true;
    next_recovery = jiffies + msecs_to_jiffies(1000);
    if (!recovery_still_owned()) return false;
    if (!clock_ready()) {
        recovery_reason = "clock-reset";
        return false;
    }
    /* Another selected channel/comparator is positive evidence of unrelated
     * ADC use. Never replace it, even while the original DT node is disabled. */
    last_select = readl(adc + 8);
    if (last_select & ~1u) {
        recovery_reason = "unrelated-selection";
        return false;
    }
    if (!configure_managed_adc()) {
        recovery_reason = "clock-reset";
        return false;
    }
    recovery_attempts++;
    recovery_budget_used++;
    needs_reconfigure = false;
    if (!hardware_still_ready()) {
        recovery_failures++;
        recovery_reason = "readback-failed";
        return false;
    }
    recovery_successes++;
    recovery_reason = "owned-adc-restored";
    return true;
}

static bool sample_diagnostic(const char *reason, bool gated, bool force)
{
    u32 pi_cfg, pi_data, pe_cfg, pe_pull;
    /* State flapping must not bypass the bounded cadence. This guard also
     * survives suspend/resume; even transition diagnostics are <= 1/second. */
    if (diagnostic_ever_logged &&
        time_before(jiffies, last_diagnostic + msecs_to_jiffies(1000))) return false;
    if (!force && diagnostic_started &&
        time_before(jiffies, next_diagnostic)) return false;
    pi_cfg = pio ? readl(pio + 0x120) : 0xffffffffu;
    pi_data = pio ? readl(pio + 0x130) : 0xffffffffu;
    pe_cfg = pio ? readl(pio + 0x94) : 0xffffffffu;
    pe_pull = pio ? readl(pio + 0xac) : 0xffffffffu;
    /* Fixed fields only: no serials, arbitrary addresses or user data. Raw
     * values are the last actual channel sample, with age and validity. */
    pr_info("h700_stick_axes: model=%s reason=%s stopreason=%s armed=0x%x clicks_released=0x%x raw=%d/%d/%d/%d raw_valid=%u raw_age_ms=%u center=%d/%d/%d/%d clicks=0x%x ctrl=0x%08x select=0x%08x ccu=0x%08x blocked=%u polls=%lu recovery=%s attempts=%u successes=%u failures=%u budget=%u reconfigure=%u pi_cfg=0x%08x pi_data=0x%08x pe_cfg=0x%08x pe_pull=0x%08x\n",
            selected->model, reason, hardware_blocked ? hardware_reason : gated ? "neutral" : "none",
            neutral_gate.armed_mask,
            neutral_gate.click_released_mask,
            last_raw[0], last_raw[1], last_raw[2], last_raw[3],
            raw_valid ? 1u : 0u,
            raw_valid ? jiffies_to_msecs(jiffies - raw_jiffies) : 0u,
            center[0], center[1], center[2], center[3], last_clicks,
            last_ctrl, last_select, last_ccu, hardware_blocked ? 1u : 0u, poll_count,
            recovery_reason, recovery_attempts, recovery_successes,
            recovery_failures, recovery_budget_used, needs_reconfigure ? 1u : 0u,
            pi_cfg, pi_data, pe_cfg, pe_pull);
    diagnostic_started = true;
    diagnostic_gated = gated;
    diagnostic_ever_logged = true;
    last_diagnostic = jiffies;
    next_diagnostic = jiffies + msecs_to_jiffies(gated ? 5000 : 60000);
    return true;
}

static void poll_sticks(struct work_struct *work)
{
    int i, values[4] = {0};
    unsigned int clicks = 0, armed, required;
    bool gated;
    struct input_dev *input = READ_ONCE(handle.dev);
    (void)work;
    if (!READ_ONCE(active) || READ_ONCE(suspended) || !input) return;
    poll_count++;
    /* PE8/PE9 are GPIO switches. An ADC mode/reset failure must not swallow
     * their edges or restart their independent release/debounce history. */
    for (i = 0; i < 2; i++)
        if ((selected->click_mask & BIT(i)) && !gpio_get_value(gpio_base + pins[i + 3]))
            clicks |= BIT(i);
    last_clicks = clicks;
    h700_observe_neutral(&neutral_gate, NULL, 0, clicks, selected->click_mask);
    for (i = 0; i < 2; i++) {
        int pressed = !!(clicks & BIT(i));
        if (!(selected->click_mask & BIT(i))) continue;
        if (!(neutral_gate.click_released_mask & BIT(i))) {
            click_candidate[i] = click_count[i] = click_state[i] = 0;
            input_report_key(input, i ? BTN_THUMBR : BTN_THUMBL, 0);
            continue;
        }
        if (pressed != click_candidate[i]) {
            click_candidate[i] = pressed; click_count[i] = 1;
        } else if (click_count[i] < 2) click_count[i]++;
        if (click_count[i] == 2 && pressed != click_state[i]) {
            click_state[i] = pressed;
            input_report_key(input, i ? BTN_THUMBR : BTN_THUMBL, pressed);
        }
    }
    if (!hardware_still_ready()) {
        bool first_block = !hardware_blocked;
        recovery_healthy_tracking = false;
        if (first_block) {
            hardware_blocked = true;
            h700_reset_axis_gate(&neutral_gate);
            neutralize_axes();
        }
        if (!recover_managed_adc()) {
            sample_diagnostic(hardware_reason, true, first_block);
            input_sync(input);
            goto next_poll;
        }
    }
    if (hardware_blocked) {
        hardware_blocked = false;
        h700_reset_axis_gate(&neutral_gate);
        diagnostic_recovery_pending = true;
    }
    for (i = 0; i < h700_profile_axis_count(selected); i++) {
        last_raw[i] = read_channel(channels[i]);
        values[i] = h700_profile_axis_sign(selected, i,
            h700_axis_value(last_raw[i], center[i]));
    }
    raw_jiffies = jiffies;
    raw_valid = true;
    /* A readback that succeeds for one poll is not a stable recovery. Three
     * writes without a full second of healthy sampling exhaust the budget,
     * including repeated interference after temporarily successful writes. */
    if (!recovery_healthy_tracking) {
        recovery_healthy_tracking = true;
        recovery_healthy_since = jiffies;
    } else if (!time_before(jiffies,
                    recovery_healthy_since + msecs_to_jiffies(1000))) {
        recovery_budget_used = 0;
        recovery_failures = 0;
    }
    armed = h700_observe_neutral(&neutral_gate, values,
                h700_profile_axis_count(selected), 0, 0);
    for (i = 0; i < h700_profile_axis_count(selected); i++)
        input_report_abs(input, axes[i], (armed & BIT(i / 2)) ? values[i] : 0);
    input_sync(input);
    required = (1u << selected->sticks) - 1;
    gated = armed != required ||
        neutral_gate.click_released_mask != selected->click_mask;
    if (sample_diagnostic(diagnostic_recovery_pending ? "hardware-restored" : gated ? "neutral-gate" : "ready",
            gated, diagnostic_recovery_pending || !diagnostic_started || diagnostic_gated != gated))
        diagnostic_recovery_pending = false;
next_poll:
    if (READ_ONCE(active) && !READ_ONCE(suspended))
        queue_delayed_work(system_freezable_wq, &poll_work, msecs_to_jiffies(10));
}

static int sticks_pm_event(struct notifier_block *nb, unsigned long event, void *unused)
{
    (void)nb; (void)unused;
    switch (event) {
    case PM_SUSPEND_PREPARE:
    case PM_HIBERNATION_PREPARE:
    case PM_RESTORE_PREPARE:
        suspended = true;
        cancel_delayed_work_sync(&poll_work);
        h700_reset_neutral_gate(&neutral_gate);
        neutralize_input();
        /* The first resumed poll records fresh fixed diagnostic state. */
        diagnostic_started = false;
        break;
    case PM_POST_SUSPEND:
    case PM_POST_HIBERNATION:
    case PM_POST_RESTORE:
        h700_reset_neutral_gate(&neutral_gate);
        /* Hardware restoration runs in the worker, not in a PM notifier.
         * Never calibrate a stick held during wake as a new neutral center. */
        needs_reconfigure = true;
        recovery_failures = 0;
        recovery_budget_used = 0;
        recovery_healthy_tracking = false;
        suspended = false;
        if (READ_ONCE(active))
            queue_delayed_work(system_freezable_wq, &poll_work, 0);
        break;
    }
    return NOTIFY_DONE;
}

static struct notifier_block sticks_pm_notifier = { .notifier_call = sticks_pm_event };

static int connect_input(struct input_handler *handler, struct input_dev *input,
                         const struct input_device_id *id)
{
    int i, result;
    (void)id;
    if (handle.dev || !input->name || strcmp(input->name, "ANBERNIC-keys") || !input->absinfo)
        return -ENODEV;
    for (i = 0; i < h700_profile_axis_count(selected); i++)
        if (test_bit(axes[i], input->absbit)) return -EBUSY;
    handle.dev = input; handle.handler = handler; handle.name = "h700-model-sticks";
    result = input_register_handle(&handle);
    if (result) { handle.dev = NULL; return result; }
    old_abs_bits = 0; old_key_bits = 0;
    for (i = 0; i < h700_profile_axis_count(selected); i++) {
        old_abs[i] = input->absinfo[axes[i]];
        if (test_bit(axes[i], input->absbit)) old_abs_bits |= BIT(i);
        input_set_abs_params(input, axes[i], -32767, 32767, 128, 4096);
    }
    for (i = 0; i < 2; i++) {
        unsigned int key = i ? BTN_THUMBR : BTN_THUMBL;
        if (!(selected->click_mask & BIT(i))) continue;
        if (test_bit(key, input->keybit)) old_key_bits |= BIT(i);
        input_set_capability(input, EV_KEY, key);
    }
    h700_reset_neutral_gate(&neutral_gate);
    hardware_blocked = false;
    diagnostic_started = false;
    active = true;
    pr_info("h700_stick_axes: attached to existing %s; original keys and force feedback retained\n", input->name);
    return 0;
}

static void disconnect_input(struct input_handle *unused)
{
    struct input_dev *input = handle.dev;
    unsigned long flags;
    int i;
    (void)unused;
    active = false;
    cancel_delayed_work_sync(&poll_work);
    neutralize_input();
    spin_lock_irqsave(&input->event_lock, flags);
    for (i = 0; i < h700_profile_axis_count(selected); i++) {
        input->absinfo[axes[i]] = old_abs[i];
        if (!(old_abs_bits & BIT(i))) __clear_bit(axes[i], input->absbit);
    }
    for (i = 0; i < 2; i++)
        if ((selected->click_mask & BIT(i)) && !(old_key_bits & BIT(i)))
            __clear_bit(i ? BTN_THUMBR : BTN_THUMBL, input->keybit);
    spin_unlock_irqrestore(&input->event_lock, flags);
    input_unregister_handle(&handle);
    handle.dev = NULL;
}

static const struct input_device_id match_ids[] = {
    {.flags = INPUT_DEVICE_ID_MATCH_EVBIT, .evbit = {BIT_MASK(EV_ABS)}}, {}
};
MODULE_DEVICE_TABLE(input, match_ids);
static struct input_handler handler = {
    .connect = connect_input, .disconnect = disconnect_input,
    .name = "h700-model-stick-axes", .id_table = match_ids,
};

static int __init sticks_init(void)
{
    struct device_node *node;
    int result;
    selected = h700_profile_lookup(profile);
    if (!selected) return -EINVAL;
    if (!selected->sticks) {
        pr_info("h700_stick_axes: model=%s has no sticks; no ADC/GPIO/input changes\n", selected->model);
        return 0;
    }
    if (!h700_profile_needs_hardware(selected)) {
        pr_err("h700_stick_axes: model=%s has %u sticks but electrical profile is unverified\n",
                selected->model, selected->sticks);
        return -EOPNOTSUPP;
    }
    if (!of_machine_is_compatible("allwinner,h616")) return -ENODEV;
    node = of_find_node_by_path("/soc@03000000/gpadc");
    if (!node) return -ENODEV;
    result = of_device_is_available(node);
    of_node_put(node);
    if (result) return -EBUSY; /* An active ADC driver must keep ownership. */
    if (probe_only) { pr_info("h700_stick_axes: ABI/profile probe only; no input or register changes\n"); return 0; }
    INIT_DELAYED_WORK(&poll_work, poll_sticks);
    result = prepare_hardware();
    if (result) goto failed;
    result = register_pm_notifier(&sticks_pm_notifier);
    if (result) goto failed;
    notifier_registered = true;
    result = input_register_handler(&handler);
    if (result) goto failed;
    handler_registered = true;
    if (!handle.dev) { result = -ENODEV; goto failed; }
    queue_delayed_work(system_freezable_wq, &poll_work, 0);
    return 0;
failed:
    if (notifier_registered) { unregister_pm_notifier(&sticks_pm_notifier); notifier_registered = false; }
    if (handler_registered) { input_unregister_handler(&handler); handler_registered = false; }
    restore_hardware();
    return result;
}

static void __exit sticks_exit(void)
{
    if (probe_only || !h700_profile_needs_hardware(selected)) return;
    if (notifier_registered) { unregister_pm_notifier(&sticks_pm_notifier); notifier_registered = false; }
    if (handler_registered) { input_unregister_handler(&handler); handler_registered = false; }
    restore_hardware();
    pr_info("h700_stick_axes: original input capabilities and registers restored\n");
}
module_init(sticks_init);
module_exit(sticks_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Explicit H700 model stick profiles on the existing BSP input device");

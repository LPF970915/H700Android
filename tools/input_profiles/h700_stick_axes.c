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
static bool prepared, active, suspended, handler_registered, notifier_registered;
static struct h700_neutral_gate neutral_gate;
static int click_candidate[2], click_count[2], click_state[2];

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

static void restore_hardware(void)
{
    int i;
    if (prepared) {
        writel(readl(adc + 4) & ~BIT(16), adc + 4);
        for (i = 0; i < 7; i++) writel(saved_adc[i], adc + registers[i]);
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
    if ((readl(ccu + 0x9ec) & 0x10001) != 0x10001) return -ENODEV;
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
    writel(saved_adc[1] & ~BIT(16), adc + 4);
    writel((saved_adc[0] & 0xffff) | (479u << 16), adc);
    writel(1, adc + 8);
    writel(0, adc + 0xc); writel(0, adc + 0x20);
    writel(0, adc + 0x24); writel(0, adc + 0x28);
    writel((saved_adc[1] & ~0x300u) | 0x10200, adc + 4);
    msleep(10);
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

static void neutralize_input(void)
{
    struct input_dev *input = READ_ONCE(handle.dev);
    int i;
    if (!input) return;
    for (i = 0; i < h700_profile_axis_count(selected); i++)
        input_report_abs(input, axes[i], 0);
    for (i = 0; i < 2; i++) {
        click_candidate[i] = click_count[i] = click_state[i] = 0;
        if (selected->click_mask & BIT(i))
            input_report_key(input, i ? BTN_THUMBR : BTN_THUMBL, 0);
    }
    input_sync(input);
}

static bool hardware_still_ready(void)
{
    return prepared && adc && ccu
        && (readl(ccu + 0x9ec) & 0x10001) == 0x10001
        && (readl(adc + 4) & 0x10300) == 0x10200;
}

static void poll_sticks(struct work_struct *work)
{
    int i, values[4] = {0};
    unsigned int clicks = 0;
    struct input_dev *input = READ_ONCE(handle.dev);
    (void)work;
    if (!READ_ONCE(active) || READ_ONCE(suspended) || !input) return;
    if (!hardware_still_ready()) {
        suspended = true;
        h700_reset_neutral_gate(&neutral_gate);
        neutralize_input();
        pr_err("h700_stick_axes: ADC/clock state changed; axes neutral, refusing register takeover\n");
        return;
    }
    for (i = 0; i < h700_profile_axis_count(selected); i++)
        values[i] = h700_profile_axis_sign(selected, i,
            h700_axis_value(read_channel(channels[i]), center[i]));
    for (i = 0; i < 2; i++)
        if ((selected->click_mask & BIT(i)) && !gpio_get_value(gpio_base + pins[i + 3]))
            clicks |= BIT(i);
    if (!h700_observe_neutral(&neutral_gate, values,
                             h700_profile_axis_count(selected), clicks))
        goto next_poll;
    for (i = 0; i < h700_profile_axis_count(selected); i++)
        input_report_abs(input, axes[i], values[i]);
    for (i = 0; i < 2; i++) {
        int pressed = !!(clicks & BIT(i));
        if (!(selected->click_mask & BIT(i))) continue;
        if (pressed != click_candidate[i]) {
            click_candidate[i] = pressed; click_count[i] = 1;
        } else if (click_count[i] < 2) click_count[i]++;
        if (click_count[i] == 2 && pressed != click_state[i]) {
            click_state[i] = pressed;
            input_report_key(input, i ? BTN_THUMBR : BTN_THUMBL, pressed);
        }
    }
    input_sync(input);
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
        break;
    case PM_POST_SUSPEND:
    case PM_POST_HIBERNATION:
    case PM_POST_RESTORE:
        h700_reset_neutral_gate(&neutral_gate);
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

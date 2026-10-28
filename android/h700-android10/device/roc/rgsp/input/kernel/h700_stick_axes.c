// SPDX-License-Identifier: GPL-2.0-only
/* Add RG34XXSP sticks to the existing BSP controller, retaining its keys/FF.
 * Wiring reference: ROCKNIX H700 DTS (PI0/1/2 mux, PE8/9 stick switches).
 * Register definitions: Allwinner H616 BSP sunxi_gpadc.h, clk-sun50iw9.h.
 */
#include <linux/module.h>
#include <linux/input.h>
#include <linux/gpio.h>
#include <linux/gpio/driver.h>
#include <linux/io.h>
#include <linux/mm.h>
#include <linux/of.h>
#include <linux/delay.h>
#include <linux/workqueue.h>
#include "../axis_math.h"

static char *profile;
module_param(profile, charp, 0444);
static bool probe_only;
module_param(probe_only, bool, 0444);
MODULE_PARM_DESC(profile, "Explicit board profile; only rg34xxsp is supported");

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
static bool prepared, active;
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
    for (i = requested - 1; i >= 0; i--) gpio_free(gpio_base + pins[i]);
    if (pio && requested) {
        u32 mux = h700_mux_mask(requested), clicks = h700_click_mask(requested);
        u32 pull = h700_click_pull_mask(requested);
        writel((readl(pio + 0x120) & ~mux) | (saved_pi_cfg & mux), pio + 0x120);
        if (clicks) writel((readl(pio + 0x94) & ~clicks) | (saved_pe_cfg & clicks), pio + 0x94);
        if (pull) writel((readl(pio + 0xac) & ~pull) | (saved_pe_pull & pull), pio + 0xac);
    }
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
    for (i = 0; i < 5; i++) {
        int result = gpio_request_one(gpio_base + pins[i],
                i < 3 ? GPIOF_OUT_INIT_LOW : GPIOF_IN, "rg34xxsp-sticks");
        if (result) return result;
        requested++;
    }
    writel((saved_pe_pull & ~0xf0000u) | 0x50000, pio + 0xac);
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
        for (i = 0; i < 4; i++) total[i] += read_channel(channels[i]);
    for (i = 0; i < 4; i++) {
        center[i] = total[i] / 24;
        if (center[i] < 1024 || center[i] > 3072) {
            pr_err("h700_stick_axes: axis %d is not centered (%d)\n", i, center[i]);
            return -EINVAL;
        }
    }
    pr_info("h700_stick_axes: calibrated X/Y/Z/RZ %d/%d/%d/%d\n",
            center[0], center[1], center[2], center[3]);
    return 0;
}

static void poll_sticks(struct work_struct *work)
{
    int i;
    struct input_dev *input = READ_ONCE(handle.dev);
    (void)work;
    if (!READ_ONCE(active) || !input) return;
    for (i = 0; i < 4; i++)
        input_report_abs(input, axes[i], h700_axis_value(read_channel(channels[i]), center[i]));
    for (i = 0; i < 2; i++) {
        int pressed = !gpio_get_value(gpio_base + pins[i + 3]);
        if (pressed != click_candidate[i]) {
            click_candidate[i] = pressed; click_count[i] = 1;
        } else if (click_count[i] < 2) click_count[i]++;
        if (click_count[i] == 2 && pressed != click_state[i]) {
            click_state[i] = pressed;
            input_report_key(input, i ? BTN_THUMBR : BTN_THUMBL, pressed);
        }
    }
    input_sync(input);
    if (READ_ONCE(active)) queue_delayed_work(system_freezable_wq, &poll_work, msecs_to_jiffies(10));
}

static int connect_input(struct input_handler *handler, struct input_dev *input,
                         const struct input_device_id *id)
{
    int i, result;
    (void)id;
    if (handle.dev || !input->name || strcmp(input->name, "ANBERNIC-keys") || !input->absinfo)
        return -ENODEV;
    for (i = 0; i < 4; i++)
        if (test_bit(axes[i], input->absbit)) return -EBUSY;
    handle.dev = input; handle.handler = handler; handle.name = "rg34xxsp-sticks";
    result = input_register_handle(&handle);
    if (result) { handle.dev = NULL; return result; }
    old_abs_bits = 0; old_key_bits = 0;
    for (i = 0; i < 4; i++) {
        old_abs[i] = input->absinfo[axes[i]];
        if (test_bit(axes[i], input->absbit)) old_abs_bits |= BIT(i);
        input_set_abs_params(input, axes[i], -32767, 32767, 128, 4096);
    }
    for (i = 0; i < 2; i++) {
        unsigned int key = i ? BTN_THUMBR : BTN_THUMBL;
        if (test_bit(key, input->keybit)) old_key_bits |= BIT(i);
        input_set_capability(input, EV_KEY, key);
    }
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
    for (i = 0; i < 4; i++) input_report_abs(input, axes[i], 0);
    for (i = 0; i < 2; i++) input_report_key(input, i ? BTN_THUMBR : BTN_THUMBL, 0);
    input_sync(input);
    spin_lock_irqsave(&input->event_lock, flags);
    for (i = 0; i < 4; i++) {
        input->absinfo[axes[i]] = old_abs[i];
        if (!(old_abs_bits & BIT(i))) __clear_bit(axes[i], input->absbit);
    }
    for (i = 0; i < 2; i++)
        if (!(old_key_bits & BIT(i))) __clear_bit(i ? BTN_THUMBR : BTN_THUMBL, input->keybit);
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
    .name = "h700-rg34xxsp-stick-axes", .id_table = match_ids,
};

static int __init sticks_init(void)
{
    struct device_node *node;
    int result;
    if (!profile || strcmp(profile, "rg34xxsp") || !of_machine_is_compatible("allwinner,h616")
            || totalram_pages < (1536UL << (20 - PAGE_SHIFT))) return -ENODEV;
    node = of_find_node_by_path("/soc@03000000/gpadc");
    if (!node) return -ENODEV;
    result = of_device_is_available(node);
    of_node_put(node);
    if (result) return -EBUSY; /* An active ADC driver must keep ownership. */
    if (probe_only) { pr_info("h700_stick_axes: ABI/profile probe only; no input or register changes\n"); return 0; }
    INIT_DELAYED_WORK(&poll_work, poll_sticks);
    result = prepare_hardware();
    if (result) goto failed;
    result = input_register_handler(&handler);
    if (result) goto failed;
    if (!handle.dev) { input_unregister_handler(&handler); result = -ENODEV; goto failed; }
    queue_delayed_work(system_freezable_wq, &poll_work, 0);
    return 0;
failed:
    restore_hardware();
    return result;
}

static void __exit sticks_exit(void)
{
    if (probe_only) return;
    input_unregister_handler(&handler);
    restore_hardware();
    pr_info("h700_stick_axes: original input capabilities and registers restored\n");
}
module_init(sticks_init);
module_exit(sticks_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("RG34XXSP analog axes on the existing H700 BSP input device");

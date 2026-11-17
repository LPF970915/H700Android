/* Host API seam. Real driver code executes; hardware and scheduling do not. */
#ifndef H700_TEST_KERNEL_SHIM_H
#define H700_TEST_KERNEL_SHIM_H
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <stdarg.h>
#include <linux/input-event-codes.h>
typedef uint32_t u32;
#define __iomem
#define __init
#define __exit
#define module_param(...)
#define MODULE_PARM_DESC(...)
#define MODULE_DEVICE_TABLE(...)
#define MODULE_LICENSE(...)
#define MODULE_DESCRIPTION(...)
#define module_init(...)
#define module_exit(...)
#define BIT(n) (1UL << (n))
#define BIT_MASK(n) BIT(n)
#define READ_ONCE(value) (value)
#define GPIOF_OUT_INIT_LOW 0
#define GPIOF_IN 1
#define INPUT_DEVICE_ID_MATCH_EVBIT 1
#define NOTIFY_DONE 0
/* Exact retained Linux include/linux/suspend.h values, not a test-only enum. */
#define PM_HIBERNATION_PREPARE 0x0001
#define PM_POST_HIBERNATION 0x0002
#define PM_SUSPEND_PREPARE 0x0003
#define PM_POST_SUSPEND 0x0004
#define PM_RESTORE_PREPARE 0x0005
#define PM_POST_RESTORE 0x0006
#define pr_info(...) mock_log_message(__VA_ARGS__)
#define pr_err(...) pr_info(__VA_ARGS__)
#define spin_lock_irqsave(lock, flags) ((void)(lock), (flags) = 0)
#define spin_unlock_irqrestore(lock, flags) ((void)(lock), (void)(flags))
struct work_struct { int unused; };
struct delayed_work { void (*function)(struct work_struct *); };
#define INIT_DELAYED_WORK(work, fn) ((work)->function = (fn))
struct gpio_chip { unsigned int ngpio; const char *label; int base; };
struct input_absinfo { int value, minimum, maximum, fuzz, flat, resolution; };
struct input_dev {
    const char *name;
    struct input_absinfo *absinfo;
    unsigned long absbit[2], keybit[16];
    int event_lock;
};
struct input_handler;
struct input_handle { struct input_dev *dev; struct input_handler *handler; const char *name; };
struct input_device_id { unsigned long flags, evbit[1]; };
struct input_handler {
    int (*connect)(struct input_handler *, struct input_dev *, const struct input_device_id *);
    void (*disconnect)(struct input_handle *);
    const char *name;
    const struct input_device_id *id_table;
};
struct device_node { int unused; };
struct notifier_block { int (*notifier_call)(struct notifier_block *, unsigned long, void *); };
static u32 mock_adc[1024], mock_pio[1024], mock_ccu[1024];
static u32 mock_adc_ctrl_read_clear_mask;
static int mock_raw[4], mock_gpio_levels[512], mock_gpio_owned[512];
static int mock_gpio_reads[512], mock_channel_reads[4];
static int mock_gpio_fail_at = -1, mock_gpio_requests, mock_gpio_frees;
static int mock_maps, mock_unmaps, mock_writes, mock_adc_reads, mock_adc_mmio_reads;
static int mock_adc_writes, mock_ccu_writes, mock_pio_writes;
static int mock_queue_calls, mock_cancel_calls, mock_handle_result;
static unsigned int mock_last_delay, mock_log_calls, mock_gpio_sets;
static unsigned long jiffies;
#define time_before(a, b) ((long)((a) - (b)) < 0)
#define time_after_eq(a, b) (!time_before(a, b))
static int mock_handler_result, mock_notifier_result, mock_pm_registered;
static int mock_compatible = 1, mock_adc_node = 1, mock_adc_available, mock_chip_available = 1;
static int mock_abs_events[64], mock_key_events[768], mock_key_reports[768], mock_syncs;
static char mock_log[2048];
static unsigned long mock_log_times[4096], mock_adc_write_times[4096];
static struct gpio_chip mock_chip = {288, "pio", 1000};
static struct device_node mock_node;
static struct input_absinfo mock_absinfo[64];
static struct input_dev mock_input;
static void *system_freezable_wq = (void *)1;
static inline void mock_log_message(const char *format, ...)
{
    va_list arguments;
    va_start(arguments, format);
    vsnprintf(mock_log, sizeof(mock_log), format, arguments);
    va_end(arguments);
    if (mock_log_calls < 4096) mock_log_times[mock_log_calls] = jiffies;
    mock_log_calls++;
}
static inline int mock_in_range(const void *address, const u32 *base)
{
    uintptr_t p = (uintptr_t)address, b = (uintptr_t)base;
    return p >= b && p < b + 4096;
}
static inline unsigned int mock_gpio_index(int gpio) { return (unsigned int)(gpio - mock_chip.base); }
static inline struct gpio_chip *gpiochip_find(void *data, int (*match)(struct gpio_chip *, void *))
{ return mock_chip_available && match(&mock_chip, data) ? &mock_chip : NULL; }
static inline void *ioremap(unsigned long address, size_t length)
{
    (void)length; mock_maps++;
    if (address == 0x05070000) return mock_adc;
    if (address == 0x0300b000) return mock_pio;
    if (address == 0x03001000) return mock_ccu;
    return NULL;
}
static inline void iounmap(void *address) { (void)address; mock_unmaps++; }
static inline u32 readl(const void *address)
{
    if (mock_in_range(address, mock_adc)) mock_adc_mmio_reads++;
    if (address == (const char *)mock_adc + 0x80) {
        unsigned int channel = (unsigned int)mock_gpio_levels[257]
                             | ((unsigned int)mock_gpio_levels[258] << 1);
        mock_adc_reads++; mock_channel_reads[channel]++;
        return (u32)mock_raw[channel];
    }
    if (address == (const char *)mock_adc + 4)
        return *(const u32 *)address & ~mock_adc_ctrl_read_clear_mask;
    return *(const u32 *)address;
}
static inline void writel(u32 value, void *address)
{
    mock_writes++;
    if (mock_in_range(address, mock_adc)) {
        if (mock_adc_writes < 4096) mock_adc_write_times[mock_adc_writes] = jiffies;
        mock_adc_writes++;
    }
    if (mock_in_range(address, mock_ccu)) mock_ccu_writes++;
    if (mock_in_range(address, mock_pio)) mock_pio_writes++;
    *(u32 *)address = value;
}
static inline int gpio_request_one(int gpio, unsigned long flags, const char *name)
{
    unsigned int pin = mock_gpio_index(gpio), shift;
    (void)name;
    if (mock_gpio_fail_at == mock_gpio_requests++) return -EBUSY;
    if (mock_gpio_owned[pin]) return -EBUSY;
    mock_gpio_owned[pin] = 1;
    if (pin >= 256 && pin <= 258) {
        shift = (pin - 256) * 4;
        mock_pio[0x120 / 4] = (mock_pio[0x120 / 4] & ~(15u << shift)) |
            ((flags == GPIOF_IN ? 0u : 1u) << shift);
    }
    if (pin == 136 || pin == 137) {
        shift = (pin - 136) * 4;
        mock_pio[0x94 / 4] &= ~(15u << shift);
    }
    if (flags == GPIOF_OUT_INIT_LOW) mock_gpio_levels[pin] = 0;
    return 0;
}
static inline void gpio_free(int gpio) { mock_gpio_owned[mock_gpio_index(gpio)] = 0; mock_gpio_frees++; }
static inline void gpio_set_value(int gpio, int value)
{
    unsigned int pin = mock_gpio_index(gpio);
    mock_gpio_sets++; mock_gpio_levels[pin] = !!value;
    if (pin >= 256 && pin <= 287) {
        unsigned int bit = pin - 256;
        mock_pio[0x130 / 4] = (mock_pio[0x130 / 4] & ~(1u << bit)) | ((!!value) << bit);
    }
}
static inline int gpio_get_value(int gpio)
{ unsigned int pin = mock_gpio_index(gpio); mock_gpio_reads[pin]++; return mock_gpio_levels[pin]; }
static inline void usleep_range(unsigned int lo, unsigned int hi) { (void)lo; (void)hi; }
static inline void msleep(unsigned int ms) { (void)ms; }
static inline unsigned int msecs_to_jiffies(unsigned int ms) { return ms; }
static inline unsigned int jiffies_to_msecs(unsigned long ticks) { return (unsigned int)ticks; }
static inline int queue_delayed_work(void *queue, struct delayed_work *work, unsigned int delay)
{ (void)queue; (void)work; mock_last_delay = delay; mock_queue_calls++; return 1; }
static inline int cancel_delayed_work_sync(struct delayed_work *work)
{ (void)work; mock_cancel_calls++; return 1; }
static inline int test_bit(unsigned int bit, const unsigned long *set)
{ return !!(set[bit / (8 * sizeof(*set))] & BIT(bit % (8 * sizeof(*set)))); }
static inline void __set_bit(unsigned int bit, unsigned long *set)
{ set[bit / (8 * sizeof(*set))] |= BIT(bit % (8 * sizeof(*set))); }
static inline void __clear_bit(unsigned int bit, unsigned long *set)
{ set[bit / (8 * sizeof(*set))] &= ~BIT(bit % (8 * sizeof(*set))); }
static inline int input_register_handle(struct input_handle *entry) { (void)entry; return mock_handle_result; }
static inline void input_unregister_handle(struct input_handle *entry) { (void)entry; }
static inline void input_set_abs_params(struct input_dev *dev, unsigned int axis,
                                       int minimum, int maximum, int fuzz, int flat)
{
    __set_bit(axis, dev->absbit);
    dev->absinfo[axis].minimum = minimum; dev->absinfo[axis].maximum = maximum;
    dev->absinfo[axis].fuzz = fuzz; dev->absinfo[axis].flat = flat;
}
static inline void input_set_capability(struct input_dev *dev, unsigned int type, unsigned int code)
{ (void)type; __set_bit(code, dev->keybit); }
static inline void input_report_abs(struct input_dev *dev, unsigned int axis, int value)
{ dev->absinfo[axis].value = value; mock_abs_events[axis]++; }
static inline void input_report_key(struct input_dev *dev, unsigned int code, int value)
{ (void)dev; mock_key_events[code] = value; mock_key_reports[code]++; }
static inline void input_sync(struct input_dev *dev) { (void)dev; mock_syncs++; }
static inline int input_register_handler(struct input_handler *entry)
{
    if (mock_handler_result) return mock_handler_result;
    entry->connect(entry, &mock_input, entry->id_table);
    return 0;
}
static inline void input_unregister_handler(struct input_handler *entry)
{
    extern struct input_handle *h700_test_current_handle(void);
    struct input_handle *current = h700_test_current_handle();
    if (current->dev) entry->disconnect(current);
}
static inline int of_machine_is_compatible(const char *name) { (void)name; return mock_compatible; }
static inline struct device_node *of_find_node_by_path(const char *name)
{ (void)name; return mock_adc_node ? &mock_node : NULL; }
static inline int of_device_is_available(const struct device_node *node) { (void)node; return mock_adc_available; }
static inline void of_node_put(struct device_node *node) { (void)node; }
static inline int register_pm_notifier(struct notifier_block *nb)
{ (void)nb; if (mock_notifier_result) return mock_notifier_result; mock_pm_registered++; return 0; }
static inline int unregister_pm_notifier(struct notifier_block *nb) { (void)nb; mock_pm_registered--; return 0; }
#endif

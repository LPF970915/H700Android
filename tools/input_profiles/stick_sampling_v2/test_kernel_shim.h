/* Host-only Linux API boundary for executing the actual candidate C file. */
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
#define PM_SUSPEND_PREPARE 1
#define PM_HIBERNATION_PREPARE 2
#define PM_RESTORE_PREPARE 3
#define PM_POST_SUSPEND 4
#define PM_POST_HIBERNATION 5
#define PM_POST_RESTORE 6
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
static int mock_raw[4], mock_gpio_levels[512], mock_gpio_owned[512];
static int mock_gpio_fail_at, mock_gpio_requests, mock_gpio_frees;
static int mock_maps, mock_unmaps, mock_writes, mock_adc_reads;
static int mock_queue_calls, mock_cancel_calls, mock_handle_result;
static unsigned int mock_last_delay, mock_log_calls, mock_gpio_sets;
static unsigned long jiffies;
#define time_before(a, b) ((long)((a) - (b)) < 0)
static int mock_handler_result, mock_notifier_result, mock_pm_registered;
static int mock_compatible, mock_adc_node, mock_adc_available, mock_chip_available;
static int mock_abs_events[64], mock_key_events[768], mock_syncs;
static char mock_log[1024];
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
    mock_log_calls++;
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
    if (address == (const char *)mock_adc + 0x80) {
        unsigned int channel = (unsigned int)mock_gpio_levels[257]
                             | ((unsigned int)mock_gpio_levels[258] << 1);
        mock_adc_reads++;
        return (u32)mock_raw[channel];
    }
    return *(const u32 *)address;
}
static inline void writel(u32 value, void *address) { mock_writes++; *(u32 *)address = value; }
static inline int gpio_request_one(int gpio, unsigned long flags, const char *name)
{
    unsigned int pin = mock_gpio_index(gpio);
    (void)name;
    if (mock_gpio_fail_at == mock_gpio_requests++) return -EBUSY;
    if (mock_gpio_owned[pin]) return -EBUSY;
    mock_gpio_owned[pin] = 1;
    if (flags == GPIOF_OUT_INIT_LOW) mock_gpio_levels[pin] = 0;
    return 0;
}
static inline void gpio_free(int gpio) { mock_gpio_owned[mock_gpio_index(gpio)] = 0; mock_gpio_frees++; }
static inline void gpio_set_value(int gpio, int value)
{ mock_gpio_sets++; mock_gpio_levels[mock_gpio_index(gpio)] = !!value; }
static inline int gpio_get_value(int gpio) { return mock_gpio_levels[mock_gpio_index(gpio)]; }
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
static inline int input_register_handle(struct input_handle *handle)
{ (void)handle; return mock_handle_result; }
static inline void input_unregister_handle(struct input_handle *handle) { (void)handle; }
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
{ (void)dev; mock_key_events[code] = value; }
static inline void input_sync(struct input_dev *dev) { (void)dev; mock_syncs++; }
static inline int input_register_handler(struct input_handler *handler)
{
    if (mock_handler_result) return mock_handler_result;
    handler->connect(handler, &mock_input, handler->id_table);
    return 0;
}
static inline void input_unregister_handler(struct input_handler *handler)
{
    struct input_handle *handle;
    /* The real driver's singleton is declared after this shim. */
    extern struct input_handle *h700_test_current_handle(void);
    handle = h700_test_current_handle();
    if (handle->dev) handler->disconnect(handle);
}
static inline int of_machine_is_compatible(const char *name)
{ (void)name; return mock_compatible; }
static inline struct device_node *of_find_node_by_path(const char *name)
{ (void)name; return mock_adc_node ? &mock_node : NULL; }
static inline int of_device_is_available(const struct device_node *node)
{ (void)node; return mock_adc_available; }
static inline void of_node_put(struct device_node *node) { (void)node; }
static inline int register_pm_notifier(struct notifier_block *nb)
{ (void)nb; if (mock_notifier_result) return mock_notifier_result; mock_pm_registered++; return 0; }
static inline int unregister_pm_notifier(struct notifier_block *nb)
{ (void)nb; mock_pm_registered--; return 0; }
#endif

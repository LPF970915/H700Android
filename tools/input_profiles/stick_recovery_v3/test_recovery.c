/* Actual driver regression tests. Each invocation starts fresh C static state. */
#define H700_HOST_TEST 1
#include "test_kernel_shim.h"
#ifndef DRIVER_SOURCE
#define DRIVER_SOURCE "h700_stick_axes.c"
#endif
#include DRIVER_SOURCE
#include <stdlib.h>

struct input_handle *h700_test_current_handle(void) { return &handle; }
static unsigned int checks;
#define CHECK(expr) do { checks++; if (!(expr)) { \
    fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #expr); exit(1); \
} } while (0)

static void fixture(const char *model)
{
    unsigned int i;
    mock_input.name = "ANBERNIC-keys";
    mock_input.absinfo = mock_absinfo;
    __set_bit(ABS_HAT0X, mock_input.absbit);
    __set_bit(ABS_HAT0Y, mock_input.absbit);
    __set_bit(ABS_RX, mock_input.absbit);
    __set_bit(BTN_SOUTH, mock_input.keybit);
    mock_gpio_levels[136] = mock_gpio_levels[137] = 1;
    for (i = 0; i < 4; i++) mock_raw[i] = 2048;
    /* Disabled ADC with channel 0 selected reflects the pre-add-on owner. */
    mock_adc[0] = 479u << 16;
    mock_adc[1] = 0x200;
    mock_adc[2] = 1;
    mock_pio[0x120 / 4] = 0x12345000;
    mock_pio[0x94 / 4] = 0x87654300;
    mock_pio[0xac / 4] = 0x12345678;
    mock_ccu[0x9ec / 4] = 0x10001;
    profile = (char *)model;
}

static void start(const char *model)
{
    fixture(model);
    CHECK(sticks_init() == 0);
    CHECK(active && handle.dev == &mock_input);
    CHECK(mock_pm_registered == 1 && mock_ccu_writes == 0);
}

static void sample(unsigned int count)
{
    unsigned int i;
    for (i = 0; i < count; i++) {
        poll_sticks(NULL);
        jiffies += mock_last_delay;
    }
}

static void arm(void)
{
    sample(3);
    CHECK(neutral_gate.armed_mask == (1u << selected->sticks) - 1);
    CHECK(neutral_gate.click_released_mask == selected->click_mask);
}

static void finish(void)
{
    mock_adc_ctrl_read_clear_mask = 0;
    mock_ccu[0x9ec / 4] = 0x10001;
    mock_adc_available = 0; mock_adc_node = 1;
    sticks_exit();
    CHECK(!active && !prepared && !handle.dev);
    CHECK(mock_maps == mock_unmaps && mock_pm_registered == 0);
    CHECK(mock_ccu_writes == 0);
}

static void test_healthy(const char *model)
{
    int writes, i;
    start(model); arm();
    writes = mock_writes;
    for (i = 0; i < 200; i++) {
        mock_raw[3] = i & 1 ? 0 : 4095;
        sample(1);
        CHECK(mock_input.absinfo[ABS_X].value == (i & 1 ? 32767 : -32767));
    }
    CHECK(mock_writes == writes && mock_ccu_writes == 0);
    CHECK(test_bit(BTN_SOUTH, mock_input.keybit));
    CHECK(test_bit(ABS_RX, mock_input.absbit));
    finish();
}

static void test_clicks_during_fault(int clock_off, int negative)
{
    int reads, writes;
    start("rg35xxh"); arm();
    mock_raw[3] = 0; sample(1);
    CHECK(mock_input.absinfo[ABS_X].value == 32767);
    if (clock_off) mock_ccu[0x9ec / 4] = 0;
    else {
        mock_adc[1] &= ~BIT(16);
        mock_adc[2] = 2; /* Another channel is selected: recovery must refuse. */
    }
    reads = mock_adc_mmio_reads; writes = mock_writes;
    mock_gpio_levels[136] = mock_gpio_levels[137] = 0;
    sample(3);
    CHECK(mock_input.absinfo[ABS_X].value == 0);
    CHECK(mock_writes == writes && mock_ccu_writes == 0);
    if (clock_off) CHECK(mock_adc_mmio_reads == reads);
    if (negative) {
        CHECK(!mock_key_events[BTN_THUMBL] && !mock_key_events[BTN_THUMBR]);
    } else {
        CHECK(mock_key_events[BTN_THUMBL] && mock_key_events[BTN_THUMBR]);
        CHECK(mock_gpio_reads[136] >= 3 && mock_gpio_reads[137] >= 3);
        CHECK(mock_last_delay <= 10);
        mock_gpio_levels[136] = mock_gpio_levels[137] = 1;
        sample(2);
        CHECK(!mock_key_events[BTN_THUMBL] && !mock_key_events[BTN_THUMBR]);
    }
    mock_adc[2] = 1;
    finish();
}

static void test_recovery(unsigned int fault, int negative)
{
    int initial_center[4], writes, before;
    start("rg34xxsp"); arm();
    memcpy(initial_center, center, sizeof(center));
    mock_raw[3] = 0; sample(1);
    CHECK(mock_input.absinfo[ABS_X].value == 32767);
    if (fault == 0) mock_adc[1] &= ~BIT(16);
    else if (fault == 1) mock_adc[1] = (mock_adc[1] & ~0x300u) | 0x100u;
    else mock_adc[2] = 0;
    writes = mock_adc_writes; before = mock_adc_reads;
    sample(120);
    CHECK(!memcmp(initial_center, center, sizeof(center)));
    if (negative) {
        CHECK(mock_adc_writes == writes);
        /* v2 ignores the channel selection register entirely. */
        if (fault != 2) CHECK(mock_adc_reads == before);
    } else {
        CHECK(mock_adc_writes > writes && mock_adc_writes <= writes + 16);
        CHECK((mock_adc[1] & 0x10300) == 0x10200 && mock_adc[2] == 1);
        CHECK(mock_adc_reads > before);
        CHECK(mock_input.absinfo[ABS_X].value == 0); /* Held stick cannot rearm. */
        CHECK((neutral_gate.armed_mask & 1) == 0);
        mock_raw[3] = 2048; sample(3);
        CHECK(neutral_gate.armed_mask == 3);
        mock_raw[3] = 4095; sample(1);
        CHECK(mock_input.absinfo[ABS_X].value == -32767);
    }
    finish();
}

static void test_real_pm(unsigned long pre, unsigned long post, int negative)
{
    int reads, queues, writes;
    start("rg35xxh"); arm();
    CHECK(PM_HIBERNATION_PREPARE == 1 && PM_POST_HIBERNATION == 2);
    CHECK(PM_SUSPEND_PREPARE == 3 && PM_POST_SUSPEND == 4);
    CHECK(PM_RESTORE_PREPARE == 5 && PM_POST_RESTORE == 6);
    mock_raw[3] = 0; sample(1);
    sticks_pm_event(NULL, pre, NULL);
    CHECK(suspended && mock_input.absinfo[ABS_X].value == 0);
    reads = mock_adc_mmio_reads; queues = mock_queue_calls;
    sample(3);
    CHECK(mock_adc_mmio_reads == reads && mock_queue_calls == queues);
    writes = mock_adc_writes;
    sticks_pm_event(NULL, post, NULL);
    CHECK(!suspended);
    sample(3);
    CHECK(mock_input.absinfo[ABS_X].value == 0);
    if (negative) CHECK(mock_adc_writes == writes);
    else CHECK(mock_adc_writes > writes);
    mock_raw[3] = 2048; sample(3);
    CHECK(neutral_gate.armed_mask == 3);
    mock_raw[3] = 0; sample(1);
    CHECK(mock_input.absinfo[ABS_X].value == 32767);
    finish();
}

static void test_bounded_fault(void)
{
    int writes, base_logs, adc_writes, i;
    unsigned long previous = 0;
    start("rg35xxh"); arm();
    writes = mock_writes; adc_writes = mock_adc_writes; base_logs = (int)mock_log_calls;
    mock_adc_ctrl_read_clear_mask = BIT(16); /* Model a register which will not stay enabled. */
    sample(550); /* 5.5 seconds with healthy 10ms digital polling. */
    CHECK(mock_adc_writes > adc_writes && mock_adc_writes <= adc_writes + 3 * 8);
    CHECK(mock_writes - writes == mock_adc_writes - adc_writes);
    CHECK(mock_ccu_writes == 0 && mock_last_delay <= 10);
    for (i = adc_writes; i < mock_adc_writes; i++) {
        unsigned long now = mock_adc_write_times[i];
        if (i != adc_writes && now != previous) CHECK(now - previous >= 1000);
        previous = now;
    }
    for (i = base_logs + 1; i < (int)mock_log_calls; i++)
        CHECK(mock_log_times[i] - mock_log_times[i - 1] >= 1000);
    CHECK((int)mock_log_calls - base_logs <= 7);
    CHECK(mock_input.absinfo[ABS_X].value == 0);
    writes = mock_adc_writes;
    sample(500);
    CHECK(mock_adc_writes == writes); /* Exhausted failure budget stays read-only. */
    mock_gpio_levels[136] = 0; sample(2);
    CHECK(mock_key_events[BTN_THUMBL] == 1);
    mock_adc_ctrl_read_clear_mask = 0;
    mock_gpio_levels[136] = 1;
    sample(110);
    CHECK(neutral_gate.armed_mask == 3);
    finish();
}

static void test_refuse_unrelated(unsigned int kind)
{
    int writes, saved_requested;
    start("rg35xxh"); arm();
    mock_adc[1] = BIT(16) | BIT(8);
    saved_requested = requested;
    if (kind == 0) mock_adc[2] = 2;
    if (kind == 1) mock_adc_available = 1;
    if (kind == 2) mock_adc_node = 0;
    if (kind == 3) requested--;
    writes = mock_writes;
    sample(220);
    CHECK(mock_writes == writes && mock_ccu_writes == 0);
    CHECK(mock_input.absinfo[ABS_X].value == 0);
    mock_gpio_levels[136] = 0; sample(2);
    CHECK(mock_key_events[BTN_THUMBL] == 1);
    requested = saved_requested;
    finish();
}

static void test_unstable_success(void)
{
    int writes, i;
    start("rg35xxh"); arm();
    writes = mock_adc_writes;
    for (i = 0; i < 1100; i++) {
        /* Each configuration reads back correctly, then an external reset
         * removes EN before the next ordinary 10ms poll. */
        mock_adc[1] &= ~BIT(16);
        sample(1);
    }
    CHECK(mock_adc_writes == writes + 3 * 8);
    writes = mock_adc_writes;
    sample(500);
    CHECK(mock_adc_writes == writes);
    mock_gpio_levels[136] = 0; sample(2);
    CHECK(mock_key_events[BTN_THUMBL]);
    mock_adc[1] = 0x10200;
    mock_gpio_levels[136] = 1;
    sample(120); /* External stable-ready state can leave quarantine. */
    CHECK(neutral_gate.armed_mask == 3 && mock_adc_writes == writes);
    mock_adc[1] &= ~BIT(16); sample(110);
    CHECK(mock_adc_writes > writes); /* Fresh stable epoch has a fresh budget. */
    finish();
}

static void test_exit_refuses_owner(unsigned int kind)
{
    int writes, reads;
    start("rg35xxh"); arm();
    if (kind == 0) { mock_adc[1] = BIT(16) | BIT(8); mock_adc[2] = 2; }
    if (kind == 1) mock_adc_available = 1;
    if (kind == 2) mock_ccu[0x9ec / 4] = 0;
    writes = mock_adc_writes; reads = mock_adc_mmio_reads;
    sticks_exit();
    CHECK(mock_adc_writes == writes && mock_ccu_writes == 0);
    if (kind == 2) CHECK(mock_adc_mmio_reads == reads);
    CHECK(!active && !prepared && !handle.dev);
    CHECK(mock_maps == mock_unmaps && mock_pm_registered == 0);
}

static void test_no_sticks(const char *model)
{
    fixture(model);
    mock_compatible = 0; mock_adc_available = 1;
    CHECK(sticks_init() == 0); sticks_exit();
    CHECK(mock_maps == 0 && mock_writes == 0 && mock_gpio_requests == 0);
    CHECK(mock_adc_mmio_reads == 0 && mock_gpio_reads[136] == 0 && mock_gpio_reads[137] == 0);
    CHECK(!handle.dev && mock_pm_registered == 0);
}

static void test_single(void)
{
    int before[4];
    start("rg40xxv"); arm();
    CHECK(requested == 4 && !mock_gpio_owned[137]);
    memcpy(before, mock_channel_reads, sizeof(before));
    mock_raw[0] = mock_raw[1] = 4095; sample(20);
    CHECK(mock_channel_reads[0] == before[0] && mock_channel_reads[1] == before[1]);
    CHECK(mock_gpio_reads[137] == 0 && mock_key_reports[BTN_THUMBR] == 0);
    CHECK(mock_abs_events[ABS_Z] == 0 && mock_abs_events[ABS_RUDDER] == 0);
    mock_adc[1] &= ~BIT(16); sample(110);
    CHECK(neutral_gate.armed_mask == 1);
    CHECK(mock_channel_reads[0] == before[0] && mock_channel_reads[1] == before[1]);
    CHECK(mock_gpio_reads[137] == 0);
    finish();
}

int main(int argc, char **argv)
{
    const char *name;
    CHECK(argc == 2 || argc == 3);
    name = argv[1];
    if (!strcmp(name, "healthy")) { CHECK(argc == 3); test_healthy(argv[2]); }
    else if (!strcmp(name, "adc-fault-clicks")) test_clicks_during_fault(0, 0);
    else if (!strcmp(name, "ccu-fault-clicks")) test_clicks_during_fault(1, 0);
    else if (!strcmp(name, "recover-disabled")) test_recovery(0, 0);
    else if (!strcmp(name, "recover-mode")) test_recovery(1, 0);
    else if (!strcmp(name, "recover-selection")) test_recovery(2, 0);
    else if (!strcmp(name, "pm-hibernation")) test_real_pm(1, 2, 0);
    else if (!strcmp(name, "pm-suspend")) test_real_pm(3, 4, 0);
    else if (!strcmp(name, "pm-restore")) test_real_pm(5, 6, 0);
    else if (!strcmp(name, "bounded-fault")) test_bounded_fault();
    else if (!strcmp(name, "refuse-selection")) test_refuse_unrelated(0);
    else if (!strcmp(name, "refuse-adc-owner")) test_refuse_unrelated(1);
    else if (!strcmp(name, "refuse-missing-node")) test_refuse_unrelated(2);
    else if (!strcmp(name, "refuse-lost-claims")) test_refuse_unrelated(3);
    else if (!strcmp(name, "unstable-success-budget")) test_unstable_success();
    else if (!strcmp(name, "exit-unrelated-selection")) test_exit_refuses_owner(0);
    else if (!strcmp(name, "exit-unrelated-driver")) test_exit_refuses_owner(1);
    else if (!strcmp(name, "exit-clock-off")) test_exit_refuses_owner(2);
    else if (!strcmp(name, "no-sticks")) { CHECK(argc == 3); test_no_sticks(argv[2]); }
    else if (!strcmp(name, "single")) test_single();
    else if (!strcmp(name, "legacy-adc-click-blocked")) test_clicks_during_fault(0, 1);
    else if (!strcmp(name, "legacy-ccu-click-blocked")) test_clicks_during_fault(1, 1);
    else if (!strcmp(name, "legacy-control-not-restored")) test_recovery(0, 1);
    else if (!strcmp(name, "legacy-selection-unchecked")) test_recovery(2, 1);
    else if (!strcmp(name, "legacy-post-no-reconfigure")) test_real_pm(3, 4, 1);
    else CHECK(0);
    printf("PASS %s / %u checks; actual C, hardware mocked\n", name, checks);
    return 0;
}

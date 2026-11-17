/* Executes the actual candidate translation unit against a host API boundary. */
#define H700_HOST_TEST 1
#include "h700_stick_axes.c"
#include <assert.h>
#include <stdlib.h>

struct input_handle *h700_test_current_handle(void) { return &handle; }
static unsigned int checks, scenarios;
#define CHECK(expression) do { checks++; if (!(expression)) { \
    fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #expression); exit(1); \
} } while (0)

static void reset_mock(void)
{
    unsigned int i;
    memset(mock_adc, 0, sizeof(mock_adc));
    memset(mock_pio, 0, sizeof(mock_pio));
    memset(mock_ccu, 0, sizeof(mock_ccu));
    memset(mock_gpio_levels, 0, sizeof(mock_gpio_levels));
    memset(mock_gpio_owned, 0, sizeof(mock_gpio_owned));
    memset(mock_absinfo, 0, sizeof(mock_absinfo));
    memset(mock_abs_events, 0, sizeof(mock_abs_events));
    memset(mock_key_events, 0, sizeof(mock_key_events));
    memset(&mock_input, 0, sizeof(mock_input));
    memset(&handle, 0, sizeof(handle));
    memset(old_abs, 0, sizeof(old_abs));
    memset(center, 0, sizeof(center));
    memset(click_candidate, 0, sizeof(click_candidate));
    memset(click_count, 0, sizeof(click_count));
    memset(click_state, 0, sizeof(click_state));
    memset(last_raw, 0, sizeof(last_raw));
    mock_input.name = "ANBERNIC-keys";
    mock_input.absinfo = mock_absinfo;
    __set_bit(ABS_HAT0X, mock_input.absbit);
    __set_bit(ABS_HAT0Y, mock_input.absbit);
    __set_bit(ABS_RX, mock_input.absbit);
    __set_bit(BTN_SOUTH, mock_input.keybit);
    mock_absinfo[ABS_RX].minimum = -1;
    mock_absinfo[ABS_RX].maximum = 1;
    mock_gpio_levels[136] = mock_gpio_levels[137] = 1;
    for (i = 0; i < 4; i++) mock_raw[i] = 2048;
    for (i = 0; i < 7; i++) mock_adc[registers[i] / 4] = 0xabc00000u + i;
    mock_pio[0x120 / 4] = 0x12345678;
    mock_pio[0x130 / 4] = 0x12345675;
    mock_pio[0x94 / 4] = 0x87654321;
    mock_pio[0xac / 4] = 0x12345678;
    mock_ccu[0x9ec / 4] = 0x10001;
    mock_gpio_fail_at = -1;
    mock_gpio_requests = mock_gpio_frees = 0;
    mock_maps = mock_unmaps = mock_writes = mock_adc_reads = 0;
    mock_queue_calls = mock_cancel_calls = mock_handle_result = 0;
    mock_last_delay = 10; mock_log_calls = mock_gpio_sets = 0;
    jiffies = poll_count = raw_jiffies = next_diagnostic = last_diagnostic = 0;
    last_clicks = last_ctrl = last_ccu = 0;
    raw_valid = diagnostic_started = diagnostic_gated = false;
    diagnostic_ever_logged = diagnostic_recovery_pending = false;
    hardware_reason = "not-sampled";
    mock_handler_result = mock_notifier_result = mock_pm_registered = 0;
    mock_compatible = mock_adc_node = mock_chip_available = 1;
    mock_adc_available = mock_syncs = 0;
    old_abs_bits = old_key_bits = 0;
    gpio_base = requested = 0;
    prepared = active = suspended = handler_registered = notifier_registered = false;
    hardware_blocked = false;
    adc = pio = ccu = NULL;
    profile = NULL; selected = NULL; probe_only = false;
    h700_reset_neutral_gate(&neutral_gate);
}

static void sample(unsigned int count)
{
    unsigned int i;
    for (i = 0; i < count; i++) {
        poll_sticks(NULL);
        jiffies += mock_last_delay;
    }
}

static void expect_restored(void)
{
    unsigned int i;
    CHECK(!active && !prepared && requested == 0);
    CHECK(mock_pm_registered == 0);
    CHECK(mock_maps == mock_unmaps);
    for (i = 0; i < 7; i++) CHECK(mock_adc[registers[i] / 4] == 0xabc00000u + i);
    CHECK(mock_pio[0x120 / 4] == 0x12345678);
    CHECK(mock_pio[0x94 / 4] == 0x87654321);
    CHECK(mock_pio[0xac / 4] == 0x12345678);
    for (i = 0; i < 5; i++) CHECK(!mock_gpio_owned[pins[i]]);
    CHECK(test_bit(ABS_RX, mock_input.absbit));
    CHECK(test_bit(BTN_SOUTH, mock_input.keybit));
}

static void test_catalog(void)
{
    unsigned int i, zero = 0, one = 0, two = 0;
    scenarios++;
    CHECK(sizeof(h700_stick_profiles) / sizeof(h700_stick_profiles[0]) == 12);
    CHECK(!h700_profile_lookup(NULL));
    CHECK(!h700_profile_lookup("rg35xxh\n"));
    CHECK(!h700_profile_lookup("RG35XXH"));
    CHECK(!h700_profile_lookup("35XX H"));
    for (i = 0; i < 12; i++) {
        const struct h700_stick_profile *p = &h700_stick_profiles[i];
        CHECK(h700_profile_lookup(p->model) == p);
        CHECK(h700_profile_axis_count(p) == p->sticks * 2);
        if (!p->sticks) zero++;
        else if (p->sticks == 1) one++;
        else if (p->sticks == 2) two++;
        else CHECK(0);
    }
    CHECK(zero == 6 && one == 1 && two == 5);
    CHECK(h700_profile_lookup("rg40xxv")->click_mask == 1);
}

static void test_no_stick_no_io(void)
{
    unsigned int i;
    scenarios++;
    for (i = 0; i < 12; i++) {
        if (h700_stick_profiles[i].sticks) continue;
        reset_mock();
        profile = (char *)h700_stick_profiles[i].model;
        mock_compatible = 0; mock_adc_available = 1;
        CHECK(sticks_init() == 0);
        sticks_exit();
        CHECK(mock_maps == 0 && mock_writes == 0 && mock_gpio_requests == 0);
        CHECK(mock_adc_reads == 0 && !handle.dev && mock_pm_registered == 0);
    }
    reset_mock(); profile = "unlisted";
    CHECK(sticks_init() == -EINVAL && mock_maps == 0);
}

static void test_ownership_guards(void)
{
    int which;
    scenarios++;
    for (which = 0; which < 4; which++) {
        reset_mock(); profile = "rg35xxh";
        if (which == 0) mock_compatible = 0;
        if (which == 1) mock_adc_node = 0;
        if (which == 2) mock_adc_available = 1;
        if (which == 3) probe_only = true;
        CHECK(sticks_init() == (which == 2 ? -EBUSY : which == 3 ? 0 : -ENODEV));
        CHECK(mock_maps == 0 && mock_gpio_requests == 0 && mock_writes == 0);
    }
    reset_mock(); profile = "rg35xxh"; mock_ccu[0x9ec / 4] = 0;
    CHECK(sticks_init() == -ENODEV);
    CHECK(mock_gpio_requests == 0 && mock_maps == mock_unmaps);
    reset_mock(); profile = "rg35xxh"; mock_input.name = "unrelated-controller";
    CHECK(sticks_init() == -ENODEV); expect_restored();
}

static void test_gpio_partial_failures(void)
{
    int i;
    scenarios++;
    for (i = 0; i < 5; i++) {
        reset_mock(); profile = "rg35xxh"; mock_gpio_fail_at = i;
        CHECK(sticks_init() == -EBUSY);
        CHECK(mock_gpio_frees == i);
        expect_restored();
    }
}

static void test_center_and_axis_collision(void)
{
    int i;
    scenarios++;
    for (i = 0; i < 4; i++) {
        reset_mock(); profile = "rg35xxh"; mock_raw[i] = 4095;
        CHECK(sticks_init() == -EINVAL); expect_restored();
    }
    reset_mock(); profile = "rg35xxh"; __set_bit(ABS_Z, mock_input.absbit);
    CHECK(sticks_init() == -ENODEV);
    CHECK(test_bit(ABS_Z, mock_input.absbit)); expect_restored();
}

static void test_dual_profiles_and_restore(void)
{
    const char *models[2] = {"rg34xxsp", "rg35xxh"};
    unsigned int m, i;
    scenarios++;
    for (m = 0; m < 2; m++) {
        reset_mock(); profile = (char *)models[m];
        CHECK(sticks_init() == 0);
        CHECK(requested == 5 && mock_adc_reads == 96 && mock_pm_registered == 1);
        sample(3); CHECK(neutral_gate.armed_mask == 3);
        for (i = 0; i < 4; i++) {
            mock_raw[channels[i]] = 0;
            sample(1);
            CHECK(mock_input.absinfo[axes[i]].value ==
                  ((selected->invert_mask & BIT(i)) ? 32767 : -32767));
            mock_raw[channels[i]] = 4095;
            sample(1);
            CHECK(mock_input.absinfo[axes[i]].value ==
                  ((selected->invert_mask & BIT(i)) ? -32767 : 32767));
            mock_raw[channels[i]] = 2048;
        }
        CHECK(mock_input.absinfo[ABS_RX].minimum == -1);
        CHECK(mock_input.absinfo[ABS_RX].maximum == 1);
        mock_gpio_levels[136] = 0;
        sample(1); CHECK(mock_key_events[BTN_THUMBL] == 0);
        sample(1); CHECK(mock_key_events[BTN_THUMBL] == 1);
        mock_gpio_levels[136] = 1;
        sample(2); CHECK(mock_key_events[BTN_THUMBL] == 0);
        sticks_exit(); expect_restored();
        for (i = 0; i < 4; i++) CHECK(!test_bit(axes[i], mock_input.absbit));
        CHECK(!test_bit(BTN_THUMBL, mock_input.keybit));
        CHECK(!test_bit(BTN_THUMBR, mock_input.keybit));
    }
}

static void test_resume_neutral_gate(void)
{
    int reads, queues;
    scenarios++;
    reset_mock(); profile = "rg35xxh";
    CHECK(sticks_init() == 0); sample(3);
    mock_raw[3] = 0; sample(1);
    CHECK(mock_input.absinfo[ABS_X].value == 32767);
    sticks_pm_event(NULL, PM_SUSPEND_PREPARE, NULL);
    CHECK(suspended && !neutral_gate.armed_mask);
    CHECK(mock_input.absinfo[ABS_X].value == 0);
    reads = mock_adc_reads; queues = mock_queue_calls;
    sample(2); CHECK(mock_adc_reads == reads && mock_queue_calls == queues);
    sticks_pm_event(NULL, PM_POST_SUSPEND, NULL);
    CHECK(!suspended);
    sample(10); CHECK(mock_input.absinfo[ABS_X].value == 0);
    CHECK(neutral_gate.armed_mask == 2); /* The independent right stick rearmed. */
    mock_raw[1] = 0;
    sample(1); CHECK(mock_input.absinfo[ABS_Z].value == -32767);
    mock_raw[1] = 2048;
    mock_raw[3] = 2048; mock_gpio_levels[136] = 0;
    sample(3); CHECK(neutral_gate.armed_mask == 3);
    mock_gpio_levels[136] = 1;
    sample(2); CHECK(neutral_gate.armed_mask == 3);
    mock_raw[3] = 4095; sample(1);
    CHECK(mock_input.absinfo[ABS_X].value == -32767);
    mock_ccu[0x9ec / 4] = 0;
    queues = mock_queue_calls; sample(1);
    CHECK(!suspended && hardware_blocked && mock_input.absinfo[ABS_X].value == 0);
    CHECK(mock_queue_calls == queues + 1 && mock_last_delay == 100);
    mock_ccu[0x9ec / 4] = 0x10001;
    sticks_exit(); expect_restored();
}

static void test_independent_stick_gates(void)
{
    scenarios++;
    reset_mock(); profile = "rg35xxh"; CHECK(sticks_init() == 0);
    mock_raw[3] = 0; /* Left stick held after calibration, before first poll. */
    sample(3); CHECK(neutral_gate.armed_mask == 2);
    mock_raw[1] = 4095; sample(1);
    CHECK(mock_input.absinfo[ABS_Z].value == 32767);
    CHECK(mock_input.absinfo[ABS_X].value == 0);
    mock_raw[3] = 2048; sample(3);
    CHECK(neutral_gate.armed_mask == 3);
    mock_raw[3] = 4095; sample(1);
    CHECK(mock_input.absinfo[ABS_X].value == -32767);
    sticks_exit(); expect_restored();
}

static void test_clicks_do_not_block_motion(void)
{
    scenarios++;
    reset_mock(); profile = "rg35xxh"; CHECK(sticks_init() == 0);
    mock_gpio_levels[136] = mock_gpio_levels[137] = 0;
    sample(3); CHECK(neutral_gate.armed_mask == 3);
    CHECK(neutral_gate.click_released_mask == 0);
    mock_raw[3] = 0; mock_raw[1] = 0; sample(3);
    CHECK(mock_input.absinfo[ABS_X].value == 32767);
    CHECK(mock_input.absinfo[ABS_Z].value == -32767);
    CHECK(!mock_key_events[BTN_THUMBL] && !mock_key_events[BTN_THUMBR]);
    mock_gpio_levels[136] = 1; sample(3);
    CHECK(neutral_gate.click_released_mask == 1);
    mock_gpio_levels[136] = 0; sample(2);
    CHECK(mock_key_events[BTN_THUMBL] && !mock_key_events[BTN_THUMBR]);
    mock_gpio_levels[137] = 1; sample(3);
    mock_gpio_levels[137] = 0; sample(2);
    CHECK(mock_key_events[BTN_THUMBR]);
    sticks_pm_event(NULL, PM_SUSPEND_PREPARE, NULL);
    sticks_pm_event(NULL, PM_POST_SUSPEND, NULL);
    mock_raw[3] = mock_raw[1] = 2048; sample(3);
    CHECK(neutral_gate.armed_mask == 3 && neutral_gate.click_released_mask == 0);
    CHECK(!mock_key_events[BTN_THUMBL] && !mock_key_events[BTN_THUMBR]);
    mock_raw[3] = 0; sample(1); CHECK(mock_input.absinfo[ABS_X].value == 32767);
    sticks_exit(); expect_restored();
}

static void test_flat_tolerance_and_jitter(void)
{
    struct h700_neutral_gate gate;
    int values[4] = {-4096, 4096, 4096, -4096};
    int i;
    scenarios++;
    h700_reset_neutral_gate(&gate);
    for (i = 0; i < 2; i++) {
        CHECK(h700_observe_neutral(&gate, values, 4, 3, 3) == 0);
        values[0] = -values[0]; values[3] = -values[3];
    }
    CHECK(h700_observe_neutral(&gate, values, 4, 3, 3) == 3);
    CHECK(gate.click_released_mask == 0);
    h700_reset_neutral_gate(&gate);
    values[0] = 4097;
    for (i = 0; i < 10; i++)
        CHECK(h700_observe_neutral(&gate, values, 4, 0, 3) == (i < 2 ? 0 : 2));
    CHECK(gate.consecutive[0] == 0 && gate.armed_mask == 2);
    /* Actual driver sampling accepts small nonzero raw jitter inside flat. */
    reset_mock(); profile = "rg35xxh"; CHECK(sticks_init() == 0);
    for (i = 0; i < 3; i++) {
        mock_raw[3] = i & 1 ? 2260 : 1836;
        mock_raw[2] = i & 1 ? 1836 : 2260;
        sample(1);
    }
    CHECK(neutral_gate.armed_mask == 3);
    mock_raw[3] = 0; sample(1); CHECK(mock_input.absinfo[ABS_X].value == 32767);
    sticks_exit(); expect_restored();
}

static void test_hardware_fault_and_recovery(void)
{
    int writes, gpio_sets, reads, logs;
    unsigned int fault;
    scenarios++;
    for (fault = 0; fault < 2; fault++) {
        u32 desired_ctrl;
        reset_mock(); profile = "rg35xxh"; CHECK(sticks_init() == 0);
        sample(3); mock_raw[3] = 0; sample(1);
        CHECK(mock_input.absinfo[ABS_X].value == 32767);
        desired_ctrl = mock_adc[4 / 4];
        if (!fault) mock_ccu[0x9ec / 4] = 0;
        else mock_adc[4 / 4] &= ~0x10000u;
        jiffies += 1000; /* Permit the first fault diagnostic after startup. */
        writes = mock_writes; gpio_sets = mock_gpio_sets; reads = mock_adc_reads;
        sample(1);
        CHECK(hardware_blocked && !suspended && mock_last_delay == 100);
        CHECK(!neutral_gate.armed_mask && mock_input.absinfo[ABS_X].value == 0);
        logs = mock_log_calls;
        sample(49); CHECK(mock_log_calls == (unsigned int)logs);
        CHECK(mock_writes == writes && mock_gpio_sets == (unsigned int)gpio_sets);
        CHECK(mock_adc_reads == reads);
        sample(1); CHECK(mock_log_calls == (unsigned int)logs + 1);
        CHECK(strstr(mock_log, fault ? "reason=adc-control" : "reason=clock-reset"));
        CHECK(strstr(mock_log, "polls=") && strstr(mock_log, "raw_age_ms="));
        sample(1000); /* 100 seconds failed: keep neutral; never seize registers. */
        CHECK(hardware_blocked && mock_writes == writes);
        CHECK(mock_gpio_sets == (unsigned int)gpio_sets && mock_adc_reads == reads);
        /* Simulate the existing owner restoring valid state, never this driver. */
        mock_ccu[0x9ec / 4] = 0x10001;
        mock_adc[4 / 4] = desired_ctrl;
        jiffies += 1000; /* Transition logging has a global one-second cap. */
        sample(1); CHECK(!hardware_blocked && mock_last_delay == 10);
        CHECK(mock_writes == writes && neutral_gate.armed_mask == 0);
        CHECK(strstr(mock_log, "reason=hardware-restored"));
        sample(3); CHECK(neutral_gate.armed_mask == 2); /* Left remains held. */
        mock_raw[3] = 2048; sample(3); CHECK(neutral_gate.armed_mask == 3);
        mock_raw[3] = 4095; sample(1);
        CHECK(mock_input.absinfo[ABS_X].value == -32767);
        sticks_exit(); expect_restored();
    }
}

static void test_diagnostic_rate_and_healthy_quiet(void)
{
    unsigned int logs;
    scenarios++;
    reset_mock(); profile = "rg35xxh"; CHECK(sticks_init() == 0);
    mock_raw[3] = 0; sample(1);
    CHECK(strstr(mock_log, "reason=neutral-gate"));
    CHECK(strstr(mock_log, "model=rg35xxh") && strstr(mock_log, "ctrl=0x"));
    logs = mock_log_calls;
    sample(499); CHECK(mock_log_calls == logs);
    sample(1); CHECK(mock_log_calls == logs + 1);
    CHECK(strstr(mock_log, "armed=0x2"));
    mock_raw[3] = 2048; sample(3);
    sample(100); /* Recovery transition is globally rate-limited. */
    CHECK(strstr(mock_log, "reason=ready"));
    logs = mock_log_calls;
    sample(5800); CHECK(mock_log_calls == logs);
    sample(200); CHECK(mock_log_calls == logs + 1); /* Healthy heartbeat <= 1/minute. */
    CHECK(strstr(mock_log, "reason=ready"));
    sticks_exit(); expect_restored();
}

static void test_single_stick_pm_and_fault(void)
{
    int reads, writes;
    scenarios++;
    reset_mock(); profile = "rg40xxv"; CHECK(sticks_init() == 0); sample(3);
    sticks_pm_event(NULL, PM_SUSPEND_PREPARE, NULL);
    mock_raw[3] = 0; mock_raw[0] = mock_raw[1] = 4095;
    mock_gpio_levels[136] = 0;
    sticks_pm_event(NULL, PM_POST_SUSPEND, NULL);
    reads = mock_adc_reads;
    sample(10); CHECK(mock_adc_reads == reads + 20);
    CHECK(neutral_gate.armed_mask == 0 && mock_input.absinfo[ABS_X].value == 0);
    CHECK(!mock_key_events[BTN_THUMBL]);
    mock_raw[3] = 2048; sample(3);
    CHECK(neutral_gate.armed_mask == 1 && neutral_gate.click_released_mask == 0);
    mock_raw[3] = 4095; sample(1);
    CHECK(mock_input.absinfo[ABS_X].value == -32767);
    CHECK(mock_abs_events[ABS_Z] == 0 && mock_abs_events[ABS_RUDDER] == 0);
    reads = mock_adc_reads; writes = mock_writes;
    mock_ccu[0x9ec / 4] = 0; sample(15);
    CHECK(hardware_blocked && mock_adc_reads == reads && mock_writes == writes);
    mock_ccu[0x9ec / 4] = 0x10001;
    mock_raw[3] = 2048; sample(3);
    CHECK(!hardware_blocked && neutral_gate.armed_mask == 1);
    CHECK(!mock_gpio_owned[137]);
    sticks_exit(); expect_restored();
}

static void test_flapping_diagnostic_bound(void)
{
    unsigned int i, previous_logs;
    unsigned long previous_time;
    scenarios++;
    reset_mock(); profile = "rg35xxh"; CHECK(sticks_init() == 0);
    sample(1);
    previous_logs = mock_log_calls;
    previous_time = last_diagnostic;
    for (i = 0; i < 400; i++) {
        mock_ccu[0x9ec / 4] = i & 1 ? 0x10001 : 0;
        poll_sticks(NULL);
        if (mock_log_calls != previous_logs) {
            CHECK(mock_log_calls == previous_logs + 1);
            CHECK(last_diagnostic - previous_time >= 1000);
            previous_time = last_diagnostic;
            previous_logs = mock_log_calls;
        }
        jiffies += mock_last_delay;
    }
    CHECK(mock_log_calls <= 25); /* ~22 seconds of rapid state transitions. */
    mock_ccu[0x9ec / 4] = 0x10001; sample(110);
    CHECK(!hardware_blocked && neutral_gate.armed_mask == 3);
    CHECK(!diagnostic_recovery_pending);
    sticks_exit(); expect_restored();
}

static void test_click_release_glitch(void)
{
    scenarios++;
    reset_mock(); profile = "rg35xxh"; CHECK(sticks_init() == 0);
    mock_gpio_levels[136] = mock_gpio_levels[137] = 0;
    sample(3); CHECK(neutral_gate.armed_mask == 3);
    mock_gpio_levels[136] = 1; sample(1); /* One high glitch, then held low. */
    CHECK(!neutral_gate.click_released_mask);
    mock_gpio_levels[136] = 0; sample(10);
    CHECK(!neutral_gate.click_released_mask && !mock_key_events[BTN_THUMBL]);
    mock_raw[3] = 0; sample(1); CHECK(mock_input.absinfo[ABS_X].value == 32767);
    mock_gpio_levels[136] = 1; sample(2);
    CHECK(!neutral_gate.click_released_mask);
    sample(1); CHECK(neutral_gate.click_released_mask == 1);
    mock_gpio_levels[136] = 0; sample(2); CHECK(mock_key_events[BTN_THUMBL]);
    CHECK(!mock_key_events[BTN_THUMBR]);
    sticks_pm_event(NULL, PM_SUSPEND_PREPARE, NULL);
    sticks_pm_event(NULL, PM_POST_SUSPEND, NULL);
    mock_gpio_levels[136] = 1; sample(1);
    mock_gpio_levels[136] = 0; sample(10);
    CHECK(!neutral_gate.click_released_mask && !mock_key_events[BTN_THUMBL]);
    sticks_exit(); expect_restored();
}

static void test_single_stick_path(void)
{
    scenarios++;
    reset_mock(); profile = "rg40xxv";
    CHECK(sticks_init() == 0);
    CHECK(requested == 4 && mock_adc_reads == 48);
    CHECK(!mock_gpio_owned[137]);
    CHECK(test_bit(ABS_X, mock_input.absbit) && test_bit(ABS_Y, mock_input.absbit));
    CHECK(!test_bit(ABS_Z, mock_input.absbit) && !test_bit(ABS_RUDDER, mock_input.absbit));
    CHECK(test_bit(BTN_THUMBL, mock_input.keybit) && !test_bit(BTN_THUMBR, mock_input.keybit));
    sample(3); mock_raw[1] = 0; sample(1);
    CHECK(mock_abs_events[ABS_Z] == 0 && mock_abs_events[ABS_RUDDER] == 0);
    sticks_exit(); expect_restored();
}

static void test_every_stick_profile_and_math(void)
{
    unsigned int m, i;
    scenarios++;
    for (m = 0; m < 12; m++) {
        const struct h700_stick_profile *p = &h700_stick_profiles[m];
        if (!p->sticks) continue;
        reset_mock(); profile = (char *)p->model;
        CHECK(sticks_init() == 0);
        CHECK(mock_adc_reads == (int)(24 * h700_profile_axis_count(p)));
        CHECK(requested == (int)(3 + p->sticks));
        CHECK(selected == p);
        for (i = 0; i < h700_profile_axis_count(p); i++) {
            int raw, previous = (p->invert_mask & BIT(i)) ? 32767 : -32767;
            for (raw = 0; raw <= 4095; raw++) {
                int value = h700_profile_axis_sign(p, i, h700_axis_value(raw, 2048));
                CHECK(value >= -32767 && value <= 32767);
                CHECK((p->invert_mask & BIT(i)) ? value <= previous : value >= previous);
                if (raw >= 2016 && raw <= 2080) CHECK(value == 0);
                previous = value;
            }
        }
        sticks_exit(); expect_restored();
    }
}

static void test_registration_failures(void)
{
    int i;
    scenarios++;
    for (i = 0; i < 3; i++) {
        reset_mock(); profile = "rg35xxh";
        if (i == 0) mock_notifier_result = -ENOMEM;
        if (i == 1) mock_handler_result = -ENOMEM;
        if (i == 2) mock_handle_result = -ENOMEM;
        CHECK(sticks_init() == (i == 2 ? -ENODEV : -ENOMEM));
        expect_restored();
    }
}

int main(void)
{
    test_catalog(); test_no_stick_no_io(); test_ownership_guards();
    test_gpio_partial_failures(); test_center_and_axis_collision();
    test_dual_profiles_and_restore(); test_resume_neutral_gate();
    test_independent_stick_gates(); test_clicks_do_not_block_motion();
    test_flat_tolerance_and_jitter(); test_hardware_fault_and_recovery();
    test_diagnostic_rate_and_healthy_quiet();
    test_single_stick_pm_and_fault(); test_flapping_diagnostic_bound();
    test_click_release_glitch();
    test_single_stick_path(); test_registration_failures();
    test_every_stick_profile_and_math();
    printf("PASS: actual candidate C, %u scenarios / %u checks; hardware APIs mocked\n", scenarios, checks);
    return 0;
}

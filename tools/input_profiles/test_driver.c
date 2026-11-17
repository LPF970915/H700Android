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
    mock_handler_result = mock_notifier_result = mock_pm_registered = 0;
    mock_compatible = mock_adc_node = mock_chip_available = 1;
    mock_adc_available = mock_syncs = 0;
    old_abs_bits = old_key_bits = 0;
    gpio_base = requested = 0;
    prepared = active = suspended = handler_registered = notifier_registered = false;
    adc = pio = ccu = NULL;
    profile = NULL; selected = NULL; probe_only = false;
    h700_reset_neutral_gate(&neutral_gate);
}

static void sample(unsigned int count)
{
    unsigned int i;
    for (i = 0; i < count; i++) poll_sticks(NULL);
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
        sample(3); CHECK(neutral_gate.armed);
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
    CHECK(suspended && !neutral_gate.armed);
    CHECK(mock_input.absinfo[ABS_X].value == 0);
    reads = mock_adc_reads; queues = mock_queue_calls;
    sample(2); CHECK(mock_adc_reads == reads && mock_queue_calls == queues);
    sticks_pm_event(NULL, PM_POST_SUSPEND, NULL);
    CHECK(!suspended);
    sample(10); CHECK(mock_input.absinfo[ABS_X].value == 0 && !neutral_gate.armed);
    mock_raw[3] = 2048; mock_gpio_levels[136] = 0;
    sample(10); CHECK(!neutral_gate.armed);
    mock_gpio_levels[136] = 1;
    sample(2); CHECK(!neutral_gate.armed);
    sample(1); CHECK(neutral_gate.armed);
    mock_raw[3] = 4095; sample(1);
    CHECK(mock_input.absinfo[ABS_X].value == -32767);
    mock_ccu[0x9ec / 4] = 0;
    queues = mock_queue_calls; sample(1);
    CHECK(suspended && mock_input.absinfo[ABS_X].value == 0);
    CHECK(mock_queue_calls == queues);
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
    test_single_stick_path(); test_registration_failures();
    test_every_stick_profile_and_math();
    printf("PASS: actual candidate C, %u scenarios / %u checks; hardware APIs mocked\n", scenarios, checks);
    return 0;
}

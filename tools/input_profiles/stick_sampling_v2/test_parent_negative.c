/* Execute the frozen Test8 driver and its own real test boundary. These are
 * negative controls reproducing old software blockers, not hardware claims. */
#define main h700_parent_test_main
#include "../test_driver.c"
#undef main

int main(void)
{
    int reads, queues;
    reset_mock(); profile = "rg35xxh"; CHECK(sticks_init() == 0);
    mock_raw[3] = 0; sample(3); mock_raw[1] = 4095; sample(1);
    CHECK(!neutral_gate.armed && mock_input.absinfo[ABS_Z].value == 0);
    sticks_exit(); expect_restored();

    reset_mock(); profile = "rg35xxh"; CHECK(sticks_init() == 0);
    mock_raw[3] = 2260; mock_raw[2] = 1836; sample(10);
    CHECK(!neutral_gate.armed && mock_input.absinfo[ABS_X].value == 0);
    sticks_exit(); expect_restored();

    reset_mock(); profile = "rg35xxh"; CHECK(sticks_init() == 0);
    mock_gpio_levels[136] = mock_gpio_levels[137] = 0;
    sample(3); mock_raw[3] = 0; sample(1);
    CHECK(!neutral_gate.armed && mock_input.absinfo[ABS_X].value == 0);
    sticks_exit(); expect_restored();

    reset_mock(); profile = "rg35xxh"; CHECK(sticks_init() == 0); sample(3);
    queues = mock_queue_calls;
    mock_ccu[0x9ec / 4] = 0; sample(1);
    CHECK(suspended && mock_queue_calls == queues);
    mock_ccu[0x9ec / 4] = 0x10001;
    reads = mock_adc_reads; sample(10);
    CHECK(suspended && mock_adc_reads == reads && mock_queue_calls == queues);
    sticks_exit(); expect_restored();
    printf("PASS: frozen Test8 actual C reproduced 4 software blockers / %u checks; hardware APIs mocked\n", checks);
    return 0;
}

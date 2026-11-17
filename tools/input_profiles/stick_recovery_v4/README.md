# H700 isolated actual-CTRL recovery candidate

This candidate starts from frozen `stick_recovery_v3`, the Test10 module.
`parent-inputs.json` pins all five production inputs and that module. Nothing
in the v3 source, Test10 image, or frozen acceptance receipts is replaced.

The connected RG35XX H reports working L3/R3 but no directions. Its fixed
diagnostics repeatedly show CTRL `0x00890000`, channel selection `1`, clock/
reset `0x10001`, valid startup centers `2092/2058/2066/2036`, and ADC polling
blocked by `adc-control`. Three readback failures exhaust the recovery budget.
The independent GPIO clicks remain released and responsive.

The retained BSP header defines an older mode mask as `3 << 8`, but its actual
`sunxi_gpadc_mode_select()` writes `mode << 18`. Retained U-Boot gpkey code also
uses bit 19 for continuous conversion and bit 16 for ADC enable. The captured
CTRL is already enabled and continuous in that real field. Test10 instead
requires bit 9, which does not read back on this machine, so it rejects a
working ADC before taking any run-time analog samples.

The production delta is limited to named CTRL definitions and their two uses:

- ADC enable is bit 16; mode is bits 18:19; continuous mode is value 2.
- Startup/recovery clears only the actual mode field before setting continuous
  and enable. Readiness checks the same actual field. Other saved CTRL bits,
  including auto-calibration bit 23, remain intact.

All v3 model routing, GPIO ownership, ADC ownership/channel/clock guards,
three-frame per-stick neutral gates, center preservation, independent click
debounce, PM PRE/POST handling, bounded recovery budgets and diagnostic cadence
remain unchanged. There are no CCU or PE11 writes or GPIO-mux takeover paths.
No-stick models still exit before hardware access; RG40XX V remains single-stick.

The host fixture executes the actual driver C behind mocked hardware APIs.
For v4 positives and the frozen-v3 field negative, writes and reads ignore
CTRL bits 8:9, mode is 18:19, and synthetic ADC data requires continuous mode,
enable, channel 0 and a ready clock. This specifically avoids the old plain-
array fixture accepting a write to a reserved bit. Tests cover the captured
CTRL/center state, all six stick models, recovery from disabled, single,
single-cycle and burst modes, and the retained v3 safety cases. Actual frozen
v3 code must reproduce blocked sampling, three failed attempts and responsive
clicks under the field readback fixture. The five earlier v2 negative controls
also remain, explicitly isolated under their original legacy array fixture.

`run_host.py` emits a new `roc.h700.stick-recovery-v4-host.v1` receipt and pins
all inputs before and after execution. It requires the coordinated nice 19 /
CPU 0-1 resource-limited runner; this directory's creation does not run it.
Tests do not certify physical timing, stick directions, Android behavior or
suspend/resume. A new module, connected-device verification, loader integration
and a new image are separate steps. Preserve default 2 GiB swap, Nav18, twelve-
model selection and all existing security settings when integrating.

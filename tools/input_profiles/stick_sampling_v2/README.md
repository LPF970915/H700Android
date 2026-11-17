# Bounded H700 stick sampling candidate

This isolated candidate preserves the frozen Test8 source, binary and receipts.
`parent-manifest.json` pins every copied parent input. It is a diagnostic and
sampling-policy candidate, not a physical fix acceptance or formal log policy.
The current physical RG35XX H report proves the selected model, loaded module
and Android axis capabilities, but provides no internal raw ADC samples. The
actual cause of its silent axes remains unproven.

Changes to the actual module translation unit:

- Each physical stick independently requires three samples within normalized
  +/-4096 (the existing advertised Android flat). Another held stick or click
  cannot block it. A held stick at startup or wake remains neutral until its
  own return to center. This tolerance does not change calibration or polarity.
- Each L3/R3 separately needs three consecutive released samples before a new
  down is eligible for the existing two-sample debounce. A one-sample release
  glitch or a held click at wake cannot arm it. Click gates do not block axes.
- PM suspension cancels polling as before. Hardware-invalid state instead
  emits neutral once and retries only fixed clock/reset/CTRL reads every 100ms.
  It does not read ADC data, drive mux GPIOs, write registers, seize ownership
  or recalibrate while invalid. Only independently restored legal state allows
  sampling again, with all center/release gates reset.
- Fixed diagnostics include model, gate masks, last raw sample and age, centers,
  clicks, CTRL, CCU, reason and poll count. A clock-gated ADC CTRL is shown as
  `ffffffff` without reading it. Gated/fault states print at most every five
  seconds; healthy sampling prints one status per 60 seconds so a later normal
  ADB bugreport retains evidence. Transition prints are additionally limited
  globally to one per second, including through PM. No arbitrary MMIO, serial,
  user input payload or write-control interface is exposed.

The zero/one/two-stick catalog, SoC/ABI/ADC/GPIO guards, initial calibration,
existing controller identity/keys/FF, owned-field rollback and module removal
restoration are inherited. Physical polarity, ADC variation, click behavior,
game input and wake acceptance must still be verified on hardware.

`run_host.py --output NEW_DIRECTORY` builds and executes the actual candidate
with the host Linux API boundary. It also executes the frozen Test8 actual C
negative controls for four old blockers: partner-stick coupling, exact-zero
jitter lockout, click coupling and permanent stop after a transient hardware
failure. Hardware APIs are mocked; neither test is a physical acceptance.
Run under `nice -n 19 taskset -c 0` for this light host test. It never compiles
a kernel module, touches a device or changes any original source/receipt.

The ordinary Longan `gpio_keys_polled.c` is not a verified match for the actual
vendor controller. Static Test8 kernel evidence instead binds its real poll
at file offsets `0x540a50..0x540df8` to the original kernel byte for byte. The
actual vendor poll reports fixed legacy axes 3/4/5 and hats 16/17; it does not
iterate the dynamic absbit mask to clear newly attached axes. Do not use the
ordinary Longan generic loop to claim the cause of this physical failure.

# H700 explicit model input candidate

This directory is an isolated candidate. The original BSP, original device
sources, shipped prebuilt module and prior images remain inputs. A successful
host/ABI test is not physical input acceptance.

The old extension always requested `profile=rg34xxsp` and rejected machines
with less than 1.5 GiB RAM. The candidate has no RAM identity test. Both loading
paths use the manually selected canonical `androidboot.roc_model`, together
with a matching `androidboot.roc_sticks`. Android receives these as
`ro.boot.roc_model` and `ro.boot.roc_sticks`. The legacy persistent input profile
also selects media behavior; it is deliberately not repurposed as model ID.

`generate_profiles.py` imports the single model catalog in
`tools/boot_selector/reference_model.py`. Run `--check` to detect drift.

| Model | Sticks | Added axes | Added clicks | ADC sign candidate |
| --- | ---: | --- | --- | --- |
| rg34xx, rgsp, rg35xxplus, rg35xx_2025, rg28xx, rg35xxsp | 0 | none | none | none |
| rg40xxv | 1 | X/Y | L3 | -/- |
| rg34xxsp | 2 | X/Y/Z/RUDDER | L3/R3 | -/-/-/- retained |
| rg35xxh, rgcubexx, rg40xxh, rg35xxpro | 2 | X/Y/Z/RUDDER | L3/R3 | -/-/+/+ |

Negative means the reported axis decreases as raw ADC increases. The channels
are physical mux states 3/2/1/0. `axis_math.h` already computes `middle - raw`,
so the polarity helper applies this sign exactly once. The module retains the
existing Android right-stick `Z/RUDDER` mapping.

The existing RG34XXSP behavior retains its previously exercised polarity. The
other five models use a **common ROCKNIX driver candidate**, pending physical
direction measurements. Saved sources also contain deleted older 35H ranges
that suggest different Y/RY signs; those driver semantics have not been fully
reconstructed. Mathematical monotonicity tests cannot resolve that physical
direction question. No independent per-model invert override was saved for
CubeXX, 40H, 40V or 35Pro.

Saved source provenance is frozen in:

- `out/test7-rg35xxh-sticks-20261116/input-review-v1/hardware-profiles-v2.json`
  (use v2; the earlier GPADC block-selection error is retained as an erratum).
- `out/test7-rg35xxh-sticks-20261116/reference-review-v1/result.json` and
  `direction-source-conflict-supplement.json` (the supplement supersedes the
  earlier single-sign recommendation).

The six stick-equipped models have saved PI0/PI1/PI2 mux and PE8/PE9 click
declarations. Such declarations also occur on boards without physical sticks.
The selected catalog count therefore controls actual axis sampling and GPIO
requests. RG40XX V never samples a nonexistent right stick or requests PE9.
No-stick profiles exit before reading DT, mapping registers, requesting GPIOs,
or changing input capabilities. PE11 remains untouched: source declarations do
not establish its current owner or measured electrical role.

The extension retains the actual H616-compatible SoC check, disabled GPADC
ownership check, exclusive GPIO requests, ready clock/reset check, absent-axis
checks, center bounds, unchanged original controller keys/FF, partial-failure
rollback and restoration on removal. It never force-loads a module or rewrites
MODVERSIONS. Hardware/ABI refusal is nonfatal to Android startup and is logged.

Before suspend, the PM notifier cancels polling and emits neutral axes and
released clicks. After resume, the retained calibration is reused only if the
ADC/clock state is still valid; a changed state neutralizes output and refuses
register takeover. Three full neutral/released samples are required before
input resumes. A stick held through wake cannot immediately drive navigation.

Both loaders pin the actual module SHA and reject duplicate/missing model
metadata, mismatched stick counts, and an already-loaded different profile.
They never unload a competing module. The early helper is installed at
`/grow/h700-optional-axes.sh`; Android's retained service script is replaced at
`/vendor/bin/rgsp-stick-axes.sh`. The common module stays at
`/vendor/modules/h700_stick_axes.ko`. Updating both scripts together prevents
the old hardcoded RG34XXSP path from restoring the wrong profile.

Validation commands (ordinary files only):

```sh
python3 -B tools/input_profiles/generate_profiles.py --check
gcc -std=gnu11 -O2 -Wall -Wextra -Werror -Wno-sign-compare \
  tools/input_profiles/test_driver.c -o /tmp/h700-profile-driver-host-test
/tmp/h700-profile-driver-host-test
python3 -B tools/input_profiles/test_loaders.py --output NEW_OUTPUT_DIRECTORY
```

`test_driver.c` includes the actual candidate driver translation unit. Its
kernel APIs are mocked; it exercises all twelve model routes, center/ownership
failure paths, per-axis math, partial GPIO rollback, input capability changes,
single/dual count clipping, PM cancellation and wake-neutral gating. It does not
simulate the physical ADC or certify the chosen polarity. Loader tests run the
early script with the retained ARM64 BusyBox and its exact original libraries,
with only `insmod` intercepted; Android command APIs are a separate test seam.

`build_module.ps1` defaults to an inspectable plan. `-Execute` uses the normal
one CPU, CPU 0-1, nice 19, 6 GiB RAM, 512 MiB swap, idle I/O, global lock and
three-hour cap. A private mount namespace makes original BSP kernel sources
read-only. The new work directory compiles only preparation tools, nineteen
small export translation units and this module. Full kernel/image targets,
device control, module loading and source CRC rewriting are absent. It checks
the module against 410 working reference CRCs, locally generated CRCs, the
pinned original kernel, and identical Test7 export/CRC/name/relocation ranges.

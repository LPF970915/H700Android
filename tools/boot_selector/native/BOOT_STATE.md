# Boot-state helper integration

Final helper candidate: `out/boot-selector-integration-20261114/boot-state-v2/boot-state-aarch64`.

- Static AArch64 ELF: 636640 bytes, SHA256 `45b726a5b0f6302252e76e77b063f7e814ce735ae3ffa8f896def7f3c9da94c9`.
- Source `tools/boot_selector/boot_state.c`: SHA256 `cbc7a63041d72633a71fbc8539e8140e1b0dbed3ca84450eab9d714865c977f7`.
- Host helper: 21968 bytes, SHA256 `ee915b6307373634ded5e62b5cf3f8a65c6cdaac2e892567b5316fbe67d8af70`.

The older helpers in native/build-v3 predate strict result JSON parsing and next_start validation. Do not install those versions.

## Commands

```text
boot-state --result /run/roc-selector-result.json
boot-state --partition /dev/<confirmed-env-partition> status
boot-state --partition /dev/<confirmed-env-partition> save rg35xxh
boot-state --partition /dev/<confirmed-env-partition> once rg35xxh
boot-state --partition /dev/<confirmed-env-partition> clear-next
```

`--result` touches no environment. It accepts a single-link regular file, no symlink, 1–512 bytes, containing exactly the native menu's three fields: integer `schema=2`, canonical string `model_id`, boolean `save_default`. Any order and JSON whitespace are accepted; unknown/duplicate/missing fields, escaped strings, bad types, NUL, extra JSON and malformed input are rejected. This narrow accepted grammar matches native-generated output. Success prints only:

```text
model=rg35xxh
save=1
```

All 12 canonical model IDs are parseable. The outer init integration must enforce the current image's implemented model set before any selection is applied or saved.

Environment commands require explicit target kind, exact16MiB size, nonblocking exclusive lock, valid128KiB CRC, `roc_selector_schema=2`, an actual `run roc_selector_apply` call in boot_normal, and a nonempty roc_selector_apply variable. `--partition` requires a block device; `--fixture` requires a single-link ordinary file and is reserved for offline tests. No implicit path discovery exists in this helper.

`status` prints three safe lines: `saved=...`, `next=...`, `next_start=...`. Saved/next must be empty or canonical; next_start must be empty or exactly1, and next_model/next_start must appear together. Those checks apply before writing as well. Invalid state fails instead of being silently migrated.

`save <model>` updates the saved default and clears the one-shot selection. `once <model>` preserves a saved default and sets next_model plus next_start=1. `clear-next` removes the two one-shot keys while retaining the saved default. Only these three owned keys are changed; unknown keys, order, values and the presence/absence of the vendor's leading empty row are preserved. Bytes after the first128KiB of the16MiB target are never written. Readback is checked after fsync. If writing or verification fails, the original128KiB is restored where possible and the command fails. This is verified write/readback behavior, not a guarantee against power loss during a raw environment write.

## Validation

`native/test_boot_state.py` reads the real parent environment range from the retained shared Test2 prefix and builds ordinary16MiB fixtures. It does not open real block devices. Host and actual static AArch64/QEMU each passed50 cases: state transitions, no-op idempotence, original unknown-row/order/leading-empty preservation, no-leading preservation,128KiB CRC, exact16MiB remainder preservation, missing integration markers, invalid state, duplicate keys, badCRC, wrong size, symlinks/hardlinks, FIFO/directory, regular file rejected as block partition, and strict result JSON cases.

Evidence: `out/boot-selector-integration-20261114/boot-state-v2/{result.json,tests.json}`. Controlled unit `roc-boot-state-20261114-163107`: PASS5.997s, CPU3.886s, swap0. First build163054 failed only a misleading-indentation warning under `-Werror`; source formatting was corrected, failure retained. Selector ELF was not recompiled or changed during this helper work. No live card, block partition, device security or runtime state was touched.

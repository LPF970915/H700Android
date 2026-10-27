# H700 workspace instructions

Read `docs/CURRENT_BASELINE_20261028.md`, `docs/REPRODUCE_BASELINE_20261028.md`, and `docs/STORAGE_RETENTION_20261028.md` before changing build inputs, device state, or storage.

- Current working-tree checkpoint: `baseline/h700-storage-trim-20261028`; immutable source freeze: `baseline/h700-v5i-usb-network-20261028`. Read `docs/CLEANUP_20261028.md` for removed historical content and `docs/SPACE_REVIEW_20261028.md` for the subsequent WSL/source/image storage pass. The delivered v5i IMG predates the USB/network fixes; do not describe it as already containing them.
- `docs/baselines/h700-v5i-usb-network-20261028/source-lock.json` locks the frozen edited-source overlay. Historical prepare scripts are not an ordered rebuild recipe; do not replay them blindly after restoring final source.
- `LOCAL_PRESERVE_H700_BASELINE_20261028/`, final IMG, final native35 stage, upstream archives, signing material and needed WSL source are protected local inputs, not all backed up by Git. Do not treat them as caches during ordinary cleanup. Follow the retention document and the user's explicit cleanup scope.
- Do not upload images, private keys, raw device/session logs, local preservation directories, `.dsh-diag/`, or unrelated caches. Publish sanitized evidence summaries; preserve exact frozen source hashes.
- New and old devices share product labels. Read serial/model/transport before control. Current private identity is in the local preservation directory when present. Old audit defaults target COM4/old RGSP and must be adapted; never control the Retroid.
- At most one controller and one passive observer may own a session. Retry observations only, never blindly repeat A/directions or destructive actions.
- Build through `tools/build_h700_low_pressure.ps1 -Execute`: aggregate one CPU, CPU affinity 0-1, `-j1`, 6GiB RAM, 512MiB swap, nice 19. Do not relax these constraints.
- Use LF for new Android shell/init files. Frozen snapshots preserve exact native bytes (including existing vendor CRLF) and are marked `-text`; never reformat them. Preserve upstream notices and retain failed evidence/rollback inputs until scoped cleanup is authorized.
- Software fixes and baseline reviews do not imply whole-card flashing, formatting, boot0/GPT writes, factory reset or cleanup.
- Historical scripts/docs/tests removed from main remain accessible through the source-freeze tag. Do not restore the entire old tree just to retrieve one historical reference. Current Java host tests use `tools/test_navigation_geometry.ps1` and `tools/navigation_tests/`.

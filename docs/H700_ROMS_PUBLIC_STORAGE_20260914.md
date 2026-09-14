# H700 ROMS Public Storage Integration

Date: 2026-09-14, Asia/Shanghai.
Status: source implemented, system/vendor built, components persistently
installed on the Wi-Fi-connected device, app/SAF and remount tests passed.
Full device reboot and fresh-flash acceptance remain pending.

The subsequent complete-image baseline is documented in
`H700_V5F_ROMS_BASELINE.md`. Its authoritative offline verification status
is `baselines/h700-v5f-roms/image-manifest.json`.

## Current Device

```text
private mounted null
public:179,8 mounted 7E99-7141
emulated mounted null
sys.rgsp.roms=ready
```

The public volume has label `ROMS`, `mountFlags=VISIBLE`,
path `/storage/7E99-7141`, and raw path `/mnt/media_rw/7E99-7141`.
Only p8 is exposed; the disk remains non-adoptable.
The Settings storage overview shows ROMS under portable storage, with
96.91 GB total and about 2.13 MB used at the screenshot sample.
The ordinary app probe measured 96,906,641,408 total bytes and approximately
96,904,511,488 available bytes. Filesystem activity changes free space.

Local evidence:

- `out/vold-roms/runtime-final.txt`
- `out/vold-roms/storage-final.png`
- Device UI captures under `/data/local/tmp/rgsp-roms-v1/`.

The existing private-storage 32 GB estimate is deliberately not relabeled as
128 GB. Application/private storage and ROMS remain separate filesystems.
The earlier capacity arithmetic is documented in
`H700_STORAGE_RUNTIME_DIAGNOSIS_20260914.md`.

## Implementation

`tools/rgsp-vold-roms.patch` is pinned to this BSP's original sources.
On product `rgsp`, disk major/minor 179:0 is protected:

- Validate p8 device number, partition name and fixed start sector 54960128.
- Require GPT Basic Data for p8 and skip every other partition.
- Forbid the whole-device fallback and public/private/mixed repartition.
- Forbid formatting public representations of boot-card partitions 0-8.
- Refuse to check or mount p8 if mountinfo still contains device 179:8.
- Require FAT and the `ROMS` filesystem label.

Actual p1-p4 are also GPT Basic Data. A generic whole-card fstab entry without
the patched backend is unsafe. The guards were added before live deployment.
Backend format rejection remains necessary even if a Settings format action
is presented. Destructive commands were not executed against the real card
to test their rejection.

`tools/rgsp-roms-visible.patch` changes StorageManagerService's public-volume
visibility for exactly `rgsp`, `disk:179,0`, `public:179,8`. It does not set
adoptable or primary flags and does not replace internal emulated storage.

The vendor fstab registers the mmcblk0 disk source. New ROMS-vold ramdisks
run the existing grow/check helpers before mounting data, then leave FAT
mount ownership to vold. Boot/kernel logs use private `/data/rgsp-persist`.
The image builder's `--roms-vold` option requires a matching raw vendor
image; it cannot silently preserve the old fstab/vendor logger.

`rgsp-roms-handoff.sh` also supports the current device's older ramdisk:
stop the bounded logger, preserve named legacy log files on data, sync and
normally unmount `/rgsp-persist`, restart the data-backed logger, then mount
the registered public volume. Busy mounts are not lazily or forcibly removed.
Its init service runs after boot completion. This compatibility path allows
the installed files to work with the unchanged device boot partition; that
next full-boot path still requires physical acceptance.

## Provider Stability

The BSP defaults low-RAM products to only 3 cached processes, with 1 empty
process. During the first remount/rename test, ActivityManager repeatedly
killed `android.process.media` as `empty #2` before its provider finished
starting. The ExternalStorageProvider and the dependent probe were then
killed. The rename had committed before its response was lost; the test
file was present as `renamed.txt`, not lost.

A controlled change from unset DeviceConfig to
`activity_manager/max_cached_processes=8` stopped this failure. A fresh
create/unmount/check/remount/read/rename/delete sequence then passed.
The handoff script seeds 8 only when the RGSP value is unset, preserving
explicit operator tuning. At the final sample the device had about 557 MiB
MemAvailable. This is not a long-running memory-pressure qualification.

## Live Verification

- Firmware file backups preceded installation.
- Temporary per-file vold/fstab/logger overlays proved p8 discovery and
  sole FAT ownership. Those overlays were removed during persistent install.
- New vold and services.jar were installed together with the fstab, logger
  and compatibility service. One Android framework restart loaded the new
  visibility policy; the kernel/device was not rebooted.
- System and vendor returned to read-only mounts.
- The system directory picker displayed ROMS and granted access through the
  normal confirmation dialog.
- The local-only probe ran as UID 10092, not root. It checked StorageManager
  visibility, created/wrote/read a shared file through a granted SAF tree,
  and separately wrote/read/deleted in its app-owned external directory.
- Normal unmount removed the raw FAT mount. `fsck_msdos -n` passed.
- After remount, the same app read the saved nonce, renamed and deleted the
  file and removed its uniquely named test directory.
- A fresh full cycle after the cache-limit correction returned
  `ROMS_APP_CREATE_PASS` and `ROMS_APP_VERIFY_PASS`.
- The test app was uninstalled, removing its temporary root-tree grant.
- Bounded logging remained running in `/data/rgsp-persist`.

An initial direct-path write to the shared secondary-volume root failed.
This is not counted as a passing test or bypassed with broad filesystem
permissions. The successful shared-file tests use Android's SAF grant;
direct writes were verified in the app-owned external directory.

The first normal vold filesystem check reported and corrected a FAT FSInfo
signature. Subsequent unmounted read-only checks passed. No formatting,
partition resizing, repartitioning, full-card flash or raw boot write occurred.

## Build And Tests

Final installed identities:

| Component | SHA-256 |
| --- | --- |
| vold | `9869fa1e7c4f9584504ef8ffa407381fd9236d711b7b917bd3bab6cb02d012ce` |
| services.jar | `299d97f020f97ca4bfc400773870983f52df8fa8b036ae245640cdad58b04413` |
| handoff script | `e5dce65ed9eaa0ff9a4828b52219ee9ff42f2c0dc03eeaa79c9ba24f5ddb71e5` |

49 host tests passed across ROMS policy/mount ordering, firstboot/HOME,
grow orchestration and dirty-FAT recovery. The 8 ROMS tests include compiled
C++ execution of the exact policy helpers with host fixtures.

`test_rgsp_roms_ramdisk.py` separately rebuilt the ramdisk from the pinned
baseline prefix and verified preserved boot prefix/kernel/DTB, grow payloads,
mount ordering and packaged ARM runtime. This is not full-image verification.
`verify_system(..., roms_vold=True)` passed against the final product output,
including the protected native/framework binaries and the earlier accepted
AT4K, wallpaper, keyboard, Settings and navigation components.

Successful low-pressure logs:

- `out/logs/build/h700-low-pressure-20260914-102534.log`: vold.
- `out/logs/build/h700-low-pressure-20260914-102929.log`: system and vendor.
- `out/logs/build/h700-low-pressure-20260914-104010.log`: framework/system.
- `out/logs/build/h700-low-pressure-20260914-113138.log`: final handoff default/system.

Prepare future builds using `tools/prepare_rgsp_roms.py --source
/home/lpf/h700-android10/android`. It checks pinned source identities and
preserves unknown edits; the generated sync receipt supports subsequent
known local changes. Use the existing low-pressure build wrapper.

The early complete-image packaging attempt failed before producing a
deliverable. Its transformation was corrected and tested separately.
At the end of the initial live integration pass, v5e remained the published
baseline and these ROMS changes were not yet committed. The subsequent
user-requested packaging task produced
`out/H700_Android_SingleCard_v5f_ROMSPublic.img` from the new system/vendor
outputs and new ROMS-vold ramdisk. The v5f baseline documents and manifest
record that follow-on image, 69 packaging-time regression tests and its
verification boundary; v5e is preserved as the prior baseline.

## Rollback And Remaining Acceptance

The original device files are under
`/data/local/tmp/rgsp-roms-v1/installed-originals/` and the key original
binaries/configs are also in `out/vold-roms/`. `.absent` markers identify
new files that did not previously exist. Do not rerun the one-shot installer
over its existing receipt or discard these backups.

Rollback must be coordinated: unmount the public volume normally, stop
framework/vold/logger, restore the recorded original files and labels,
remove only the newly installed handoff files indicated by `.absent`,
restore read-only firmware mounts, and restore the old ROMS/log ownership
before restarting the original services. The prior DeviceConfig value was
unset; only revert it if it still equals this trial's 8. No automatic rollback
was required during the successful install.

Still pending: a complete device reboot with the old-ramdisk compatibility
path, fresh-flash testing of the new ramdisk, repeated cold boots, large game
libraries, long-running memory pressure and application-specific SAF support.

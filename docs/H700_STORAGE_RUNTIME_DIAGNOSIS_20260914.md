# H700 Storage Runtime Diagnosis

Follow-on implementation and live results:
`H700_ROMS_PUBLIC_STORAGE_20260914.md`. The observations below are the
pre-integration snapshot, not the current post-install volume state.

Date: 2026-09-14, Asia/Shanghai.
Transport: Wi-Fi ADB (machine-local endpoint omitted).
Scope: diagnose the Settings capacity report without repartitioning,
formatting, filesystem repair, remounting, service restart or device reboot.

## Confirmed Result

The kernel recognizes the full card address space and the expanded ROMS
filesystem. Android does not publish ROMS as a public storage volume.
Settings displays an estimated private-storage total, not the card capacity.
Its used-space value is not a measurement of files occupying half the card.

The UI hierarchy directly confirms:

- Title: `16.21 GB`.
- Summary: used space, total `32 GB`.
- Donut: `51%` used.

Local evidence:

- `out/logs/storage/20260914/runtime.txt`
- `out/logs/storage/20260914/storage-ui.xml`

These captures do not contain saved Wi-Fi credentials or application data.
The runtime capture ends with expected missing-file errors for the two v5e
identity checks below; that nonzero exit does not invalidate earlier output.

## Measured Geometry

GB here means decimal bytes / 1,000,000,000; GiB means bytes / 1,073,741,824.

| Object | Measured bytes | Meaning |
| --- | ---: | --- |
| mmcblk0 | 125,069,950,976 | 244,277,248 sectors, full kernel-visible card |
| p5 system partition | 8,589,934,592 | Fixed 8 GiB |
| p6 vendor partition | 2,147,483,648 | Fixed 2 GiB |
| p7 data partition | 17,179,869,184 | Fixed 16 GiB |
| p8 ROMS partition | 96,930,363,904 | Expanded to remaining card space |
| ROMS filesystem total | 96,906,641,408 | FAT metadata accounts for partition difference |
| ROMS filesystem free | 96,905,330,688 | Snapshot; background logs can change this |
| data filesystem total | 16,729,894,912 | After filesystem overhead |
| data filesystem free | 16,664,416,256 | Includes reserved blocks |
| data filesystem available | 15,788,646,400 | Non-root usable space |

The data filesystem had about 65.48 MB of allocated blocks at the initial
sample, not 16.21 GB. Allocated filesystem blocks are not an app-category
usage measurement. Reserved space and metadata must remain distinct.

The capacity marker is `capacity_sectors=244277248`.
ROMS is mounted read/write from `/dev/block/mmcblk0p8` at `/rgsp-persist`.
This establishes recognized capacity, not a full-card authenticity or
write/read test. No app-level ROMS write or reboot-persistence test was done.

## Why Settings Says 32 GB / 16.21 GB

Checked against this project's actual WSL Android source at
`/home/lpf/h700-android10/android/`:

1. `frameworks/base/core/java/android/os/storage/StorageManager.java:1223`
   returns rounded `/data` plus system-root filesystem capacity.
   This layout rounds up to 32,000,000,000 bytes. It does not read mmcblk0
   capacity or add the ROMS filesystem.
2. `frameworks/base/services/usage/java/com/android/server/usage/StorageStatsService.java:178`
   returns that rounded total for internal private storage.
3. The same file at line 194 calculates available space from the private
   volume's usable space, with reclaimable-cache handling when applicable.
4. `packages/apps/Settings/src/com/android/settings/deviceinfo/StorageDashboardFragment.java:143`
   displays total minus available as used.

The observed arithmetic reproduces the UI:

```text
32,000,000,000 - 15,788,646,400 = 16,211,353,600 bytes
                                              = 16.21 GB displayed
```

This is not fixed by changing a label from 32 GB to 128 GB: keeping the
private-volume free-space value would falsely inflate the used-space value.
Likewise, adding ROMS free space to app-install capacity would misrepresent
the current separate FAT32 and ext4 volumes.

## Why ROMS Is Absent

Runtime `dumpsys mount` has no disks and no public volume.
`sm list-volumes all` lists only private and emulated internal storage.
The runtime vendor fstab contains system, vendor, data and zram, but no
ROMS vold-managed entry. `/storage` contains only emulated and self.
The existing root-owned `/rgsp-persist` mount is used for boot/kernel logs;
it is not Android public-volume registration.

Do not apply a generic whole-card vold-managed entry as a quick fix:

- This is also the boot/system/data card.
- Local `system/vold/main.cpp` adds disk sources, and
  `system/vold/model/Disk.cpp` scans their partition tables.
- Disk formatting paths can erase the partition table.
- `PublicVolume::doMount()` checks and mounts the filesystem. It must not
  independently check/remount the already live writable ROMS filesystem.

## Runtime Identity Boundary

The connected device reports:
`h700_rgsp-eng 10 QP1A.191105.004 eng.lpf.20260906.180644 test-keys`.
Build properties alone are insufficient to identify a repackaged release.
Both `/system/etc/preferred-apps/at4k-home.xml` and
`/system/media/wallpapers/IMG_3111.jpg` are absent.
The connected system therefore does not match the verified v5e system
payload. Do not describe this run as fresh-flashed v5e acceptance.

The v5e release also explicitly leaves ROMS public-volume integration
pending, so flashing it is not presented as a fix for this issue.

## Follow-On Repair

1. Retain the validated card geometry. Do not re-expand or shrink data/ROMS
   merely to change the Settings percentage.
2. Integrate only the fixed ROMS partition into Android storage ownership,
   with boot-partition filtering and backend protection against whole-card
   format/repartition operations. Coordinate the existing early mount and
   bounded logger so there is one filesystem mount/repair owner.
3. Expose ROMS to Settings, Files/DocumentsUI and app storage selection.
   Keep app-install/private capacity separate from shared-file capacity.
   Correct the private-storage summary using consistent total/free semantics;
   a whole-card overview may additionally show reserved system space.
4. Validate app-context create/read/rename/delete through the exposed volume,
   D-pad navigation, media visibility and log continuity.
5. With an agreed reboot, verify persistence, clean shutdown and repeated
   startup; then build and qualify a new image.

This pass changes no storage behavior and does not claim a deployed fix.
It opens Settings storage and writes only a UI capture in `/data/local/tmp`
on the device. Evidence and this report are saved on the host.

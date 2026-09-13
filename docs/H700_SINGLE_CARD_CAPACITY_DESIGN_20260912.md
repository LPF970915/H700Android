# Capacity-independent single-card image

Status: v5 implementation and helper tests completed; complete-image validation,
card write/readback and physical acceptance have separate gates. See
`H700_SINGLE_CARD_V5_BUILD_AND_ACCEPTANCE_20260912.md` and the image manifest.

## Required behavior

Distribute one raw image with a documented minimum device size in bytes.
Do not distribute separate 128 GB, 256 GB, 512 GB, or 1 TB builds.
Compatibility with every card/controller combination still needs testing.

Keep the established boot payloads and partition starts unchanged.
Keep system, vendor, and Android data allocations independent of card size,
with room for incremental Android updates. Give the remaining space to
the final ROMS/shared-files partition.

After a normal raw-image flash, early boot must detect the actual boot
device capacity and reconcile the GPT and ROMS filesystem before mounting
ROMS. A larger partition alone is not a larger usable filesystem.
An empty shared-files volume is not the same as unallocated sectors.

## Local audit findings

- `tools/prepare_rgsp_single_card_v2.py` sets `SIZE = 62239277056`.
  `header()` and `layout()` derive GPT boundaries from that constant.
- The same generator deliberately uses eight 128-byte GPT entries.
  Its warning says a conventional 128-entry GPT overlaps Boot0. Preserve
  the verified boot-region bytes; do not normalize this layout blindly.
- `tools/create_flashable_image.ps1` copies manifest ranges into a file
  whose length is `manifest.target_bytes`. This assembles an image but
  does not implement device-side expansion.
- `tools/rgsp_single_card_init.sh` requires p8 and mounts it as vfat before
  mounting Android. It later binds this volume to `/rgsp-persist`.
  Removing the dependency requires auditing persistent-file consumers;
  do not silently replace persistent storage with temporary storage.
- Existing ROMS metadata is FAT32, not evidence of an unformatted volume.
  Do not use resize2fs on FAT32 or change to exFAT without checking the
  kernel, early userspace tools, and Android mount configuration.

These are source findings; inspect the packed boot ramdisk before claiming
that edited source has reached a release image.

## Safe expansion contract

1. Identify the actual boot card, sector size, GPT geometry, GUIDs, and
   filesystem; reject an ambiguous device, overlapping ranges, bad CRCs,
   unsupported filesystem, or a device smaller than the image.
2. Validate both GPT copies, preserving boot-region bytes and p1-p7.
   Derive backup-table size from entry count and entry size, not a fixed
   33-sector or 1536-byte assumption.
3. Plan recovery for interrupted updates and stale backup GPT signatures
   left by earlier contents at the physical card end.
4. Relocate the backup GPT and grow only the final partition. Preserve
   its start, name, type, and unique GUID.
5. Grow the filesystem using an appropriate tested implementation.
   Never automatically format an existing ROMS volume to resolve an error.
6. Verify geometry, CRCs, protected ranges, filesystem consistency, and
   available space before recording completion. A marker alone is not
   proof of success.
7. Repeated boots must be idempotent. An already-expanded card must not
   be rewritten each boot. A failed optional expansion should retain the
   original usable storage when possible and report the failure.

## Image size and verification

Eventually publish a compact raw image with a small valid ROMS filesystem,
not a whole-card-sized image padded to a particular card capacity. Shrink
the filesystem before reducing its partition and regenerating the GPT.
Preserve update headroom in system/vendor/data; minimal size is not the
only goal. Compression alone is not a substitute for smaller raw geometry.

Test virtual block devices representing actual 64/128/256/512 GB and 1 TB
sizes, including different nominally-equal card sizes, undersized media,
stale backup GPTs, interrupted expansion, existing files, and repeated runs.
Verify boot regions and p1-p7 unchanged. Then test cold boots, usable ROMS
space, write/read persistence, and restart on physical devices.

Keep the proven v3b fallback and incremental Android build outputs until
a replacement passes physical acceptance. Retire obsolete release images
only after that acceptance.

## Current boot failure: separate investigation

`out/logs/uart/rgsp/rgsp_uart_20260912_201921_115200.log` records successful
DRAM training, recognition of a 119276 MB card, boot package loading,
U-Boot, and Linux kernel startup. Output ends near kernel timestamp 1.84s.
This does not establish that the kernel hung at that instruction, or that
GPT capacity caused the failed Android boot. Compare successful UART logs,
inspect console configuration and packed boot components, and verify card
payloads before assigning a root cause.

The v4 write log reports completion; no complete readback result was
obtained. The attempted ROMS expansion did not show an increased size.
Neither v4 bootability nor its focus-navigation fix is accepted.

## Subsequent card evidence and implementation

Read-only capture `out/rgsp-v4-card-evidence` found a ROMS boot log with three
`ERROR: unable to mount Android data` entries. The captured first 1 MiB of
the data partition is entirely zero, including the ext4 magic location.
This is direct evidence of a missing data filesystem on that card, not
evidence that a 128 GB card cannot boot. The valid v3b data filesystem is
used for the v5 factory image. Do not repeat the earlier capacity-only diagnosis.

The v5 seed image is 32,434,554,368 bytes. Its system, vendor and data sizes
remain 8, 2 and 16 GiB; ROMS starts at byte 28,139,585,536 with a 4 GiB
FAT32 filesystem. Eight-entry GPT metadata is retained at both ends.
The on-device helper moves the backup GPT, enlarges only p8, then grows
the FAT32 filesystem. It never substitutes formatting for resizing.
It refuses media smaller than the recorded source geometry.

Tests cover ARM64 GPT updates for 62,239,277,056 / 125,069,950,976 /
256,000,000,000 / 512,000,000,000 / 1,000,000,000,000-byte devices.
FAT32 resizing to 128 GB and 1 TB device geometries preserves a sentinel
file and passes fsck; these are sparse-file/QEMU tests, not physical
endorsements of every SD card. Linux loop-device integration exercises
the actual partition-resize ioctl and repeated runs.

The implementation deliberately recognizes only this verified eight-entry
layout and 512-byte sectors. It must reject unsupported layouts rather than
guess. Recovery from an interrupted GPT primary-header/entry update uses
the validated physical-end backup. An interrupted FAT resize requires
offline recovery: it is not advertised as power-loss atomic.

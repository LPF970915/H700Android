# H700 Android 10 Single-Card Build

Date: September 11, 2026.
Status: latest main-slot boot FAILED (user reports black screen/no visible
response). Fresh readback confirms the first 8 MiB payload, but the layout
overlaps both Brandy boot-package candidate locations. Repair is not deployed.

The previous whole-card qualification assertion is withdrawn. The old writer
and finalizer are quarantined pending complete source boot-package capture. See
`H700_ANDROID10_SINGLE_CARD_FAILURE_20260911.md` for the September 11 audit.

## Target

方案 A uses one 64GB card in the handheld's original Linux/main-card slot.
The card is intended to contain Android boot, system, vendor, data and a
shared ROMS partition. The second card slot remains optional expansion
storage after Android has booted. The main-card U-Boot reads the GPT
partition named `boot` with `sunxi_flash`, so the boot partition is raw rather
than FAT.

The current dual-card handoff is not reused. It restores TF1 boot, waits for
TF2 and consumes a one-shot marker. The prototype init is
`tools/rgsp_single_card_init.sh`; it mounts the same card as `mmcblk0` and
has no TF1 recovery or marker dependency.

## Current Inputs

- Android system baseline:
  `out/rgsp-fix72-wifi-profile/system.raw.img`,
  SHA256 `199c03bf5b46a81e26aab133d8310ae576690c99c926b1835d5f3e8ac3115faa`.
- Audio vendor candidate:
  `out/rgsp-audio-candidate-20260910/vendor.raw.img`,
  SHA256 `9d0c8d4a95b69131a70db6aebdfa1d9b3967afa9dc7dc8e95932872ecb372cc2`.
- Existing Android kernel/DTB and boot header remain verified inputs.
- Current work card remains the rollback reference and is not modified.

## Proposed 64GB Layout

The first prototype keeps the existing Android partition sizes:

| Partition | Size | Purpose |
|---|---:|---|
| p1 | 64 MiB | raw Android boot image, GPT name `boot` |
| p2 | 8 GiB | system |
| p3 | 2 GiB | vendor |
| p4 | 16 GiB | data |
| p5 | remaining space | ROMS/shared storage |

The layout is approximately 26.3 GiB before p5 and fits a genuine 64GB
card. The exact final sector count must be derived from the new card, not
copied from the current 125GB working card.

## Blocking Qualification

The prototype is not yet a flashable release image. The following must be
verified with the new card and UART:

1. U-Boot main-card `sunxi_flash read boot` can read p1.
2. The loaded kernel exposes the same card as the expected Android block
   device.
3. The boot image loads automatically from the Android card in the TF1 main
   slot without either original work card or manually entered commands.
4. Android's first-stage init accepts the single-card fstab/PARTUUID setup.
5. The second card is optional and is not mistaken for system/vendor/data.
6. A failed boot can be recovered by reinstalling the preserved work card.

No U-Boot environment, boot0, GPT or physical card has been changed in this
offline step.

## September 11 Write Evidence Correction

The first Scheme-A 64GB prototype was written to the USB card identified as
`Generic MassStorageClass`, serial `000000001539`, size
`62239277056` bytes. The target was Disk 3; the TF1 Linux work card and other
disks were not written.

The current writer intends the following layout; this is not proof of its
complete deployment:

- a preserved first 8 MiB H700 source area with replacement GPT records;
- p1 `boot` is 64 MiB at LBA 16384;
- p2 `system` is 8 GiB;
- p3 `vendor` is 2 GiB;
- p4 `data` is 16 GiB;
- p5 is the remaining FAT32 `ROMS` partition;
The retained finalize transcript reports p1-p4 hashes and geometry/GUID checks
passing at 10:30:47. The boot-area file was generated at 14:49:31. No later
successful boot-area write/readback receipt was found in the inspected output
directory. Finalize formats ROMS and reads partitions; it does not deploy or
verify the boot payload. Do not rerun it merely as a read-only diagnostic.

The user now reports a failed physical boot. Fresh card readback and, where
available, UART from power-on are required before attributing the failure to
missing Boot0, partition layout, DRAM, the card, or display hardware.

## Decision After Physical Boot

If the Android card boots in the TF1 main slot with both original work cards
removed, record that single boot observation and
continue with the release-readiness plan. Do not rewrite the card merely
because the first boot creates data or changes normal Android filesystem
metadata. Preserve a complete untouched source-card manifest and create any
debug copy from the offline images.

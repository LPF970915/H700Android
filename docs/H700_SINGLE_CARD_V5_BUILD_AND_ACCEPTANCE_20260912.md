# RGSP single-card v5: build and acceptance

## Scope and acceptance status

This release candidate preserves the proven v3b boot/hardware components,
the adapted AT4K dex/resources, and the TV/D-pad configuration intended for
v4. It adds capacity-independent ROMS expansion and corrects the missing
Android data filesystem observed on the failed v4 card.

An image manifest with `OFFLINE_VERIFIED_READY_FOR_FLASH` means offline
checks passed, not that the device booted. A writer result with
`WRITE_AND_FULL_IMAGE_READBACK_VERIFIED` means the complete image was
read back from the card with the matching hash. Only a later UART/device
acceptance can mark startup, screen layout and input behavior verified.

## Retained baseline and evidence

- Keep `out/H700_Android_SingleCard_v3b.img`: confirmed on two devices.
- Keep `out/rgsp-single-card-v3b-20260912/prefix-212m.bin` and its manifest.
- Failed-card evidence is in `out/rgsp-v4-card-evidence/`.
- The old v4 full image and invalid redundant raw partition payloads were
  removed. The successful v3b image, evidence, Android sources, product
  intermediates and incremental build outputs were not removed.
- Actual incremental build root:
  `/home/lpf/h700-android10/android` in WSL Ubuntu.

The v4 card reached the custom ramdisk and mounted ROMS. Its boot log
reports `unable to mount Android data`; the data partition capture begins
with 1 MiB of zeros and has no ext4 superblock. Do not describe this failure
as proof of a hard 64 GB boot limit.

## Layout and capacity

Raw image: `out/H700_Android_SingleCard_v5_Universal.img`.
Length: **32,434,554,368 bytes** (about 30.2 GiB).
Use a card with at least that many actual bytes; a nominal 32 GB card is
too small. The same image targets 64 GB and larger supported cards.

| Partition | Start byte | Factory size |
| --- | ---: | ---: |
| special | 37,748,736 | 64 MiB |
| boot-resource | 104,857,600 | 32 MiB |
| env | 138,412,032 | 16 MiB |
| boot | 155,189,248 | 64 MiB |
| system | 222,298,112 | 8 GiB |
| vendor | 8,812,232,704 | 2 GiB |
| data | 10,959,716,352 | 16 GiB |
| ROMS | 28,139,585,536 | 4 GiB, grows on first boot |

The remaining space becomes usable FAT32 ROMS storage, not Android app
data and not unallocated disk space. On the currently identified
125,069,950,976-byte card, p8 can hold 96,930,363,904 bytes before FAT
metadata and alignment overhead. FAT32 retains its per-file size limit.
Do not use conventional GPT repair tools blindly: expanding the GPT entry
array to 128 entries overlaps the verified Boot0 at byte 8192.

## Preserving TV mode and AT4K

Android 10 reads `config_defaultUiModeType` as an integer. v5 builds it as
4 (TV), with `config_hasPermanentDpad=true` and
`config_defaultInTouchMode=false`. The earlier boolean
`config_defaultUiModeTypeIsTelevision` did not control this source tree.
TV mode is not proof that every third-party menu correctly handles focus.

Adapted AT4K:

- Input APK SHA256:
  `700276cb79c1e11e974c3fc10ab2edebbb2d381e5af8c60a241b52d3f6e039af`
- Packaged APK SHA256:
  `b6b2a3db335e5f2a27c284fc48ece6de9ccaf46a8886222aef07c17a26ee5d5b`
- `classes.dex`:
  `590718211152c842b9f13d508d96671e66134c806442e4f23b91cdc9a7e10ed2`
- `resources.arsc`:
  `a20e44470f9e51121a6f7c2357cbc43e38ae5798aca3af57e5f2c66ebe69b236`

The Android packaging step changes ZIP-level bytes; it does not change
those adapted dex/resources. Both default-HOME helpers now check the
reviewed input/packaged APK hashes instead of incompatible old hashes.
The adapted input was copied back to the repository prebuilt. The old
repository copy is retained at `out/rgsp-v5-provenance/at4k-previous-cd0568.apk`.

For this full-flash product, the firstboot service runs at boot completion.
It configures LeanbackIME and AT4K once, verifies the result, and records
`/data/local/rgsp-firstboot/complete-v1`. Later user choices are preserved.
Do not separately push this factory-default RC onto existing unprovisioned
user data without reviewing the intended preference changes.

## Rebuild sequence

1. Preserve and verify the input APK above. Do not blanket-sync an old
   Windows prebuilt over the WSL source.
2. Build the system with `tools/build_h700_low_pressure.ps1 -Targets
   systemimage -Execute`. Synchronize the intended overlay, firstboot
   files and `tools/set_rgsp_home.sh` to their existing WSL source paths.
3. Prepare the isolated ARM64 runtime with
   `tools/prepare_rgsp_grow_runtime.sh`. Retain downloaded packages and
   `packages.sha256`; package versions and licenses matter for distribution.
4. Run `tools/build_rgsp_grow_helpers.sh`, `tools/test_rgsp_capacity.py`,
   `tools/test_rgsp_auto_grow.py`, `tools/test_rgsp_offline.py` and the
   root-only `tools/test_rgsp_block_resize.py`.
5. Convert the successful Android sparse `system.img` to raw with the
   build's `out/host/linux-x86/bin/simg2img`.
6. Run `tools/build_rgsp_compact_image.py --system <raw-system> --output
   <new-image-path>`. It preserves the baseline boot/kernel/DTB and
   vendor/data, patches only the ramdisk, and constructs a valid FAT seed.
7. Run `tools/verify_rgsp_compact_image.py <image>` as WSL root. This
   reads the complete image, checks all four filesystems, packed ARM
   dependencies, actual framework resources and APK contents, and gates
   the manifest for flashing. Never manually bypass a failing gate.
8. Re-identify the physical target by USB UniqueId, actual byte capacity,
   boot/system-disk exclusions, and captured first-MiB hash. Use
   `tools/write_rgsp_verified_image.ps1` with explicit values and
   `-ConfirmWrite`. Keep its complete stage log and JSON result.

The build script limits resource consumption. `TasksMax=2048` permits the
old Soong/Go I/O workers without increasing the one-core CPU or 6 GiB
memory quotas. The final small incremental rebuild includes the corrected
firstboot scripts, not just the earlier framework build.

## Expansion safety and limitations

Before mounting ROMS, the ramdisk validates the compact GPT, validates and
mounts data for its journal, checks FAT consistency, and grows GPT/p8 and
FAT32. The packaged ARM64 helper uses libparted's filesystem API only;
it never commits a libparted disk label. FAT label `ROMS` is restored and
verified after resizing because libparted drops the boot-sector label.

GPT backup is committed and flushed before the primary update. Primary
header/entry corruption is recoverable from a validated physical-end
backup. A required kernel partition refresh may cause one reboot; an
already correctly sized kernel partition does not request another resize.

FAT resizing is not power-loss atomic. If interrupted,
`/data/.rgsp-fat-grow-pending-v1` blocks automatic retries. Capture UART and
recover offline; do not remove the marker blindly or format automatically.
First boot, especially on very large cards, can spend time resizing before
the Android logo. Keep stable power connected.

The firmware still runs a development configuration inherited from the
baseline, including permissive SELinux and development ADB. This is not a
security-hardened public consumer release. External redistribution also
requires reviewing the proprietary APK/firmware and runtime licenses.

## Physical acceptance checklist

- Cold boot from TF1 with TF2 removed, with UART captured from power-on.
- Observe expansion completion and Android `sys.boot_completed=1`.
- Verify TV mode and AT4K as the resolved HOME activity.
- Inspect AT4K small-screen clipping and the upper-right menu's lower items.
- Navigate Settings and DocumentsUI with the D-pad, A and B.
- Verify actual ROMS filesystem capacity, create/read a file, and reboot
  twice to confirm persistence and no repeated expansion loop.
- Keep v3b until these physical checks pass. Record failures as failures,
  even when the image and raw-card hashes match.

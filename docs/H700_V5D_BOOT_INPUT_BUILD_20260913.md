# H700 v5d Boot/Input Integration

Physical update, 2026-09-13: first boot passed, but the user's next reboot
failed on dirty FAT plus a stale FSInfo count. This image is NOT physically
reboot-qualified. See `H700_V5D_REBOOT_AND_VIDEO_20260913.md`.
The offline results below remain valid but did not cover this failure.

Date: 2026-09-13, Asia/Shanghai.
Status: systemimage build, corrected complete-image packaging and final
independent read-only release gate passed: OFFLINE_VERIFIED_READY_FOR_FLASH.
The complete image SHA-256 matches the manifest and checksum sidecar.
Physical boot validation remains pending (physical_boot_verified=false).
No physical card has been written by this work.

## Requested Scope

The user requested a new full-flash image containing the preceding
boot-blocker, keyboard and focus-navigation fixes for manual reflashing.
Flicker investigation is paused. Do not interpret this request as permission
to modify supply voltage, panel clocks, POWER mapping or to flash a card.

## Integrated Changes

- Preserve the accepted LeanbackIME APK:
  `2a57b52cbac36d09138f7d94ba43f5d7fa9c4175966f7f1b43bb004b1a83ff18`.
  Physical A opens/operates the keyboard and B dismisses it. This patch was
  already present in v5c and accepted in the later live session; this build
  preserves it rather than claiming a newly proven fix for every intermittent
  noninteractive IME state. Fresh-boot Wi-Fi input still requires acceptance.
- Preserve the v5c Settings APK:
  `f1756b7dca7b92e4b3946c9b66701aa289363b8646e2b1b5b8cae25be03bfc83`.
- Build `RGSPNavigation` from the physically accepted v0.2 Java sources as
  a normal system app, using the platform build's signing configuration.
  Version 1.0 / code 3 keeps package `com.roc.rgsp.navtrial` for source
  continuity. Only version/label and build integration change; the subtle
  gray fill, HAT directions, A actions, B return and editor/IME yielding
  remain unchanged. This is a built-in scoped accessibility service, not
  a claim that all underlying AOSP views now have native D-pad focus.
- Provision that service once for owner user 0 after boot completion.
  Preserve other enabled services and later user disable/preferences.
  Back up the original service settings and roll back failed provisioning.
  No network or input-text logging permissions are added to this app.
- Include the physically validated `console=running -> stop console`
  init action, leaving the existing root `rgsp-console` as UART owner.
  No graphics-driver code or timing change is bundled with that fix.

## Boot And ROMS Handling

The observed reboot blocker was a FAT32 dirty flag. The new ramdisk checker
first runs packaged ARM dosfstools 4.2 in read-only mode. Clean volumes are untouched.
Recovery is restricted to the qualified dosfstools 4.2 diagnostic showing
only primary boot-sector byte 65 = 1 versus backup = 0. It verifies that
clearing this single byte makes the entire boot sector equal its backup.
Any extra FAT/directory/I/O error or unknown diagnostic refuses recovery.

Before the one-byte write, save the boot sector and fsck evidence under
`/data/rgsp-fat-dirty-<boot-id>/` (the ramdisk temporarily mounts data at
`/grow-state`). Flush the backup, recheck the original sector, write exactly
one byte, verify readback and require a clean read-only fsck. Interrupted
capacity-resize markers still block automatic retries. There is no automatic
format, general fsck repair, userdata resize or ROMS deletion.

Inspection of the actual Android 10 `system/core/init/reboot.cpp` found
that `MountEntry::IsBlockDevice` recognizes only `/dev/block` mount sources.
The old ramdisk mounted ROMS from `/dev/mmcblk0p8`, outside that scan.
The new ramdisk creates `/dev/block/mmcblk0p8` from the kernel's reported
major/minor and mounts through it. It MOVES the ROMS mount into Android,
instead of retaining the old-root mount plus a bind alias. This addresses
the software cleanup path; successful physical normal-reboot cleanup still
needs validation. A power loss can still leave filesystem damage.

ARM execution testing exposed that the inherited `/sbin/fsck.fat` is
3.0.26, not the host's 4.2. The recovery path therefore explicitly invokes
`/grow/fsck.fat` 4.2 with the isolated runtime loader and the required
CP850 conversion module. Both the host and the packed ARM tools pass all
nine dirty-FAT tests, including the captured 128 GB fault, a valid Unicode
filename and rejection of an already mounted Android block alias. The legacy
utility is retained for the unchanged clean post-resize check.

The initial packaging run had already packed the old-tool recovery path
when this test found the discrepancy. That unqualified candidate was
refreshed with the tested ramdisk before passing the release gate.
`tools/refresh_rgsp_candidate_boot.py` accepts only that local unqualified
v5d image and the exact old/new boot hashes. It backs up the old boot and
manifest, refreshes only p4, then recalculates the full image hash. The
normal builder now directly emits the corrected ramdisk on future builds.
No intermediate image was offered for flashing.

ROMS capacity remains a separate FAT32 partition; Android public-volume
exposure and app-level ROMS read/write are not fixed by this release.

## Build Provenance

Android source: `/home/lpf/h700-android10/android`, WSL Ubuntu.
System build passed at 18:06 on 2026-09-13.
Log: `out/logs/build/h700-low-pressure-20260913-175638.log`.
The existing one-core aggregate CPU, 6 GiB memory and 512 MiB swap build
limits were retained. Source/compiled Settings and Leanback hashes match
the accepted artifacts.

The old v3b image/prefix referenced by earlier documents no longer exists
locally. The retained v5c image is therefore the pinned packaging baseline:

`out/H700_Android_SingleCard_v5c_SettingsDpad.img`

SHA-256:
`cf481773dd2658a0a7307222f2a19679fd74c88a53923a0d72a13bfe7ef711cb`.

The builder verifies this complete hash before use. It preserves the
bootloader, kernel/DTB, vendor and empty factory data; repacks only the
ramdisk, replaces system, and creates the existing clean 4 GiB FAT seed
for firstboot expansion. No live device passwords, personal settings,
navigation test files or diagnostic logs are copied into the image.

New output:
`out/H700_Android_SingleCard_v5d_BootInput.img`.
Do not flash a `.partial` file or a candidate whose JSON manifest has not
passed `OFFLINE_VERIFIED_READY_FOR_FLASH`.

Image size: `32434554368` bytes (about 30.2 GiB; nominal 32 GB cards are
too small). Corrected image SHA-256:
`96e31e46273dbe1882295e031e56bb3a7bb502b59482b26a09cf6db23cffc2e4`.
Corrected boot/p4 SHA-256:
`5e5a7245d90317b2c7ec2312fb8cc43cafdd1f27c0d7ff9969a6481200c4cf57`.
Built-in navigation APK SHA-256:
`d6e417bbc76be29962eaf9eab4dee7a33101203e85df10ea666d7c7d87ba9b56`.

Completed checks:

- 42 host tests: FAT recovery, factory navigation provisioning, grow-script
  orchestration, existing firstboot behavior and boot/package checks.
- Nine tests repeated with the actually packaged ARM fsck and BusyBox od.
- Ten host Java directional-navigation cases.
- Seven capacity tests, including 64 GB-1 TB GPT geometry/idempotence,
  corruption rejection/recovery, and 128 GB/1 TB FAT growth with file
  preservation. The initial run referenced the removed v3b fixture;
  the retained v5c fixture replaced it and the complete suite was rerun
  successfully, not simply marked passing.
- Linux loop-device p8 resize/ioctl and repeat-run integration.
- ARM BusyBox ROMS mount/move, actual `/dev/block` mount provenance,
  writing a fixture file, clean unmount and FAT dirty flag cleared.
- Read-only system-image inspection: accepted IME/Settings hashes,
  AT4K dex/resources, TV/D-pad resources, navigation service and init scripts.
- Final independent release gate: baseline identity, GPT CRC/bounds,
  preserved bootloader/kernel/DTB, packed ARM runtime, four clean
  filesystems, system components and complete image SHA-256 all passed.

Final logs are under `out/logs/build/`, named `h700-v5d-*`.
The intermediate image hash beginning `cad4ea5e` is obsolete and must not
be used to identify the corrected image.

## Acceptance After Flash

Full-card flashing overwrites existing card data; back up needed files first.
Use the 128 GB card or another card larger than the image, not a nominal
32 GB card.

1. Boot TF1 alone, allow firstboot expansion to finish, reach Android/AT4K.
2. Open Wi-Fi password with A; enter, delete, dismiss and reopen; connect.
3. Add/select Simplified Chinese with physical directions and A.
4. Exercise Files drawer, directories, toolbar and B return; inspect gray fill.
5. Perform two normal Android menu reboots, verifying no FAT-dirty rescue
   stop and that keyboard/navigation provisioning persists.
6. Record black flashes separately; this image makes no flicker-fix claim.

AT4K menu scrolling, broader picker/context-menu/multiselect coverage,
audio acceptance and ROMS public storage remain separate pending work.
The existing development security posture is unchanged; this is an
integrated test firmware, not a security-hardened public release.

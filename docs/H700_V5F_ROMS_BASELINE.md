# H700 v5f ROMS Public Storage Baseline

Date: 2026-09-14, Asia/Shanghai.
Git tag: `baseline/h700-v5f-roms`.
Status: `OFFLINE_VERIFIED_READY_FOR_FLASH`.

## Scope

Integrate the accepted live ROMS storage repair into a complete single-card
image, retain v5e's AT4K/input/wallpaper work, and version the source and
sanitized image receipt as the next development baseline.

The authoritative full-image status and SHA-256 are recorded in
`baselines/h700-v5f-roms/image-manifest.json`. Offline verification does not
qualify a physical first boot or reboot. No device/card is flashed or
rebooted during this packaging task.

## Included

- All v5e components: factory AT4K HOME, original translucent bottom shortcut
  row lifted into view, menu scrolling, bundled IMG_3111 custom-image default,
  wallpaper export, accepted LeanbackIME and Settings APKs, gray D-pad
  navigation and a single UART console.
- Protected vold exposes only the fixed p8 ROMS partition of the boot card.
  Backend guards reject boot-card format/repartition and whole-device
  fallback; other boot/system/data partitions are not exposed.
- StorageManagerService publishes ROMS as a visible portable volume for
  Settings, Files/DocumentsUI and applications using a normal SAF grant.
  It is neither primary storage nor adoptable app storage.
- The new ramdisk retains GPT/FAT growth and checked dirty-FAT/stale-FSInfo
  recovery, then delegates FAT mounting to vold. It no longer holds p8
  mounted for diagnostic logs. Boot/kernel logs live in `/data/rgsp-persist`.
- A boot-completed handoff service also supports an older ramdisk when
  persistently installing individual components. It seeds the cached-process
  limit to 8 only when unset, addressing the observed SAF/provider restart
  loop without overriding an explicit operator setting.

ROMS remains separate from the fixed internal app/data filesystem. The
internal summary can still show a nominal 32 GB total with roughly 16 GB
available; this is not the whole card's capacity. The tested card reported
about 96.91 GB in the separate ROMS entry. This release does not change the
private-storage accounting formula or repartition data to absorb ROMS.

## Image Inputs

Output: `out/H700_Android_SingleCard_v5f_ROMSPublic.img`.
Size: 32,434,554,368 bytes (about 30.2 GiB).
SHA-256: `fed34834be77931bc38f1bf925bf66451c242c2b5dc6bde75e7a107e55be21bb`.
Use a 64 GB or larger supported card, not a nominal 32 GB card.

The preserved v5d image is only the hash-pinned source of hardware payloads
and blank factory data. Its previous physical reboot failure remains
historical evidence, not an accepted reboot result. v5f replaces its ramdisk,
system and vendor and creates a clean 4 GiB FAT32 ROMS seed that grows to the
remaining card capacity on first boot.

The raw system/vendor inputs were converted from the actual final product
outputs, not from older retained raw images. Build logs:

- `out/logs/build/h700-low-pressure-20260914-102534.log`: protected vold.
- `out/logs/build/h700-low-pressure-20260914-102929.log`: system/vendor.
- `out/logs/build/h700-low-pressure-20260914-104010.log`: framework/system.
- `out/logs/build/h700-low-pressure-20260914-113138.log`: final handoff/system.

No live userdata, Wi-Fi credentials, app preferences, diagnostic logs or
storage probe APK are included in the factory image. The complete image
stays local; Git contains the integration source, existing product prebuilts,
tests, documentation and sanitized receipts.

## Verification

See `baselines/h700-v5f-roms/test-results.json` and the image manifest.

The live component integration already passed ordinary-app StorageManager
visibility, SAF create/write/read, app-owned external-directory I/O, normal
unmount, read-only FAT check, remount, persisted read, rename and delete.
The temporary probe and its test directories were removed. This was a
component upgrade of an older device image, not a fresh v5f flash.

The 69 packaging-time regression tests cover ROMS protections, default-HOME
preservation, firstboot, dirty FAT, grow orchestration, wallpaper export and
navigation provisioning, and 64 GB through 1 TB growth/file preservation.
A separate ramdisk test verifies the actual ARM
runtime, preserved kernel/DTB and mount ordering. The full-image gate checks
GPT, all four filesystems, blank factory data, exact system/vendor payloads,
boot preservation and the complete image hash with read-only loop mounts.

## After Flash

Back up needed files before flashing: writing a complete image overwrites
card data, including existing ROMS files.

1. Confirm first boot reaches AT4K without a HOME chooser and uses IMG_3111.
2. Check the shortcut row, DOWN into other apps, menu scrolling, Wi-Fi
   keyboard, language selection and Files using physical keys.
3. Open Settings storage and scroll to portable storage / ROMS. Its capacity
   should track the remaining card space, not just the 4 GiB factory seed.
4. Use a normal app or Files to create, read, rename and delete a test file
   on ROMS. An app may need an explicit directory-picker permission grant.
5. Perform two normal Android reboots and a cold boot. Confirm Android and
   ROMS return, the retained file is readable and logs continue on data.

Full-device reboot of the older-ramdisk compatibility path, fresh-flash
acceptance, large libraries, application-specific SAF behavior, long-running
memory pressure and audio remain pending. This release makes no hardware
flicker-fix claim.

Details: `H700_ROMS_PUBLIC_STORAGE_20260914.md`,
`H700_STORAGE_RUNTIME_DIAGNOSIS_20260914.md`, and
`H700_V5E_AT4K_BASELINE.md`.

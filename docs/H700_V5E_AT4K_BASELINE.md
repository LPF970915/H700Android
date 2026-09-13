# H700 v5e AT4K Integration Baseline

## Scope

Requested integration: make AT4K the factory HOME, retain the corrected
bottom shortcut row and menu scrolling, bundle IMG_3111 as the initial
custom-image wallpaper, build a complete system image and push the source
baseline to Git. This remains development firmware, not a production or
security-hardened release.

The final image manifest under `docs/baselines/h700-v5e-at4k/` records
`OFFLINE_VERIFIED_READY_FOR_FLASH`. Physical boot,
two normal reboots and first-run picker behavior remain acceptance tasks.
No physical card was flashed by this work.

## Included

- Initial HOME preference for `com.overdevs.at4k/.MainActivity`, installed in
  `/system/etc/preferred-apps/at4k-home.xml`. Launcher3 and RGSPLauncher stay
  available for recovery. This is not an every-boot kiosk override.
- Latest AT4K prebuilt: original translucent five-shortcut row fully visible
  near the bottom at the RGSP resolution; other apps below the first viewport;
  toolbar remains in its original initial position.
- Main category scrolling and reduced category/submenu padding. Live injected
  D-pad checks reached offscreen items in Theme, Appearance and Controls.
  This does not qualify every nested dialog or physical key combination.
- `IMG_3111.jpg`, unchanged original, included both in the APK and at
  `/system/media/wallpapers/IMG_3111.jpg`.
- First unset AT4K theme becomes `mode=customi` using
  `android.resource://com.overdevs.at4k/raw/rgsp_wallpaper`. Existing theme
  choices are preserved. Licensing state is not modified.
- Missing bundled JPEGs are copied to `Pictures/Wallpapers` after boot and
  media-scanned. Existing files are preserved. Additional images can join this
  directory in future builds without altering the selected theme.
- Previously accepted LeanbackIME, Settings, built-in gray focus-navigation
  service and single UART console configuration are retained.
- Latest qualified dirty-FAT/stale-FSInfo checker is in the new ramdisk, with
  sector backups and refusal of broader corruption. ROMS shutdown mount
  provenance remains `/dev/block/mmcblk0p8` with mount-move handoff.

## APK Provenance

- Final APK SHA-256:
  `b2fa0343e903ad01c3854999dba70335ba4df5f5522dd931ed9d7189cf841a7d`.
- DEX SHA-256:
  `e54181a4c6b8149d65199abe4bbb4231109bb425ab92bf793b3d5f7eb2e948b9`.
- Resource table SHA-256:
  `9cafe0ec2ec20680e2fe319dceae5ed1f5a42bcb6c92585492d464ea63b0d8f9`.
- Wallpaper SHA-256:
  `0d99ad08346620e240fa6eb7e765bb55996d4a311c8141a209626e08cad88997`.

The AT4K Make module copies the already aligned, signed APK unchanged.
Both v2/v3 signature verification and the actual Android 10 build-output
hash check passed. Earlier experimental re-packed or v1-only APKs are not
the product prebuilt. See `tools/at4k/README.md` for the build order.

## Build and Packaging

Android source: `/home/lpf/h700-android10/android`, WSL Ubuntu.
Build log identifier (host local timestamp):
`out/logs/build/h700-low-pressure-20260914-020717.log`.

`systemimage` completed successfully in 14m22s through the existing
one-core aggregate CPU, `-j1`, 6 GiB RAM, 512 MiB swap build wrapper.
The resulting system image contains the expected unchanged signed APK,
original wallpaper and default-HOME configuration.

The earlier v5c image is no longer present locally. The retained v5d image is
the explicitly hash-pinned packaging input:
`96e31e46273dbe1882295e031e56bb3a7bb502b59482b26a09cf6db23cffc2e4`.
Its prefix hash is
`aaf0558ae5062c3698d116f546c85320336689e3bfc6952b4cc7305f7d8d3da6`.

This does NOT requalify v5d, whose physical reboot failure remains recorded.
The builder preserves its hardware payload, vendor and blank factory data;
replaces system; repacks the ramdisk with the latest checker; and creates
a clean 4 GiB ROMS seed. The independent release gate rechecks all of these.
No live Wi-Fi credentials, private preferences or user data enter the image.

Verified output:
`out/H700_Android_SingleCard_v5e_AT4KDefault.img`.
Size: 32,434,554,368 bytes. Use a 64 GB or larger card, not a nominal 32 GB card.
Image SHA-256:
`7c1eea8d903315dbe210dadc3ff61e8d618bac3d47a662bd1cf3924a3982ac0b`.
New boot partition SHA-256:
`994baba1ba8b8243165331a1439cb4612aabf116cbbf0c554991b1bb67eb9413`.

## Verification Boundary

Completed before full-image verification:

- 23 offline APK/firstboot/HOME tests.
- 7 wallpaper export/product tests.
- 13 host dirty-FAT/FSInfo tests.
- 5 grow-orchestration and 6 navigation provisioning tests.
- 7 capacity tests, including 64 GB through 1 TB GPT geometry, recovery,
  idempotence and FAT growth with file preservation.
- 10 Java directional-navigation cases.
- The 13 FAT tests repeated with the actually packaged ARM runtime.
- ARM BusyBox mount-move, Android block-device source, file write and clean
  unmount on a disposable loop volume.
- Live APK replacement preserved the existing theme. A backed-up unset-theme
  trial initialized the bundled image and retained it after restarting AT4K.
  The original wallpaper bytes matched on host and device.

The independent release gate passed: pinned packaging input, GPT, preserved
bootloader/kernel/DTB, packed ARM runtime, four clean filesystems, exact system
components, blank userdata and the complete image hash. All loop mounts were
read-only and detached when finished.

The image manifest records these independent full-image results. Screenshots,
preferences backups, build logs and complete images stay local; source,
prebuilt APK, bundled image and sanitized manifests are the Git baseline.

## After Flash

1. Boot TF1 and confirm no launcher chooser, AT4K and the bundled image.
2. Check the bottom shortcut row, DOWN to other apps and UP back.
3. Check Theme, Appearance, Controls and file-picker navigation physically.
4. Choose a different theme; restart AT4K and reboot normally to check it stays.
5. Perform two normal Android reboots and confirm no pre-Android rescue stop.
6. Check Wi-Fi keyboard, Chinese-language selection and Files.

Audio, ROMS public-volume access and broad hardware/power qualification remain
separate. The replacement handheld stopped flickering in the user's report;
this release makes no flicker-fix claim.

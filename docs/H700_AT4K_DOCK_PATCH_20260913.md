# AT4K Dock and Menu Update - 2026-09-13

Superseded as the latest artifact by the v5e wallpaper/default-HOME APK.
The dock/menu changes below are retained. See `H700_V5E_AT4K_BASELINE.md`.

## Scope

APK-only live update. Preserve the original home: wallpaper above one
translucent five-shortcut row, with other installed apps below the viewport.
No device reboot, firmware rebuild, preference reset, or licensing changes.

## Delivered

- APK: `out/at4k-video-20260913/AT4K-dock-final.apk`
- Package: `com.overdevs.at4k`
- APK SHA-256: `8c2a7cc5c7bcf08706ffc13f6a2140bc52305f82299703006bc08a9bc557cf08`
- Signer SHA-256: `270d448f3fcab1889d110b8b9852d1d99c867d50c77819c2654494f91eb5ab81`
- Installed successfully using `adb install --no-incremental -r` over Wi-Fi.
- Device endpoint during verification: `192.168.31.160:5555`.

The formal firmware prebuilt has NOT been replaced. The earlier
`AT4K-layout.apk` is superseded and does not contain the effective dock fix.

## Implementation

`tools/at4k/patch_layout.py` patches a fresh apktool decode of the pinned
AT4K baseline. `tools/at4k/RgspLayout.smali` supplies small-screen offsets.

- On configurations below 600dp screen height, lift the original scrolling
  content 52dp. Counter-offset its toolbar to retain the original position.
- Preserve app ordering, shortcut styling, scroll state and user preferences.
- Add vertical scrolling to the main settings category column.
- Reduce main category and shared submenu padding from 32dp to 12dp.
- Retain the existing submenu focus callbacks and scroll implementation.

Baseline APK:
`android/h700-android10/device/roc/rgsp/prebuilt/AT4K/AT4K.apk`

Baseline SHA-256:
`700276cb79c1e11e974c3fc10ab2edebbb2d381e5af8c60a241b52d3f6e039af`

Build sequence: fresh apktool decode, run `patch_layout.py` with the decoded
directory and `--source` baseline APK, apktool build, sign with the compatible
local test keystore, apksigner verify, then install with replacement enabled.
Do not apply the patch twice to an already patched decode.

## Verified on Device

All screenshots are under `out/at4k-video-20260913/`.

- `home-dock-final.png`: 720x480 initial home; original toolbar visible;
  translucent shortcut row approximately y=357..470; all five icons visible;
  no installed-app row on the initial screen.
- `apps-down-final.png`: one injected DOWN reveals the installed-app row.
- `home-return.png`: injected UP returns to the intended initial composition.
- Main settings categories: injected DOWN reaches Help.
- `theme-entry.png`, `theme-down-final.png`: Theme can scroll from Light Mode
  to the offscreen Icon Pack item.
- `appearance-entry.png`, `appearance-down.png`: Appearance can scroll to
  the Screensaver item.
- `controls-entry.png`, `controls-down.png`, `controls-up.png`: Controls can
  move down to enhanced desktop recognition, then back up to five apps.
- Final APK signature verification passed; device crash log was empty.
- Settings toggles were not activated during navigation checks.

These are ADB-injected direction-key and screenshot checks, not physical
D-pad acceptance. Not every nested dialog or help page has been validated.
The narrower padding improves visible space; this update does not claim a
complete menu typography or focus-highlight redesign.

## Device State and Next Step

Device left on the initial AT4K home screen. Manual-test screen timeout remains
2147483647ms; previous 60000ms value is recorded on-device at
`/data/local/tmp/rgsp-at4k-20260913/timeout.before`.

Temporary Wi-Fi ADB remains available for follow-up debugging, with the
previously configured TCP5555 firewall restriction to host 192.168.31.211
and IPv6 TCP5555 block. No persistent TCP ADB property was set.

Original APK and preferences backups remain on-device in
`/data/local/tmp/rgsp-at4k-20260913/`.

Obtain physical D-pad and layout acceptance before integrating this APK into
the firmware. Firmware integration also needs the existing hash-pinned
firstboot/release contracts updated. Boot and flicker work are outside this
APK update; this result does not establish that those issues are fixed.

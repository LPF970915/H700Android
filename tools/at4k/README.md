# RGSP AT4K Integration

The checked-in product APK includes the small-screen dock/menu changes,
14sp submenu rows with CLICK semantics, and custom-image synchronization to
the native A-unlock screen. It is a prebuilt adaptation, not the upstream
launcher's original source tree. Current SHA-256:
`93041269d215dd450f4b559cb4fe57337267753d6ff7444ca142e17d07d997cf`.
See [the device increment](../../docs/RG34XXSP_DEVELOPMENT_20261028.md) for
acceptance limits, signature migration and the unchanged frozen snapshot.

## Inputs

- The older `patch_layout.py` adaptation baseline APK SHA-256:
  `700276cb79c1e11e974c3fc10ab2edebbb2d381e5af8c60a241b52d3f6e039af`.
  It is retained in Git commit `0fd8f20` at
  `android/h700-android10/device/roc/rgsp/prebuilt/AT4K/AT4K.apk`.
  Do not use the new product APK as input to `patch_layout.py`.
- Default wallpaper: product `wallpapers/IMG_3111.jpg`, original bytes,
  SHA-256 `0d99ad08346620e240fa6eb7e765bb55996d4a311c8141a209626e08cad88997`.
- Current `patch_rg34xxsp.py` input SHA-256:
  `b2fa0343e903ad01c3854999dba70335ba4df5f5522dd931ed9d7189cf841a7d`,
  retrieved from `baseline/h700-v5i-usb-network-20261028` by the builder.
- Current toolchain: hash-pinned apktool **2.9.3** (the old 3.0.3 label was
  incorrect), existing AOSP SDK29/Java9/D8/zipalign/apksigner. The JAR is read
  from the historical tag if absent; no extra current repository copy.
- Current signing uses the existing local platform key, not included in Git.
  Certificate SHA-256:
  `c8a2e9bccf597c2fb6dc66bee293fc13f2fc47ec77bc6b2b0d52c11f51192ab8`.
  The former `270d448f…` test key was not found locally; ordinary updates
  from that certificate are incompatible. The documented system-package
  migration preserved this device's data; do not uninstall to bypass it.

## APK Build Order

Run `tools/build_h700_low_pressure.ps1 -Targets H700Apps -Execute`.
The builder restores and verifies the frozen input, decodes it, applies
`patch_rg34xxsp.py`, compiles `RgspWallpaper.java` as classes2.dex, stores
dex/JNI, aligns, signs, and verifies Android 10 compatibility. It does not
install or replace the checked-in product automatically. ZIP timestamps can
change the output hash; verify a new build before updating hash gates.

`patch_layout.py` and `RgspDefaults.smali` document the older small-screen /
bundled-image step already present in the frozen input. Do not replay them
on the final APK. No entitlement/licensing preference is changed here.

The Android 10 Make prebuilt uses `LOCAL_REPLACE_PREBUILT_APK_INSTALLED` to
copy the already prepared APK unchanged. The legacy generic PRESIGNED path
rewrites ZIP entries and strips v2/v3 signatures. A v1-only workaround is
not the delivered artifact.

## Defaults and Additional Images

`RgspDefaults.seed` runs before the launcher's model reads preferences.
It does nothing if either `mode` or `custom_wallpaper_uri` already exists.
For an unset theme it selects `customi`, the stable raw-resource URI and dark
overlay text. No entitlement, licensing, keyboard or navigation preferences
are changed.

The APK's raw resource makes the initial wallpaper independent of shared
storage mounting, picker permissions and media indexing. The system also
stores original JPEGs in `/system/media/wallpapers`. The boot service publishes
missing files into `Pictures/Wallpapers` for later manual selection, without
replacing a user's existing file.

Add future bundled images to the product `wallpapers/` directory using
distinct ASCII filenames and the `.jpg` extension. The product wildcard
includes them on the next build; adding a photo does not change the default
or activate a slideshow.

## Verification

- `tools/test_rgsp_wallpapers.py` belongs to the historical tag; it was
  removed during cleanup. Current on-device menu/mouse/wallpaper evidence
  and kernel ABI receipts are summarized in the device development record.
- `verify_wallpaper_live.py`: explicitly tests unset-theme seeding by backing
  up preferences and removing only the two theme fields. It checks unrelated
  values, captures a screenshot, and verifies an app restart. On failure it
  restores the original preferences. This is not a full-data reset or a
  fresh-flash boot test.
- `tools/verify_rgsp_compact_image.py`: checks the final image's APK, wallpaper,
  default HOME XML and factory scripts against the source contracts.

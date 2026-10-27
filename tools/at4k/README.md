# RGSP AT4K Integration

The checked-in product APK includes the small-screen dock/menu changes and
the bundled custom-image default. It is a prebuilt adaptation, not the
upstream launcher's original source tree.

## Inputs

- Pristine adaptation baseline APK SHA-256:
  `700276cb79c1e11e974c3fc10ab2edebbb2d381e5af8c60a241b52d3f6e039af`.
  It is retained in Git commit `0fd8f20` at
  `android/h700-android10/device/roc/rgsp/prebuilt/AT4K/AT4K.apk`.
  Do not use the new product APK as input to `patch_layout.py`.
- Default wallpaper: product `wallpapers/IMG_3111.jpg`, original bytes,
  SHA-256 `0d99ad08346620e240fa6eb7e765bb55996d4a311c8141a209626e08cad88997`.
- Toolchain used: apktool 3.0.3, Android build-tools 34.0.0 apksigner,
  and the existing Android 10 tree's zip2zip/zipalign.
  apktool is an external dependency; its redundant repository JAR was removed
  during the 2026-10-28 cleanup and remains available in the historical tag.
- Signing uses the existing local compatible development key. The key is
  not included in Git. Certificate SHA-256:
  `270d448f3fcab1889d110b8b9852d1d99c867d50c77819c2654494f91eb5ab81`.

## APK Build Order

1. Decode a pristine baseline with apktool, keeping case-collision mappings.
2. Run `patch_layout.py DECODED --source BASELINE.apk`. The default wallpaper
   comes from the product wallpaper directory. Hash checks reject other inputs.
3. Build the decoded tree with apktool.
4. Before final signing, use zip2zip to store `lib/**/*.so` and
   `classes*.dex` without compression, then run `zipalign -f -p 4`.
5. Sign the prepared APK with apksigner and the compatible local key.
   Verify v2/v3 signatures and verify against `--max-sdk-version 29`.
   Do not rezip or realign the APK after signing.
6. Install with replacement enabled, preserving app data. Verify the wallpaper
   and dock on-device before replacing the product prebuilt and hash gates.

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

- `tools/test_rgsp_wallpapers.py`: image/APK hashes, stored dex/JNI,
  Make contract, export, media scan, repeat behavior and refusal cases.
- `verify_wallpaper_live.py`: explicitly tests unset-theme seeding by backing
  up preferences and removing only the two theme fields. It checks unrelated
  values, captures a screenshot, and verifies an app restart. On failure it
  restores the original preferences. This is not a full-data reset or a
  fresh-flash boot test.
- `tools/verify_rgsp_compact_image.py`: checks the final image's APK, wallpaper,
  default HOME XML and factory scripts against the source contracts.

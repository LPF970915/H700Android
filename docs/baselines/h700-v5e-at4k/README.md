# H700 v5e AT4KDefault Baseline

Integration overview: `docs/H700_V5E_AT4K_BASELINE.md`.
Git tag: `baseline/h700-v5e-at4k`.
The image receipt is `image-manifest.json`; its status is authoritative.
The independent gate passed: `OFFLINE_VERIFIED_READY_FOR_FLASH`.

## Image

- Local file: `out/H700_Android_SingleCard_v5e_AT4KDefault.img`.
- Size: 32,434,554,368 bytes, approximately 30.2 GiB.
- SHA-256:
  `7c1eea8d903315dbe210dadc3ff61e8d618bac3d47a662bd1cf3924a3982ac0b`.
- Recommended card capacity for this image: 64 GB or larger.
- The raw image is local, not stored in Git. Source, product APK, original
  bundled wallpaper, tests and this sanitized receipt form the Git baseline.

This baseline does not claim physical boot or reboot qualification. A complete
flash overwrites card data; make a separate backup of any needed user files.
The retained v5d image is a hash-pinned hardware/blank-data packaging input,
not a recommended image to flash. Its old checker is replaced in v5e.

## Reproduction

1. Prepare the verified local Android 10 build inputs and selected product
   sources. Preserve local signing keys and donor binaries outside Git.
2. Run `tools/build_h700_low_pressure.ps1 -Targets systemimage -Execute`.
3. Convert the built sparse `system.img` to a new raw image with `simg2img`.
4. Run `tools/build_rgsp_compact_image.py` in WSL with the raw system,
   retained pinned v5d baseline, verified grow build/runtime and a new output
   path. Do not overwrite the preserved packaging input.
5. Run `tools/verify_rgsp_compact_image.py OUTPUT.img` as WSL root. It uses
   read-only loop mounts for filesystem inspection and rechecks the complete
   baseline/image hashes. Do not flash a `.partial` or failed candidate.

No live user data, Wi-Fi credentials or app preferences were imported into
the new image. Additional bundled JPEGs belong in
`android/h700-android10/device/roc/rgsp/wallpapers/`.

## Test Receipt

See `test-results.json` for the completed host/ARM/live checks.
`physical_boot_verified` remains false until new-flash acceptance is recorded.

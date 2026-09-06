# H700 Android 10 RGSP Preflight Record

Date: 2026-09-06
Product: h700_rgsp-eng
Status: offline preflight complete; no device write performed

This status describes the preflight step only. Subsequent device deployment
and Fix65-67 repairs are recorded in
`H700_ANDROID10_FIX67_STABLE_DESKTOP_20260906.md`. The test boot listed below
is not the final Fix67 boot; do not use it as a replacement for that entry.

## Package

The final package is generated at:

```text
out/h700-android10-preflight/
```

The package is rebuilt from the Android 10 source output and contains the
verified RGSP kernel, DTB and legacy boot header combined with the current
Android 10 ramdisk, system image and vendor image.

## Payload hashes

| File | Bytes | SHA-256 |
|---|---:|---|
| h700-android10-test-boot.img | 67108864 | b8f7583d18d8c9d8e64c367e23c0eb7c12739b2834d4f53c523c0e33cb3d4fff |
| ramdisk-android10.img | 768459 | 358cade307c2dd42c505872af5aa90af28ac8d00c91cea66adb305db8de3148a |
| system.img | 772759964 | e11a8284244f3efb349540cc2c71f2308a1878ed62a3ccb3b82f9cf322d34ff9 |
| vendor.img | 20975836 | e8f0a46b91f4eb729ee03707210dd41f5f803eef95ef6ea5b6023f82600afd1f |
| system.raw.img | 8589934592 | 4ec7a614a2667fd6eefa42053527ce4f9f6a8dae498f7e1f4a50c1e88b03f485 |
| vendor.raw.img | 2147483648 | 5682a3b884ec195b47bbe8840f4d89a61f860361a2d11f08f2cbd172b3ca38ad |

The complete list, including metadata, is in the package
`SHA256SUMS.txt`.

## Checks passed

- Android 10 B2 staging regenerated from the current source output.
- Boot image is exactly 64 MiB.
- Kernel, DTB and ramdisk survive pack/extract round-trip checks.
- No forbidden product identities were found in the staged ramdisk, root or
  vendor manifest.
- Sparse system and vendor images were expanded to the verified TF2 sizes.
- `e2fsck -fn` returned exit code 0 for both raw images.
- PowerShell syntax checks passed for the B2, preflight and write-gate scripts.
- The package manifest explicitly records `writes_performed: false`.

## Target layout

```text
TF2 /dev/mmcblk1p2  system  offset 269484032   size 8589934592
TF2 /dev/mmcblk1p3  vendor  offset 8859418624  size 2147483648
```

`ANDROID_DATA` is intentionally not included or formatted by this package.

## Hardware boundary

The following work still requires the serial adapter on the RGSP device:

1. Enumerate the live COM port and capture the RGSP boot console.
2. Record live TF1/TF2 CID, boot partition hash, U-Boot environment head hash
   and current TF2 filesystem hashes.
3. Confirm the physical disk geometry and rollback state.
4. Decide whether to use the test boot image as a one-shot handoff input, then
   write only after the live checks pass.
5. Capture the first Android 10 boot, UART, kmsg, logcat, ADB and display state.

The projector remains a reference donor only. Its display, power, audio and
`rtl8822bs` wireless configuration are not part of this package.

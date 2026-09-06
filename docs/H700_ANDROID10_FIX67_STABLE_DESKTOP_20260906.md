# Android 10 Fix67 Stable Desktop

Date: 2026-09-06. Device: RGSP/H700. UART: COM4, 115200 8N1.

## Result

Fix67 boots Android 10 system/vendor images AFTER the deployment repairs below
into Launcher without an interactive serial command. This is not yet a clean,
unpatched image or blank-data installation result.
At uptime 90.85 seconds, `/data` was mounted,
`sys.boot_completed=1`, SurfaceFlinger and zygote were running, and the five
core PIDs were:

```text
surfaceflinger zygote system_server SystemUI Launcher3
1494           1504   1912          2090     2230
```

At uptime 234.23 seconds the same PIDs were still present. The crash log buffer
was empty, and WindowManager reported the focused activity as
`com.android.launcher3/.Launcher`. The verified UART screenshot is
`out/h700-android10-b2/fix67-stable-desktop.png` (157364 bytes, SHA-256
`5fb08ddb1e37079f1aca342c7b13654083fd2be8ef4ef86590e1efe82789c365`).

The device was left running Android on this desktop. The handoff had already
restored and verified the original TF1 Linux boot image, so the next ordinary
reboot returns to Linux unless another one-shot Android boot is prepared.

## Root Causes And Fixes

Four clean-image integration defects were fixed after the earlier visible-UI
milestone:

1. The clean vendor image omitted `/vendor/lib/egl`. The upstream GPU selector
   did not match `mali-bifrost`, so the verified 32-bit H616 Mali r20p0 EGL was
   explicitly packaged and restored as `/vendor/lib/egl/libGLES_mali.so`.
2. The handoff did not execute Android's `latemount`, leaving TF2 p4 unmounted.
   The handoff now requires `/dev/mmcblk1p4` and mounts it read-write at
   `/android-root/data` before `switch_root`.
3. Reinstalling the clean system image removed the RGSP kernel module. The
   deployment now restores the original H700 `mali_kbase.ko`, verifies its
   size and SHA-256, and loads it during `post-fs-data`.
4. Pre-mounting `/data` caused Android `mount_all --late` not to publish a
   crypto state or start the normal nonencrypted framework path. Fix67 sets
   `vold.decrypt=trigger_restart_framework` after the data and graphics-device
   preparation completes. This starts main and late-start classes without a
   serial intervention.

The graphics mapper 3.x lookup messages are compatibility probes. The device
falls back to its registered allocator 2.0 and mapper 2.0 implementation; they
did not prevent boot completion or stable Launcher operation.

## Hardware Acceleration

This boot uses the actual Mali kernel and userspace stack, not software raster
composition:

```text
mali_kbase 512000 ... Live
r20p0-01rel0 (UK version 11.17)
GPU identified as 0x3 arch 7.0.9 r0p0
EGL implementation : 1.4 Bifrost-"r20p0-01rel0"
GLES: ARM, Mali-G31, OpenGL ES 3.2 v1.r20p0-01rel0...
```

HWC still uses the explicitly enabled timerfd software-VSYNC compatibility
path because the H700 framebuffer VSYNC ioctl returns immediately and the
kernel emits no usable display VSYNC events. Rendering and buffer allocation
are GPU accelerated; only presentation timing is synthesized in userspace.

## Artifacts

```text
Fix67 boot SHA-256:
c3745e62bf2e965d7f798c7f2fa851ab43e67bcb463998156a9ccdcc59d06662

Fix67 ramdisk (2605108 bytes):
8160e3a4f4f96a9b6985969003529263ce98a7719c6eb729b0a790a4bc16babd

HWC:
89a1f16c3b2b03b3f3250c77f1cae3d35a9995a44281a7538307d8fbbb7fecf2

Mali EGL:
05dc81f866b7ab947d20f283f25dcd96ca2f56ffd48e637b68778c1a994a6925

RGSP mali_kbase.ko:
987e2feb5621f455c139c9e93c0c2a972f6eee0478b755b2cdfecfeb249970a9
```

Protected TF1 values remain unchanged:

```text
boot: d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
env first 128 KiB: d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
```

The deploy entry point is
`tools/prepare_h700_android10_b3_fix67_framework_trigger.sh`; its complete
device-side payload list is `out/h700-android10-b2/fix67-payload.sha256`.
A Git-tracked copy is `docs/baselines/fix67-payload.sha256`. The image binaries,
kernel module and proprietary EGL are not distributed through Git.

## Evidence

- `out/logs/uart/rgsp/rgsp_uart_fix36_20260906_230048_115200.log`: complete
  Fix67 preparation, protected checks, write, reboot, and Android startup.
- `out/logs/uart/rgsp/rgsp_serial_exec_20260906_230257_115200.log`: automatic
  boot baseline with `/data`, Mali, EGL, boot completion, and initial PIDs.
- `out/logs/uart/rgsp/rgsp_serial_exec_20260906_230521_115200.log`: unchanged
  PIDs after more than 120 seconds, Launcher focus, and empty crash buffer.
- `out/logs/uart/rgsp/rgsp_serial_exec_20260906_230610_115200.log`: persistent
  screenshot size and SHA-256.

## Remaining Work

Update at 23:22 CST: a read-only UART probe found `wifi`, `wifiscanner`,
`connectivity` and `netd` registered. `vendor.wifi_hal_legacy` and `wificond`
were running. No `wlan0` or loaded `8821cs` was present, and the module was not
found at `/vendor/modules/8821cs.ko`, `/vendor/lib/modules/8821cs.ko` or
`/system/lib/modules/8821cs.ko`. The old missing-WifiService diagnosis is
historical, not the current network blocker.
Evidence: `out/logs/uart/rgsp/rgsp_serial_exec_20260906_232208_115200.log`.
At uptime 1242.20 seconds all five core PIDs still matched the Fix67 baseline.

- Run the formal 60-minute soak and ten cold-start qualification.
- Basic RGSP short-press mapping is complete, including temporary A-to-ENTER.
  Continue model-specific boot-time calibration later. RGSP
  has no analog sticks and must not share one fixed map with all H700 devices.
- Regress Settings after WifiService publication; bring up the real Wi-Fi
  driver/interface and other missing hardware backends.
- Adapt audio, suspend/resume, battery/brightness, Wi-Fi, and Bluetooth.
- Replace permissive bring-up policy and broad GPU/ION permissions with a
  production SELinux/device-label policy.
- Investigate a real H700 display VSYNC source and qualify tearing/latency.

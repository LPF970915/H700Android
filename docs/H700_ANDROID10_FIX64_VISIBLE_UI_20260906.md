# Android 10 Fix64 Visible UI

Date: 2026-09-06. Device: RGSP/H700, UART COM4 at 115200 8N1.

## Status

Real 720x480 Android screenshots now show the lock screen, Launcher desktop,
and app drawer. The user confirmed on 2026-09-06 that the physical LCD shows
the same desktop. The visible-UI milestone is confirmed, but this is not
completion of the full A10-B4 qualification. A 60-minute soak and ten cold
starts remain separate acceptance items.

The initial Fix63 session ran for over 30 minutes without a whole-device
reboot. Its SurfaceFlinger/SystemUI/Launcher/system_server PIDs remained stable
until an intentional graphics/framework restart to install Fix64 HWC.
The Fix64 HWC then ran for over ten minutes without recurring post-startup
`Faking VSYNC` messages or a change to those four process IDs.

Full Fix64 boot verification succeeded after the reboot at approximately
11:26 China Standard Time (03:26 UTC). At 11:35:54 the device uptime was
595.24 seconds and SurfaceFlinger/system_server/SystemUI/Launcher still had
PIDs 1481/1732/1912/2083 respectively. No manual watchdog-helper repair was
needed: at uptime 166.12 seconds it recorded `boot_completed=1`,
`stable_seconds=120`, and exited. The original TF1 boot was restored and
verified before Android handoff. This is one full boot, not ten cold starts.

At 11:36 the LCD driver reported 720x480, 59.8 Hz, `err:0`, and `skip:0`.
`MemAvailable` was 699792 KiB; TF2 ANBOOT retained 93 MiB free and `/data`
had 16 GiB available. These point-in-time values are not a memory-leak test.

The final check at 11:41:35 recorded uptime 936.25 seconds (15.6 minutes),
the same four PIDs, and Launcher as the resumed activity after home/app-drawer
navigation. The device was left running Android on its desktop. The 11:39
check independently reverified both protected TF1 hashes and showed only
the single startup `Faking VSYNC` entry at 03:26:22 UTC, with no recurrence.

## Corrected Diagnosis

The previous thread's Fix61 logs did NOT show a stable SystemUI:
its PID repeatedly changed and its RenderThread aborted with
`EGL_NOT_INITIALIZED`. Launcher also reported `ion_open failed with Permission
denied`. Accepting a single snapshot containing four process names, as the
unexecuted original Fix62 proposed, would hide the crash loop.

Three independent defects were addressed:

1. `/dev/ion` and `/dev/mali0` were 0660 system:graphics, preventing normal app
   UIDs from creating GPU contexts and importing buffers. These application
   interfaces now use 0666. Display controller/framebuffer access remains
   restricted to the graphics services. SELinux is still permissive in this
   bring-up image; these permissions are not a production security review.
2. The Windows overlay selected `tablet`, but WSL still built `homlet`.
   HWC and its `libdisplayconfig` dependency therefore switched the LCD into
   HDMI/CVBS policy. Both libraries were rebuilt for `tablet` and installed
   together; the Homlet displayservice autostart was removed.
3. The ramdisk watchdog could not execute its helper after `switch_root`.
   The original `/bin/busybox` is dynamically linked against the Linux
   ramdisk loader, not static. Fix64 preserves the verified static
   `/vendor/bin/busybox` at `/dev/rgsp/busybox`, and reads Android properties
   with `chroot /proc/1/root`. It requires `sys.boot_completed=1` and unchanged
   framework PIDs for 120 samples spaced at least one second apart.

The watchdog stops after that process-stability check; it does not certify
the physical panel or long-duration reliability. Failed startup retains a
600-second recovery deadline, followed by SysRq sync, remount-read-only,
and reboot into the previously restored original TF1 boot.

## VSYNC Compatibility

The H700 LCD interrupt counter advances at about 60 Hz, but the kernel's
VSYNC counter stayed at 3 while its skip counter grew. No `vsync proc` tasks
were found in `/proc`. The test binary `rgsp_vsync_probe` measured:

```text
120 FBIO_WAITFORVSYNC calls: 314375 ns total
3-second netlink observation: 0 VSYNC messages
```

Thus a successful FBIO_WAITFORVSYNC return is not proof of a working wait.
Do not use this ioctl directly as a clock without testing elapsed time.

`tools/h616-hwc-rgsp-software-vsync.patch` adds an explicitly enabled timerfd
source inside HWC's existing event loop. The device property is:

```text
persist.vendor.hwc.software_vsync=true
```

The period comes from the active LCD configuration: 16949152 ns, about 59 Hz.
Rendering still uses H616 Mali-G31/EGL/gralloc and the real H700 display engine.
This is software timing, NOT restored hardware-vblank synchronization.
Hardware VSYNC, presentation timing accuracy, and possible tearing remain
kernel/display follow-up work. Other products keep the original uevent path
unless the compatibility property is enabled.

## Artifacts

All large artifacts stay on D: and are excluded from Git.

| File in `out/h700-android10-b2` | SHA256 |
| --- | --- |
| `hwcomposer.cupid.fix64.so` | `89a1f16c3b2b03b3f3250c77f1cae3d35a9995a44281a7538307d8fbbb7fecf2` |
| `libdisplayconfig.fix63.so` | `0d158bf4ff7335416c319736f52aca3cda57f34f3fded4c2c1d3a6c8b0b5daf3` |
| `ramdisk-a10-handoff-fix64.gz` (2604992 bytes) | `e5f0dab04fdfb7945030b4f2a1265ec2496cc967e3ededa278e808c19284c2fc` |

Protected TF1 values remain:

```text
boot: d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
env first 128 KiB: d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
```

The complete current small-file manifest is `fix64-payload.sha256`. Upload
it and its listed files to TF2 ANBOOT. On the verified original Linux root:

```sh
sh /mnt/sdcard/prepare_h700_android10_b3_fix64_stable_ui.sh
```

This profile invokes the shared Fix63 deployment procedure with Fix64
artifact names, hashes, and software-VSYNC policy. It checks both card CIDs,
protected hashes, payload hashes, ext4 health, and the boot image header
before writing TF1 p4. It never writes boot0, partition tables, or env.
Handoff restores and verifies the original TF1 boot BEFORE Android starts.
The old Fix62 preparation template with REPLACE fields is not deployable.

## Evidence

Local screenshots, all downloaded over UART with matching SHA256:

- `out/h700-android10-b2/fix63-screen-49.png`: actual lock screen.
- `out/h700-android10-b2/fix63-desktop.png`: actual Launcher app drawer.
- `out/h700-android10-b2/fix64-settings.png`: despite the attempted Settings
  launch, the image is the Launcher desktop. It is NOT Settings evidence.
- `out/h700-android10-b2/fix64-final-boot-desktop.png`: desktop after the
  complete Fix64 reboot, 157120 bytes; SHA256
  `d993c626da7f625abe8724c34654c150eb2cb740125543f6f12969e6add19ee3`.
- `out/h700-android10-b2/fix64-confirmed-drawer.png`: app drawer after the
  final reboot, 59648 bytes; SHA256
  `429e38b10b68d61fd8e0e159eeabe2f12befaffc8bb89fdf1013f357809eb174`.

Key logs:

- `out/logs/uart/rgsp/rgsp_serial_exec_20260906_103236_115200.log`:
  original GPU/ION permission failures.
- `out/logs/uart/rgsp/rgsp_serial_exec_20260906_105528_115200.log`:
  successful live repair of the watchdog helper and actual property reading.
- `out/logs/uart/rgsp/rgsp_serial_exec_20260906_110700_115200.log`:
  framebuffer/netlink VSYNC probe.
- `out/logs/uart/rgsp/rgsp_serial_exec_20260906_111319_115200.log`:
  timerfd HWC startup, stable framework, real LCD scanout.
- `out/logs/uart/rgsp/rgsp_serial_exec_20260906_112241_115200.log`:
  more than ten minutes without new post-startup VSYNC stall messages.
- `out/logs/uart/rgsp/rgsp_uart_fix36_20260906_112529_115200.log`:
  full Fix64 boot attempt (capture tool retains its historical filename).
- `out/logs/uart/rgsp/rgsp_serial_exec_20260906_113626_115200.log`:
  watchdog completion, memory/storage snapshot, and LCD scanout state.
- `out/logs/uart/rgsp/rgsp_serial_exec_20260906_113733_115200.log`:
  all nine current payload-manifest entries verified on TF2 after uploading
  the updated preparation script and bounded logcat collector.
- `out/logs/uart/rgsp/rgsp_serial_exec_20260906_113816_115200.log`:
  Settings is killed after `No service published for: wifi` in
  `WifiSummaryUpdater`, not a new EGL/RenderThread failure.
- `out/logs/uart/rgsp/rgsp_serial_exec_20260906_113903_115200.log`:
  stable PIDs, SurfaceFlinger startup history, protected TF1 hashes.
- `out/logs/uart/rgsp/rgsp_serial_exec_20260906_114131_115200.log`:
  final 15.6-minute check, Launcher foreground, LCD state, bounded logcat PID.

## Logging And Build Reproduction

The persistent logcat collector now uses 4 MiB per file plus three rotated
files (`RGSP_ANDROID_LOGCAT_BOUNDED.log`). It was installed and restarted
live after the final reboot; the shared deployment script installs it for
future runs. The ramdisk kernel-log collector is still unbounded and must
be bounded before unattended long-duration operation.

The tablet selector, software-VSYNC property, and GPU/ION permissions must
be present in the WSL device overlay as well as this repository. The tested
property/permission files were synchronized and the common board config
compared equal on 2026-09-06. The tested
TF2 system/vendor partitions include cumulative bring-up repairs and direct
patches: this milestone does not claim that a clean full-image rebuild
reproduces every live partition change. Keep the payload hashes and current
TF2 images together when archiving or reproducing this candidate.

## Remaining Work

- Physical LCD/desktop match is user-confirmed. Detailed tearing,
  brightness, color, and rotation qualification remains.
- Run the full A10-B4 60-minute soak and ten cold-start tests.
- Settings returns to Launcher because the Wi-Fi framework service is not
  published. Adapt the product feature/service configuration and retest;
  an activity-start status of `ok` is not functional success.
- The Gatekeeper HIDL wrapper restarts because its backing HAL is absent.
  Do not package the emulator's insecure software authentication backend
  merely to silence this failure.
- Bluetooth was disabled through Android settings after its unadapted HAL
  caused repeated crashes; radio support is not validated.
- Hardware key navigation, suspend/resume, audio, radio, and production
  SELinux/security are not qualified.
- Bound/rotate the remaining kernel-log collector before unattended long runs.

## Test Incident

An early Fix63 watchdog iteration used an unusable helper and advanced 600
iterations in about 30 seconds. Its premature reset left two FAT log tails
inconsistent. The partition was unmounted, checked with `fsck.vfat -n`,
repaired with `fsck.vfat -a`, and checked again. The recovery image and all
payload hashes remained correct. Later code adds a real-uptime guard and
uses the static vendor helper. This failed iteration is not stability evidence.

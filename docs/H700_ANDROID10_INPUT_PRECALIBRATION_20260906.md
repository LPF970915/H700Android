# Android 10 Input Precalibration

Date: 2026-09-06. This step stops before user-operated physical-key calibration.
The Fix64 HWC, ramdisk, and protected TF1 partitions are not changed.

User-operated calibration has subsequently begun. Per-model constraints and
observations are recorded separately in `RGSP_INPUT_CALIBRATION_20260906.md`;
the preparation results below are retained as the pre-calibration checkpoint.

## Result

Precalibration is ready. Stop here until the user is ready for physical input.
No calibrated `.kl`, TV launcher, or mouse mode has been installed.

- At 12:11 CST, EventHub/InputReader accepted all three real input devices.
  `ANBERNIC-keys` has gamepad/joystick sources `0x01000511`; the two auxiliary
  devices have keyboard source `0x00000101`.
- The evdev nodes are `0660 root:input`, labeled `input_device`. The obsolete
  `js0` interface remains restricted; Android uses evdev.
- A five-second idle sample at 12:12:50 contained no raw input events.
  The getevent warning about `js0` not supporting an evdev ioctl is expected,
  not an unsolicited key event.
- The final installer and a repeated deployment succeeded. At 12:21:22,
  uptime was 3322.85 seconds (55.4 minutes), with unchanged core PIDs
  1481/1732/1912/2083. This still does not complete the 60-minute soak.
- `/vendor` is read-only again. The bounded logger kept PID 14497 across
  the successful repeated deployment. A diagnostic `/dev/kmsg` marker was
  read back from the bounded log, and an on-device stdin test produced
  exactly four 32-byte files at a test limit of 32 bytes.
- Latest desktop screenshot remains correct at 720x480, SHA256
  `c65c827a5726e2fa0027be19e6b3afe9e6c4ab67f34f7db6d117b23e1cd06ed3`.

Evidence:

- `out/logs/uart/rgsp/rgsp_serial_exec_20260906_121135_115200.log`
- `out/input-calibration/20260906_121250-idle.log`
- `out/logs/uart/rgsp/rgsp_serial_exec_20260906_121951_115200.log`
- `out/logs/uart/rgsp/rgsp_serial_exec_20260906_122114_115200.log`
- `out/h700-android10-b2/input-precalibration-desktop.png`
- `out/h700-android10-b2/input-precalibration.sha256`

Build and checks: Android ARM32 logger build passed, three host logger tests
passed, the existing ramdisk/boot-image tests passed, shell syntax and the
AOSP host init verifier passed, and the PowerShell capture tool was exercised
through the idle recording and SHA-verified download.

## Confirmed Starting Point

- Kernel devices: `axp2202-pek`, `ANBERNIC-keys`, `dierct-keys-polled`.
- EventHub initially registered only its virtual keyboard. The real evdev
  nodes remained `0600 root:root` on inherited devtmpfs, and EventHub logged
  `Permission denied` for each one.
- The framework runs with the Android `input` supplementary group (1004).
- AOSP `ueventd.rc` specifies `0660 root:input` for `/dev/input/*`, but the
  handoff deliberately skips coldboot scanning. Merely adding another
  ueventd rule does not repair already inherited nodes.
- EventHub watches CREATE/DELETE, not IN_ATTRIB. A chmod alone does not cause
  it to reopen devices rejected during initial enumeration.
- `/dev/uinput` exists, but no virtual mouse has been created or enabled.

## Implementation

`rgsp-input-prepare.sh` sets evdev nodes to `0660 root:input` and restores
their SELinux labels. A vendor post-fs-data action repeats this before
future framework startup. No game-key mapping is installed before calibration.

The live refresh preserves each character-device inode with a temporary
hard link outside `/dev/input`, then recreates its original pathname.
This gives EventHub a CREATE notification without restarting system_server
or creating a persistent duplicate input device. A failed restoration keeps
the staged inode available for recovery.

`rgsp_kmsg_logger` replaces the runtime unbounded kernel-log reader with a
1 MiB file and three rotations. It handles `/dev/kmsg` EPIPE, flushes at most
five seconds after writes, and uses an exclusive lock to avoid duplicate
collectors. Host tests exercise rotation, restart/append, and symlink refusal.
The old handoff log is retained unchanged once its reader stops.

This only bounds runtime collection after Android starts. The early ramdisk
reader still runs until the replacement is ready; a hard pre-Android cap is
a separate follow-up. The existing logcat rotation remains 4 MiB plus three
rotations. Permissive SELinux bring-up is not a production security baseline.

## Deployment And Verification

The additive installer is `tools/install_rgsp_input_precalibration.sh`.
It validates both card CIDs, TF1 boot/env hashes, the Fix64 HWC hash and the
payload manifest before remounting only `/vendor`. It installs four small
helper files, remounts `/vendor` read-only, starts the bounded logger, and
refreshes inputs. Backups and input dumps are kept in
`/rgsp-persist/input-precalibration-backup`.

The deployment does not write TF1 boot, env, boot0, partition tables, or
the Fix64 graphics payload. Persistence across a future reboot needs its
own verification and is not inferred from a successful live installation.

An initial installation reached input discovery but its final grep used
unsupported basic-regex alternation; this was corrected to fixed-string
checks. A repeat installation exposed ext4 refusing remount-ro while an
unlinked old logger executable was still mapped. The logger was explicitly
stopped, the mount restored read-only, and the installer corrected to skip
identical files and stop the owned collector before upgrading it. The
corrected repeat run passed without restarting the core Android processes.

## Physical Calibration Boundary

Before asking the user to press anything:

1. Verify all three physical devices in EventHub/InputReader.
2. Confirm unchanged graphics/framework PIDs and active LCD output.
3. Record an idle sample and inspect for spontaneous input.
4. Stop and ask the user to get ready.

For each user-confirmed step run, for example:

```powershell
.\tools\capture_rgsp_input_calibration.ps1 -Step dpad-up -Seconds 20
```

The tool captures capabilities and raw timestamped events from all input
devices, then downloads the result with SHA256 verification. It does not
grab or remap devices; unexpected input can still reach the current desktop.
Do not ask for Power or lid-close in the initial sequence.

Suggested sequence: idle, D-pad up/down/left/right, A/B/X/Y, L1/R1/L2/R2,
Select, Start, Menu, volume down/up, then hold/repeat and selected chords.
Do not equate evdev capability names or the historical Linux table with
verified physical labels. In particular, auxiliary-device duplicates and
the vendor's mismatched BTN names must be checked.

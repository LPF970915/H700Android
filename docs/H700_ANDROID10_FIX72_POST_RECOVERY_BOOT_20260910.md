# Fix72 Post-Recovery Boot Regression

Date: September 10, 2026, UTC+08:00.
Device: original RGSP, pinned original TF1/TF2 pair, COM4.

## Authorization And Entry

The user explicitly authorized guarded one-shot preparation and reboot,
followed by Android regression. This includes the TF1 p4 handoff boot
write and TF2 p1 one-shot marker, not formatting, repairing fsck or a
TF2-only boot conversion.

Evidence directory:
`out/rgsp-fix72-boot-regression-20260910-0736/`.
The host authorization receipt was persisted before preparation.
Its SHA-256:
`83a70296c2a5587f57c0f4f549ac6e4e38a7fdfdf2f58907cbedad2f68b3ffe0`.

At 07:35:09, UART confirmed original Linux root and unchanged boot ID
`0269b797-1586-4fe2-b59c-b9776bda94f0`, both card CIDs, external power,
unmounted p4 and no boot marker. Data retained its qualified clean state,
without `needs_recovery`, and the corrected free counters.
Evidence: `out/logs/uart/rgsp/rgsp_serial_exec_20260910_073507_115200.log`.

The exact previously tested helper remained in device RAM:
`/run/prepare_rgsp_fix72_boot_only_diagnostics.sh`, SHA-256
`5351083c4f6c426002459207b7764b05b0d7184b20c1a474f8ea02057fbb4ccf`.
Its source was archived in the evidence directory. All 18 boot-helper
tests passed again before reboot.

## Preparation Attempt

`--prepare codec` began at 07:35:55. This mode runs the complete guarded
preflight before any preparation writes. System, vendor and data each
passed all five read-only filesystem-check stages without diagnostics.
Complete system/vendor hashes were then checked.
Attempt transcript:
`rgsp_serial_exec_20260910_073555_115200.log` in the evidence directory.

The helper subsequently returned `FIX72_BOOT_ONLY_CHECK_OK`, then
`FIX72_BOOT_ONLY_PREPARED` and exit 0. TF1 p4's 64 MiB write was fully
read back, while system/vendor/data were not written by preparation.

## Boot And Recovery Result

At 07:44:19 the independent pre-reboot check reconfirmed:

- TF1 handoff boot hash:
  `c3745e62bf2e965d7f798c7f2fa851ab43e67bcb463998156a9ccdcc59d06662`.
- Original Linux recovery file and original env hashes.
- Exact one-shot marker for this boot.
- First 4 MiB of TF1 SHA-256:
  `54e6c77646578152c2ae6185060aabc01eb1265f3ccf2f572b405a577091dc97`.

The guarded normal reboot was requested at approximately 07:44:57.
Continuous UART capture:
`out/logs/uart/rgsp/rgsp_uart_fix36_20260910_074453_115200.log`.
The legacy `fix36` capture filename is not the Android candidate version.

Linux shutdown reported failure to unmount `/mnt/vendor`. Firmware
reported early DRAM calibration/memory-test failures followed by training
success and a passing memory test, then backup/main SPL writes and
`update boot0 success`. These are retained observations, not a clean
bootloader/hardware acceptance.

Android completed boot with ID
`53fae06e-3b06-4e4d-92b4-beb2febe9fd1`. The first 4 MiB of TF1 changed to
`021245fc0d269c45ae9985e324592c0b877239a44919e21d95f5aec626b205c6`,
consistent with the logged firmware writes. This sampled region is not
an exact byte-range attribution of every bootloader change.

The intended recovery checks passed: TF1 p4 was automatically restored
to original Linux hash
`d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5`;
env retained
`d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396`;
the one-shot marker was consumed. Do not claim all of TF1 was unchanged.

## Runtime And Application Regression

The complete `check_rgsp_fix72_runtime.ps1 -Profile Codec` passed:
`out/logs/uart/rgsp-fix72-runtime-20260910_074832/`.

- `sys.boot_completed=1`; correct original card pair.
- TF2 p2 root and p3 vendor read-only; p4 data read-write.
- p1 `/rgsp-persist` successfully mounted as read-write vfat, without
  any `FAT-fs (mmcblk1p1)` messages in the sampled current kernel log.
- All 17 fixed components plus three codec XML hashes matched.
- No codec-directory overlays; OMX and media services running.
- Active AT4K and LeanbackIME APK hashes and HOME/IME selections retained.
- Recovery Launcher3/LatinIME present, firstboot still `not-applied`.
- Crash buffer empty without clearing logs.

Wi-Fi automatically reconnected with `192.168.31.164/24`. Baidu DNS and
two separate 3/3 ping samples passed. No credentials were read or entered.
The WebView application loaded the real `https://www.baidu.com/` page and
remained foreground. Both UI XML and screenshot were downloaded with
matching SHA-256 and visually inspected. No codec overlay, media-service
restart, certificate bypass or app installation was used.

Evidence files in the new regression directory:

- `https-page.png`: actual Baidu page and HTTPS address, SHA-256
  `d42c1702bfb715dbf4a9352800bda5c549ced996f6113541fea95840994fb77a`.
- `https-page.xml`: SHA-256
  `2beceb92b6edeebf152fbeb270eba6e9650e36b8727b713890b717f20edd8b28`.
- `settings.png`: Settings rendered and focused, SHA-256
  `759f9aaeab7da8384f982298c84e14b7c381321f3a3d76bd8411754a0a059931`.
- `home.png`: returned AT4K desktop, SHA-256
  `bdd08522c7fa83632960e4eeef3d895dc4b478b9d715ce3a4374ed9c2b18a6cd`.

Injected MENU dismissed the existing keyguard; injected BACK returned
from WebView to AT4K. Settings was launched through its standard intent,
then injected HOME returned to AT4K. These are software-injected control
checks, not physical Y/B/HOME button or all-button installation acceptance.
Settings values and permissions were not changed. Settings' activity
`LaunchState: COLD` does not mean a hardware cold boot occurred.

At 07:53:18, final guarded regression passed with uptime 491.62 seconds.
SurfaceFlinger/zygote/system_server remained 1494/1515/1926 across samples;
MemAvailable was 610500 kB. AT4K was foreground, crash buffer still empty,
p1 still read-write with no FAT error lines, no overlays, media running,
and original TF1 p4/env hashes plus absent marker reconfirmed.
Final log: `rgsp_serial_exec_20260910_075311_115200.log` in the evidence
directory. No further reboot or shutdown was requested.

## Acceptance Boundaries

The prior p4 recovery receipt remains valid for its pre-Android timestamp.
Android normally mounts data read-write; later changes must not be treated
as proof that the recovery failed. Never repeat the original-preimage
24-block apply against data changed by a subsequent Android boot.

This is a warm reboot via the TF1-dependent handoff, not a cold-start,
independent-TF2 or formal 60-minute soak qualification. Startup firmware
previously reported its own boot0 updates; verifying p4/env is not proof
that the entire TF1 or early boot region stayed byte-identical.

The p1/data blockers and persistent-codec warm-runtime regression are
resolved for this run. Independent boot, power-off cold cycles, formal
60-minute monitoring, a deliberate settings-save/reboot test, audio,
sleep/wake, power reporting and physical-button APK workflows remain open.
The runtime logs still contain missing power/sensor/soundtrigger/mapper
HAL lookup messages; the present checks do not qualify those subsystems.

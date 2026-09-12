# Fix72 Hardware Regression

Date: 2026-09-08. Host timestamps below are UTC+08:00.
Device: original no-stick RGSP, original pinned TF1/TF2 pair, COM4.
Status: first warm-boot runtime regression passed; overall acceptance OPEN.

September 10 update: after p1/data recovery, the persistent codec vendor
passed a new guarded warm boot, all 20 runtime component checks and a
visually verified Baidu HTTPS page without overlays. The device remains
in Android at AT4K with original TF1 p4/env restored and marker consumed.
Detailed current evidence and remaining hardware boundaries:
`H700_ANDROID10_FIX72_POST_RECOVERY_BOOT_20260910.md`.
The paragraphs below retain the earlier September 8 failure/trial history.

Later checkpoint: application qualification found a WebView native crash.
The missing codec catalog was verified as the cause by a reversible RAM
overlay: the browser then displayed Baidu over HTTPS. The overlay was
removed and media services restored. The frozen on-card candidate still
has the missing catalog; persistent repair and another regression remain
required. The earlier empty-crash-buffer sample is not the current state.

## Candidate And Recovery

The guarded system/vendor deployment and recovery set are recorded in
`H700_ANDROID10_FIX72_DEPLOYMENT_GATE_20260907.md`. The subsequent data fsck
scope violation remains part of that record. Resuming the plan does not
reclassify it as authorized journal-only repair.

Frozen source material and reproduction limits:
`H700_ANDROID10_FIX72_REPRODUCTION_LOCK_20260908.md`.
Two clean Android builds remain outstanding.

The boot-only helper's `--check` passed, then its `--prepare` completed
with exit 0. The 64 MiB TF1 p4 handoff write was read back and verified.
This preparation did not write Android system/vendor/data or env.
It created the TF2 p1 one-shot marker and did not itself reboot.

Evidence:
`out/logs/uart/rgsp/rgsp_serial_exec_20260908_120258_115200.log`.

At 12:12:29, a separately guarded normal reboot was requested. UART:
`out/logs/uart/rgsp/rgsp_uart_fix36_20260908_121229_115200.log`.
The historical `fix36` filename prefix is the capture helper's naming,
not the version of the installed candidate.

The original firmware reported DRAM retraining followed by a successful
memory test, then `get_boot_dram_update_flag 1`, writes of backup/main SPL,
and `update boot0 success`. No tool requested a bootloader/env rewrite,
but the firmware itself performed this startup write. Do not claim the
entire TF1 or early boot region remained byte-identical. The p4/env checks
below do not cover boot0; an immediate pre-reboot boot0 comparison is absent.

## Runtime Result

`tools/check_rgsp_fix72_runtime.ps1` is a repeatable read-only validator.
It checks the frozen 17-entry manifest hash before contacting the device,
then verifies card identities, mount sources/options, runtime components,
active APKs, HOME/IME choices, recovery boot/env and the consumed marker.
It never installs, provisions, repairs, reboots or changes preferences.

PowerShell and remote shell syntax checks passed. All 40 existing host
tests passed again. The new validator then passed on the real device.
Logs:
`out/logs/uart/rgsp-fix72-runtime-20260908_121627/`.

Observed:

- `sys.boot_completed=1`, product `rgsp`.
- TF2 p2 is read-only ext4 root; p3 read-only vendor; p4 read-write data;
  p1 is the `/rgsp-persist` FAT mount.
- All 17 installed component hashes match the frozen candidate.
- Active AT4K and active LeanbackIME APK hashes also match, including the
  package selected by Package Manager rather than just the system copy.
- HOME remains `com.overdevs.at4k/.MainActivity`; LeanbackIME remains selected.
- Launcher3 and LatinIME recovery packages are present.
- First-run helper `status` works and reports `not-applied`. It was not
  run in apply mode; existing selections were retained without reprovisioning.
- TF1 p4 and its recovery image both match the original Linux boot hash.
  The env 128 KiB prefix matches its original hash. One-shot marker absent.
- Native output is 720x480, Android density 213.
- Mali-G31 / r20p0 OpenGL ES 3.2 is active.
- SurfaceFlinger/zygote/system_server PIDs: 1498/1520/1937.
- Boot ID: `42d10299-73b6-4695-a528-c778abee77ea`.
- First runtime sample: MemAvailable 690372 kB; crash-buffer query empty.
  This is not proof of sustained memory/crash stability.

The current `RGSP_ANDROID_PROC_LAST.log` records completed boot and the
same framework PIDs for 120 seconds, followed by watchdog exit.
`RGSP_ANDROID_WATCH_LAST.log` is a stale September 2 record and must not be
used as the current watchdog result.

At 12:27 the same core PIDs and completed-boot property remained present,
uptime 870.26 seconds. This is an interval observation, not a formal
60-minute soak or a cold-boot cycle.

## Network And Display

Without supplying or reading credentials, Wi-Fi reconnected after this
warm boot and acquired an IPv4 address on wlan0. On the handheld:

- `www.baidu.com` resolved; ping received 3/3 responses.
- TCP/HTTP returned `HTTP/1.1 200 OK`, 30522 response bytes.
- The lock-screen notification still displayed limited connectivity.

Logs: `rgsp_serial_exec_20260908_121708_115200.log` and
`rgsp_serial_exec_20260908_121805_115200.log` under `out/logs/uart/rgsp/`.
At this first checkpoint HTTPS had not been tested. The later browser
attempt and RAM-only repair trial are recorded below. The earlier
Google-probe diagnosis is historical evidence, not a new HTTPS result.
Do not classify HTTP success as HTTPS/certificate validation.

Verified screenshots, 720x480:

- `out/rgsp-fix72-regression-20260908/initial-screen.png`: system lock screen.
- `out/rgsp-fix72-regression-20260908/at4k-screen.png`: actual AT4K desktop
  after a MENU key event dismissed the lock screen.

No AT4K layout, default HOME, keymap, lock-screen security or permissions
were changed. Screenshots were deliberate diagnostic writes under
`/data/local/tmp`, then downloaded with SHA-256 verification.

## Keyguard Correction

Injected ENTER and DPAD_CENTER did not dismiss the initial lock screen;
injected MENU did. The initial interpretation that this proved a general
button-only unlock defect was premature.

The user then reported that physical Y unlocks on prior runs, and is
currently away from the device. Both live files and the source confirm:

`key 306 BUTTON_Y` -> Generic.kcm `fallback SPACE`.

SystemUI's `StatusBarWindowView.dispatchKeyEvent` handles SPACE key-up
through `StatusBar.onSpacePressed`. This supports the user's observation.
It does not constitute a new physical-Y test on Fix72. No lock-screen
patch is justified by the failed A-only test, and no such patch was made.

Live Generic.kcm SHA-256:
`a2ff357a8b9e16bf212ec70fad8f6f85af636d06ec40e0f38de74b109c43dd8b`.
Evidence: `out/logs/uart/rgsp/rgsp_serial_exec_20260908_122711_115200.log`.

## Startup Boundary

Live sysfs identifies TF1 as sdc0/mmc0 and TF2 as sdc2/mmc1. This establishes
wiring/controller identity, not BootROM/SPL support for TF2-only boot.
The unchanged saved TF2 GPT head has zero 16-byte headers at offsets 8192
and 131072. This package has no qualified standalone early boot payload;
those two observations alone are not an exhaustive boot-ROM capability test.

The existing handoff still requires TF1 and writes its pinned Linux boot
recovery image. It must not be launched directly with another stock TF1.
The preparation wrapper's CID/hash guards must remain intact.

The original TF1 p5 and p6 were inspected only via ext4 `ro,noload` mounts
under `/dev`, then unmounted and the temporary directories removed.
No startup scripts were executed from these mounts or modified.
The loader chain observed is:

`/etc/init.d/launcher.sh` -> `/mnt/vendor/ctrl/loadapp.sh`
-> `/mnt/vendor/ctrl/mmc_new.sh add`.

`loadapp.sh` then conditionally executes `/mnt/mod/ctrl/autostart`.
However, `mmc_new.sh` only mounts TF2's first partition at `/mnt/sdcard`;
the inspected fstab is unconfigured and the inspected init/systemd files
did not establish how `/mnt/mod` is supplied. This is a candidate hook,
not a demonstrated TF2 autorun path or proof about the second stock card.
Do not merely place a script on TF2 and advertise automatic startup.

Startup file hashes:

- rc.local: `21052e543422aa244af52b965b02e562d007d4a4b8b8097f7349479211e9aa6a`
- launcher.sh: `f7462d88cf221c00ef9c7aa2ef97fa6461d6c61997266bf1d171cdaaadb8fe9e`
- loadapp.sh: `06c8e574780b6cb531822226a7f4159a6bf589804a42412690f7d6bd5104d4b3`
- mmc_new.sh: `460d21394a06231077e4974acd2039f84f91c8c7efbe80b1c9d17dc8c0b24317`

Read-only UART records: 12:24:29, 12:24:49, 12:25:13, 12:25:33,
12:25:56 and 12:27:59 under `out/logs/uart/rgsp/`.

## Remaining Gates

1. Complete physical Fix72 input/app regression and clean-build reproduction.
2. Trace the dual-card hook or implement a separately reviewed TF1 companion
   with per-card recovery, opt-in and failed-attempt loop prevention. No
   automatic boot installer has been deployed. Separately qualify sdc2's
   early boot chain with TF1 absent before producing a TF2-only candidate.
3. Ten genuine cold boots, monitored 60-minute operation, broader settings
   preservation, explicit Wi-Fi reconnect cycles and HTTPS.
4. Audible output/volume, power/charging accuracy, suspend/wake, and physical
   button installation, permissions, app use and HOME return.

Firmware logs show missing requested power/light HIDL services; framework
battery/audio/power services being present does not qualify their hardware
backends. No audio, suspend, battery-accuracy or physical cold-boot pass is
claimed. The user is away, so no unattended power-off/card-move test was
initiated. AT4K layout work and replacement-launcher development stay paused.

## WebView Blocker And Reversible Trial

At 12:31, launching the installed WebView shell with
`https://www.baidu.com/` briefly succeeded at the Activity level, then the
process crashed back to AT4K. `am start -W` status `ok` did not establish
page-load success. Its `LaunchState: COLD` describes an app launch, NOT a
cold boot of the handheld.

Crash evidence:
`out/logs/uart/rgsp/rgsp_serial_exec_20260908_123231_115200.log`.
PID 4175 / `Chrome_InProcGp` received SIGSEGV. The top frame is
`JavaMediaCodecListWrapper::JavaMediaCodecList` in `libmedia_jni.so`.
The three core PIDs stayed 1498/1520/1937.

Both live state and H616 source explain the failure:

- media.player, IOmxStore/IOmx, and the Codec2 software service are running.
- No `media_codecs*.xml` files exist in the normal system/vendor/odm
  configuration directories. The separate software Codec2 APEX has its own
  catalog and libraries, but it does not satisfy IOmxStore's catalog lookup.
- The live `OmxInfoBuilder` reports `IOmxStore reports parsing error`.
- `MediaCodecList` therefore fails initialization. The JNI wrapper throws
  an exception for a null list but then continues constructing the wrapper
  and dereferencing that null pointer.

No JNI/framework patch was made. The intended repair is to supply the
missing catalog, not to hide a broken media subsystem.

`tools/probe_rgsp_software_codecs.sh` defaults to read-only `--check`.
Explicit `--probe` verifies the pinned card pair, read-only vendor and
three XML hashes. It temporarily mounts a small tmpfs on the existing
`/vendor/odm/etc`, preserving its original build.prop, supplies the catalog,
and restarts only the OMX service before opening the browser. Cleanup
stops the test browser, unmounts the overlay, restarts OMX/mediaserver to
discard trial caches, and verifies the original directory and core PIDs.
Unknown mounts are not unmounted. No card filesystem is remounted writable.

Payloads were uploaded with size/SHA verification under `/data/local/tmp`.
This is a deliberate diagnostic data write, not a claim of zero writes
anywhere on the device. The temporary config itself lives only in tmpfs.
Pinned XML hashes:

- Root catalog: `152e5797f0b9a27101faf43614b438f6b75022e9c24423e333582dccbbaed3b4`
- H616 AOSP Google audio: `f33464aee38c30e1fe52764bdb1d98ccd56a8214618d03b061b0fd63c38b0000`
- H616 AOSP Google video: `876f5f850cbb5ce4f7a9582654ce006888903e6016dd0b8053e61ab0fd993839`

The trial at 12:46:40 completed with exit 0 and
`CODEC_PROBE_RESTORED`. The downloaded screenshot shows the Baidu page with
an HTTPS address, rather than AT4K, an error page or a certificate dialog.
No certificate bypass, credential entry or new application installation was
performed. The result qualifies this temporary configuration's page load;
it does not qualify persistent repair, audio/video playback or hardware
decoding.

Evidence:

- `out/logs/uart/rgsp/rgsp_serial_exec_20260908_124640_115200.log`
- `out/rgsp-fix72-codec-probe-20260908/browser-trial.png`
- `out/rgsp-fix72-codec-probe-20260908/browser-trial.xml`

The root catalog and two AOSP copy rules are now in the RGSP product
configuration. The source overlay was synced with the guarded helper.
All 51 host tests pass, including trial cleanup/failure and import rules.
The runtime checker now fails explicitly on a nonempty crash buffer instead
of merely printing its line count. Historical crash evidence is not cleared.

A vendor-only build started at 12:51:18 using the required low-pressure
wrapper. No system/launcher build or new image deployment was requested.
It completed at 13:01:38 with exit 0 (10m19.641s elapsed, 5m16.731s CPU,
5.0 GiB peak memory and 512 MiB peak swap). The one-core CPU quota and
CPU 0-1 cgroup constraint were verified despite affinity warnings.
Log: `out/logs/build/h700-low-pressure-20260908-125118.log`.

Verified artifacts under `out/rgsp-fix72-codec-probe-20260908/`:

- `vendor.build.img`: 38113500 bytes, SHA-256
  `f6f8f013dc75f31142dae6de0537a54b58b935f7ec7d0fbdc4a157c255cdefa6`.
- `vendor.build.raw.img`: 2147483648 bytes, SHA-256
  `ad6b909daec8607376425f5dde01992c41dee10e52a762c6e8a17db6f87c45e0`.
- `vendor.build.fsck.txt`: read-only `e2fsck -fn` exit 0.
- All three XMLs extracted using debugfs match the trial's pinned hashes.
- `build-inputs.json` and `product.patch` retain this build's input evidence,
  not an original Fix72 clean-build lock.

The complete read-only file/ownership/mode comparison against frozen
vendor found four changed entries: the three new XMLs and `build.prop`.
Report: `fresh-build-vs-frozen.json` in the same directory. Therefore the
fresh build is not blindly substituted for the frozen repaired vendor.
The separate narrow packager adds only the XMLs to a new baseline copy.
No persistent deployment or second hardware regression has occurred.

## Narrow Offline Candidate

At 13:14:35 CST, `tools/prepare_rgsp_codec_candidate.py --prepare` completed
the independent candidate at `out/rgsp-fix72-codec-candidate-20260908/`.
Default invocation is hash/path preflight only. Preparation accepts only
the pinned local regular image files, refuses an existing output, preserves
the 120 GiB free-space floor, and never contacts a device.

- `vendor.raw.img`: 2147483648 bytes, SHA-256
  `1e1c90ffdc6fc08e7e40d333d3fab4ea065c19a34df38b4a0889bcc83a8dc891`.
- `CANDIDATE_MANIFEST.json`: status `OFFLINE_VERIFIED_NOT_DEPLOYED`.
- `candidate-after.fsck.txt`: `e2fsck -fn` exit 0, 425 allocated inodes.
- Exactly three added paths: `etc/media_codecs.xml`,
  `etc/media_codecs_google_audio.xml`, `etc/media_codecs_google_video.xml`.
- New files preserve the built 0644/root/root metadata and
  `u:object_r:vendor_configs_file:s0` SELinux label.
- All existing paths, file hashes, modes, ownership, symlink targets and
  extended attributes match the frozen baseline. Timestamps and ext4
  allocation metadata are not asserted identical.
- All seven frozen vendor component checks remain valid; the original
  vendor and build image full hashes were rechecked after packaging.
- A separate run of the existing read-only image comparator confirms
  exactly three changes; report `independent-diff.json`.
- Executed recipe and its two Python dependencies are archived alongside
  the candidate with hashes in its manifest.

The original system image, TF1, TF2 and data were not modified by packaging.
This is not a generic replacement for the two-image deployment package:
the boot-only helper still pins the original vendor hash, and the existing
writer expects its existing two-partition manifest. Do not bypass either
guard. Persistent deployment requires separately reviewed candidate-aware
validation, backup/readback and boot/rollback handling.

The RAM trial used `/vendor/odm/etc`, while the product build and candidate
use `/vendor/etc`. Persistent catalog discovery and WebView regression
therefore remain mandatory. Software catalogs do not qualify hardware
decoding or audible output. The final full host suite passes all 62 tests,
including 11 narrow-candidate tests. WSL mount inventory confirms all
temporary candidate/comparison mounts were removed.

## One-Hour Interval Observation

At 13:15:20 CST, read-only UART confirmed:

- Boot ID unchanged; uptime 3760.12 seconds (about 62.7 minutes).
- SurfaceFlinger/zygote/system_server remain 1498/1520/1937.
- MemAvailable 635700 kB; USB power reports online.
- OMX/media/Wi-Fi HAL services running; vendor remains read-only.
- `/vendor/odm/etc` contains only original build.prop; no trial overlay.

That command exited 1 at an optional focus-field grep because
`dumpsys window windows` did not return the expected field. It did not
reach its network portion and is not reported as a complete check pass.
A separate corrected query at 13:15:56 CST used `dumpsys window` and
completed with exit 0: AT4K focused/resumed, power state Awake/display ON,
wlan0 still 192.168.31.164/24, Baidu ping 3/3.

Evidence: `rgsp_serial_exec_20260908_131520_115200.log` and
`rgsp_serial_exec_20260908_131556_115200.log` in `out/logs/uart/rgsp/`.
No key injection, service restart, settings change, reboot or suspend was
performed in these observations. The earlier crash buffer was not cleared;
its brief-format SHA-256 at the second sample is
`1a7bae97ed1709d7164307fa31bce10b9c023e89e3a8470172765c332357552d`.
This digest alone does not establish an absence of later app crashes.

These are endpoint observations over one boot, not a continuously
monitored 60-minute soak, explicit reconnect cycle, sleep/wake test or
cold-boot qualification. All remaining gates above stay open.

## Deployment Preparation Checkpoint

At 13:53 CST, the vendor-only Backup/Apply/Restore workflow and its
failure-recovery tests were prepared. Boot-only now has a separately
selected, exact-hash `codec` profile; its default frozen behavior remains.
Runtime checking adds three codec hashes only with `-Profile Codec`.
This supersedes the earlier statement that no candidate-aware helper
exists; it does NOT supersede the restrictions on the historical writer
or on using another TF1. No guard accepts arbitrary vendor hashes.

All 64 Python host tests and 18 PowerShell stream/identity tests pass.
Default Plan verified both local vendor image hashes without contacting
the handheld. The newly archived tools, limitations and physical procedure
are in `H700_ANDROID10_FIX72_CODEC_DEPLOYMENT_20260908.md`.

The subsequent read-only UART pre-removal check also passed: original TF1
boot/recovery/env, card identities, no marker, uptime 6013.86 seconds and
unchanged core PIDs. No shutdown, reboot, suspend or physical write occurred.
TF2 must now be moved to the computer AFTER normal shutdown for fresh
backup and offline p3 deployment. The backup and p3 Apply subsequently
completed at 23:20:42 with full candidate readback and protected-range
verification; system, data, ROMS and TF1 were not written. Persistent
device qualification is still pending until this TF2 returns to the
handheld and the normal boot/runtime checks pass.

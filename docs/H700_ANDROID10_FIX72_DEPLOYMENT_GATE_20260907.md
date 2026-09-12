# Fix72 Deployment Gate

Date: 2026-09-07, 23:33 CST. Device: current no-stick RGSP/H700.
Status: candidate flashed and first warm-boot runtime regression passed;
overall hardware/reproduction/startup acceptance remains open.

Later application gate: the frozen candidate's missing media codec catalog
causes WebView to crash. A reversible RAM-only catalog trial loaded Baidu
HTTPS successfully and was cleaned up. The source repair's vendor-only
build completed on 2026-09-08 at 13:01:38 CST; read-only fsck and the
three built XML hashes passed. It is not yet a persistent on-card fix.
See the hardware regression record for artifact hashes and deployment gates.

2026-09-08 13:14 CST: a separate offline vendor candidate was verified at
`out/rgsp-fix72-codec-candidate-20260908/`. It adds only the three codec XMLs
to the frozen baseline, preserving all existing content and extended
attributes. Candidate SHA-256:
`1e1c90ffdc6fc08e7e40d333d3fab4ea065c19a34df38b4a0889bcc83a8dc891`.
It has NOT been deployed. Existing writer/boot-only hash guards were not
changed or bypassed, and must not be used directly with this candidate.
The handheld still has the frozen vendor's missing-catalog defect.

2026-09-08 13:53 CST: a separate vendor-only deployment/restore wrapper is
host-tested; the boot helper now supports an explicit exact-hash codec
profile and the runtime checker its three extra files. No physical write
has been performed. Default Plan and 64 Python/18 PowerShell tests passed.
TF2 is now required in the computer after normal shutdown for a NEW backup.
See `H700_ANDROID10_FIX72_CODEC_DEPLOYMENT_20260908.md`. The historical
two-partition writer remains inappropriate for this narrow update.

2026-09-08 23:20 CST: the administrator-run vendor-only Apply completed
with readback verified. Only TF2 p3 was written; candidate SHA-256 is
`1e1c90ffdc6fc08e7e40d333d3fab4ea065c19a34df38b4a0889bcc83a8dc891`.
System, GPT, ANBOOT, data, ROMS and TF1 protected content verified unchanged.
No reboot was requested. Return TF2 to the original handheld for
`--check codec`, boot preparation and runtime/WebView qualification.

Latest checkpoint (2026-09-08, 11:02 CST): guarded p2/p3 write and readback
completed successfully. Hardware regression and independent startup remain
pending. The sections below retain earlier checkpoints for traceability.

Important later checkpoint (2026-09-08, 11:47 CST): the data journal command
exceeded the user's journal-only authorization because `-f` forced full
checking despite `journal_only`. Two free-space/inode counters were repaired.
Read-only fsck now passes, but this is NOT a successful journal-only-scope
operation. Replay is disabled, its RAM execution copy removed, and Android
has not been prepared or booted. See the incident outcome below.

Resumed checkpoint (2026-09-08, 12:27 CST): after the user's renewed
four-stage instruction, boot-only check and preparation both passed,
followed by a separately guarded warm reboot. All 17 runtime components,
active HOME/IME APKs and TF1 boot/env recovery checks passed. AT4K output
and Baidu HTTP access were verified. See
`H700_ANDROID10_FIX72_HARDWARE_REGRESSION_20260908.md`, including firmware
boot0 self-update evidence and the user's Y-key unlock correction.
No cold-boot, independent-startup or full hardware acceptance is implied.

## Priority And Scope

The user approved this sequence: freeze and regress a recoverable candidate,
qualify independent startup, cold boots and sustained operation, essential
hardware/application workflows, then polish AT4K.

AT4K APK/layout development and the separate RGSPLauncher are paused.
This session did not build, install, flash, reboot, change preferences, or
read network credentials. It queried the existing Android session over COM4.
The fixed Fix72 package predates the paused RGSPLauncher integration; current
Git HEAD must not be represented as the exact source of this older package.

## Host Checks

All seven artifact entries in
`out/rgsp-fix72-wifi-profile/DEPLOYMENT_MANIFEST.json` were checked again:
file lengths and SHA-256 hashes match, including CONTENT_CHECKS and the
retained filesystem-check reports.

- system.raw.img: 8589934592 bytes,
  `199c03bf5b46a81e26aab133d8310ae576690c99c926b1835d5f3e8ac3115faa`
- vendor.raw.img: 2147483648 bytes,
  `cb65140203807d0d80408e314f0c76554f2f81cd13fc76bf8ef07a4e46243c34`
- Both new `e2fsck -fn` runs returned 0, without mounting or modifying images.
- `python3 -m unittest discover -s tools -p 'test_rgsp*.py' -v`:
  21 tests passed under WSL, CPU 0, nice 19, idle I/O.
- D: free space was approximately 174.6 GB at this checkpoint.

Only Windows internal disks 0 and 1 were present. No USB TF2 reader was
available. Do not reuse the historical PhysicalDrive3 number.

## Live Pre-Upgrade Baseline

UART transcripts, retained locally:

- `out/logs/uart/rgsp/rgsp_serial_exec_20260907_233020_115200.log`
- `out/logs/uart/rgsp/rgsp_serial_exec_20260907_233128_115200.log`
- `out/logs/uart/rgsp/rgsp_serial_exec_20260907_233231_115200.log`

Observed:

- Android boot completed; product device `rgsp`.
- Uptime 43072.49 seconds, approximately 11 hours 58 minutes.
  This is a point-in-time uptime observation, not a monitored soak pass.
- Core PID snapshot: 1492, 1510, 1936 for the queried
  SurfaceFlinger/zygote/system_server set.
- TF2 p2 is the read-only system root, p3 read-only vendor, p4 read-write
  data, and p1 read-write `/rgsp-persist`.
- TF1 CID: `1d414455534400002000009f9401a1e7`.
- TF2 CID: `fe3432534400000020000005bc01896b`.
- TF1 boot and the Linux recovery image both match
  `d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5`.
- TF1 env first 128 KiB matches
  `d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396`.
- No pending `RGSP_ANDROID_TRY.ONCE` marker.
- wlan0 remains up with an IPv4 address; no new Internet/reconnect test.
- HOME resolves to AT4K; LeanbackIME remains selected. Launcher3 and
  LatinIME recovery packages are present.
- MemAvailable: 556020 kB. The bounded crash-buffer query returned no lines.
  Neither observation certifies absence of earlier crashes or memory issues.
- Battery service reports USB power and 100%; real fuel-gauge accuracy and
  charging behavior remain unqualified.

Compared with the 17 candidate CONTENT_CHECKS entries, 11 installed files
match: Mali module, keylayout, EGL, HWC, Wi-Fi module/firmware/init/HAL,
DocumentsUI and PackageInstaller. The graphics rc differs and must be
checked against the candidate after upgrade.

The five new system-side IME/profile files are absent. The currently active
data-side LeanbackIME APK matches the candidate APK:
`2a57b52cbac36d09138f7d94ba43f5d7fa9c4175966f7f1b43bb004b1a83ff18`.
Therefore the running system is not already the complete Fix72 candidate.

## Deployment Gates Still Open

1. Power off fully before moving TF2 to the PC reader. Never hot-remove the
   running system card. Keep TF1 in the device.
2. Reidentify the reader and all five partition GUIDs/offsets/sizes; check
   Linux recovery hash and pending boot marker. USB reader identity alone
   does not expose or prove the SD CID.
3. Take a NEW, verified backup of current GPT, ANBOOT, system and vendor.
   The earlier `out/tf2-deploy-20260907` backup predates Fix69/Fix70 live
   changes and is not a snapshot of this current working baseline.
4. Back up Android data privately before the first upgraded boot, for
   rollback of any package-manager/data changes. The existing guarded
   writer's Backup mode does not include p4; unchanged p4 during flashing
   is not the same as an available data rollback. Keep this backup outside
   Git and do not inspect or print stored credentials.
5. Use the guarded writer for p2/p3 only, with full readback and protected
   GPT/ANBOOT checks. Do not format p4/p5 or change U-Boot/environment.
6. Review a boot-only use of the verified Fix67 handoff before invoking it.
   The existing Fix67 wrapper invokes `prepare_h700_android10_b3_fix63_graphics.sh`,
   which mounts p2/p3/p4 read-write, reapplies deployment repairs, and runs
   repairing fsck. It is NOT a boot-only selector. Reusing it unchanged
   would invalidate a claim that the flashed candidate was tested unchanged.
   Preserve its CID/boot/env checks and Linux recovery behavior when
   separating boot preparation from image repairs. No new boot path was
   implemented or exercised in this session.
7. After protected startup, compare candidate component hashes, boot
   completion, GPU, HOME, IME and recovery apps; qualify Wi-Fi persistence,
   then the install/permission/app/HOME flow. Do not automatically run the
   opt-in firstboot apply helper over existing user choices.

The TF2 reader is the immediate physical prerequisite, not a failed flash.
Independent TF2 startup, ten cold starts, formal soak, hardware acceptance,
blank-data startup and two clean-build reproduction remain open.

## Reader Session Follow-Up

The user connected TF2 after the checkpoint above. Windows rediscovery found
the expected 125069950976-byte USB/GPT card at PhysicalDrive3, with all five
partition GUIDs and geometries matching. Reader slot 2 has no media. Neither
internal PC disk is a deployment target.

The guarded deployment helper now supports `-IncludeDataBackup`. Backup
locks p1/p2/p3 and optionally p4 before reading. A data-inclusive receipt
causes Write to validate the saved and live p4 hashes before writing and
validate live p4 again afterwards; p4 is never a write target. Requiring the
switch for Write rejects a receipt without the data snapshot.

Backup location: `out/tf2-fix72-deploy-20260907-current-v2/`.
The first attempt in the directory without `-v2` stopped before raw-device
access because Windows PowerShell 5.1 cannot measure hashtable keys with the
same Property syntax as PowerShell 7. The numeric summation was corrected
and checked in PowerShell 5.1. Both internal-disk negative tests stopped at
the identity gate. The unsuccessful attempt's logs remain retained.

New host checks:

- Old system and vendor snapshots pass read-only `e2fsck -fn`.
- Read-only file inventories found eight system entry changes: the IME,
  explicit profile helpers, their containing directories and graphics rc.
- The vendor inventory found only display-config directory ownership and
  whitespace in ueventd.rc; device rules and all driver binaries match.
- Reports: `system-vs-fix72.json` and `vendor-vs-fix72.json` in the backup
  directory. This inventory does not compare SELinux xattrs.
- The data backup is a private local recovery artifact ignored by Git;
  credentials are not inspected or copied into documentation.

## Boot-Only Entry

New source: `tools/prepare_rgsp_fix72_boot_only.sh`.

Default `--check` checks the original Linux root, both CIDs, TF1 boot/env,
recovery image, all five TF2 partition sizes/UUIDs, unmounted Android
partitions, read-only fsck, full candidate system/vendor hashes and pinned
boot inputs. It creates only temporary build files under `/run`.

Explicit `--prepare` additionally writes the same verified Fix67 boot image
to TF1 boot and creates the existing one-shot marker on TF2 p1. It does NOT
mount or repair system/vendor/data, rewrite U-Boot/env, select a new HOME,
run firstboot apply, or reboot automatically. Preparation failure after a
partial boot write attempts restoration and verification of original Linux.
If restoration fails, the script reports that UART recovery is required
and never automatically reboots. This cannot guarantee recovery from power
loss during a physical boot-partition write.

Local tests reconstruct the exact hardware-verified boot hash:
`c3745e62bf2e965d7f798c7f2fa851ab43e67bcb463998156a9ccdcc59d06662`.
The unchanged handoff restores Linux boot before entering Android.

Thirty host tests pass, including nine boot-only tests using temporary
regular files and command mocks. Cases include default check, explicit
prepare, mounted partitions, dirty filesystems, bad UUID/recovery image,
pending requests, partial writes and rollback failure. These tests do not
certify the new wrapper's physical-device execution.

Actual full backup completion, flashing, protected readback, any later
ANBOOT helper staging and device regression must be recorded below
separately as they finish.

## September 8 Reader Continuation

The full backup finished on September 7 at 23:54:55 with
`Backup.exitcode` content `0`. The midnight boot snapshot also has exit
code `0`. Both files are one byte long; their length is not their exit
code. The earlier conversational claim of a backup exit-code compatibility
bug was incorrect.

The original data snapshot remains unchanged:
`2d024b9cb43c42c4c86d9de50fe22314de18ae1f366015301dcbc1c5656a32b5`.
An earlier local attempt used `e2fsck -E journal_only -fy` on the separate
`data.journal-review.img`, never the original recovery snapshot or card.
It was initially described as journal-only; the later device incident
showed that `-f` overrides that limit. That experiment therefore does not
establish that pure journal replay alone resolves all discrepancies.
Its read-only `e2fsck -fn` was repeated on September 8 and returned 0.
This does not make the card's original data filesystem clean: the boot-only
wrapper still rejects a failing data fsck. Resolve and record that gate
separately before boot preparation; do not silently bypass it.

On September 8 the 30 host tests passed again using distro `Ubuntu`,
CPU 0, nice 19 and idle I/O. `Ubuntu-22.04` is not an installed distro;
the earlier test invocation with that name did not run the tests.

The original unelevated Write stopped before raw-device access. The next
elevated Write reached the live-content checks at 10:24 and stopped at
`anboot.img`, before any p2/p3 write. The GPT head matched. This is an
active integrity gate, not evidence that the candidate is defective or
that all remaining prewrite checks passed.

A fresh protected `BackupBoot` succeeded in
`out/tf2-fix72-boot-review-20260908-1026/`. GPT head and tail match the
original backup; ANBOOT SHA-256 is
`bcc1d8b58aec9ee39ad06b6c953b3f3ca1ef81b19f37fb4cb47cb2eb240716c7`.
Read-only FAT inventories compared with the original backup contain 572
entries each and zero changes. Raw metadata differences still require
review before this snapshot is used for another Write.

That review subsequently compared all 268435456 bytes against the midnight
snapshot: exactly one byte differs at zero-based offset 51568882,
`0x27 -> 0x28`. It is byte 18 (FAT last-access date) of the short directory
entry `INDEXE~1`; the date advances from September 7 to September 8, 2026.
No other raw bytes differ. The reviewed new boot snapshot was then supplied
to a new elevated Write; live GPT head and ANBOOT prewrite checks passed.

No successful Fix72 flash, hardware regression or independent startup is
claimed at this checkpoint.

The boot-only wrapper now reports `READONLY_FSCK_FAILED` with the failing
partition and original exit code, without attempting repair. A new dirty
data test verifies that all three fsck calls remain `-fn`, no boot write
occurs and no marker is created. All 31 host tests pass after this change.
The reconstructed boot image hash remains the pinned Fix67 value.

## Ordered Hardware Evidence

Keep these gates separate; host tests and a flashed image do not satisfy
physical-device acceptance.

1. After protected write/readback succeeds, move TF2 only with the handheld
   powered off. Keep the original TF1 installed and attach UART. Start
   original Linux, upload the reviewed boot-only helper, and run `--check`.
   If data fsck fails, retain the output and stop for a separately reviewed
   journal/recovery step. Do not run the older Fix63/Fix67 repair wrapper.
   Once all gates pass, prepare and boot once; compare all 17 candidate
   CONTENT_CHECKS, Android boot completion, mounts, GPU, AT4K HOME, selected
   IME, Launcher3/LatinIME fallback and restored TF1 boot/env hashes.
2. Qualify dual-card automatic entry separately from TF2-only startup.
   Neither is implemented by this one-shot wrapper. TF2-only needs physical
   boot-chain evidence without TF1; a running kernel seeing TF2 does not
   establish that the earlier boot stages can start from it. Do not persist
   experimental MMC probes into U-Boot env.
3. Record ten genuine power-off/cold-start cycles and a monitored 60-minute
   soak, not merely reboot commands or one uptime snapshot. Record settings
   before/after boot and Wi-Fi reconnect tests. Use DNS and access to
   `www.baidu.com` on the handheld for Internet testing; failure to reach
   Google without a proxy is not by itself a Wi-Fi failure. Never log PSKs.
4. Test audible output and volume, shutdown, suspend/wake, and a complete
   physical DPAD/ABXY install, permission, launch, back and HOME sequence.
   Shell-driven install or injected key events alone do not establish that
   a user can complete the physical-button workflow.

Two clean-build reproductions, blank-data first boot and formal rollback
exercise also remain open. Preserve AT4K and do not resume layout redesign
before these system-level gates.

## Guarded Write Completed

The elevated Write completed on September 8 at 11:02:50 UTC+08:00.
Both the process exit code and `Write.exitcode` are `0`;
the transcript ends with `TF2_WRITE_READBACK_OK`.

Receipt: `out/tf2-fix72-deploy-20260907-current-v2/write.json`.

- Only TF2 p2/system and p3/vendor were written.
- Full system readback matches
  `199c03bf5b46a81e26aab133d8310ae576690c99c926b1835d5f3e8ac3115faa`.
- Full vendor readback matches
  `cb65140203807d0d80408e314f0c76554f2f81cd13fc76bf8ef07a4e46243c34`.
- GPT head/tail and reviewed ANBOOT passed the postwrite hash checks.
- Full 16 GiB p4 data matched the original recovery snapshot before AND
  after writing. Receipt field `data_hash_verified` is `true`.
- ROM/p5 was not written; a full ROM content hash was not collected.
- TF1, U-Boot and env were not accessed by the PC writer.
- The writer exited and released its handles. An elevated storage rescan
  returned 0 after an unelevated rescan was refused by Windows.

The next prerequisite is physical: safely eject TF2, return it to the
powered-off handheld while retaining TF1, and reconnect UART for original
Linux checks. No new helper was staged onto ANBOOT, no data journal replay
was performed on the card, and no handheld boot/reboot was initiated here.
The Fix72 hardware regression gate, clean-build reproduction, startup
qualification and subsequent hardware/button acceptance are still open.

## First Postwrite Device Check

On September 8 at 11:08 the user had returned TF2 to the handheld.
COM4 reached original Ubuntu 22.04/Linux 4.9.170 as root.
Root is TF1 `/dev/mmcblk0p5`; TF2 p1 is mounted at `/mnt/sdcard`.
Both CIDs match the pinned card identities. Android p2/p3/p4 are unmounted.
No reboot or partition repair was requested by the serial commands.

Device-side hashes match the original TF1 boot, Linux recovery image and
TF1 env prefix. No pending one-shot boot marker exists.
Device `e2fsck` version is 1.46.5. Read-only checks returned:

- system/p2: 0.
- vendor/p3: 0.
- data/p4: 4, with journal recovery skipped in read-only mode and the same
  orphan/bitmap/free-count discrepancies observed in the raw backup.

UART records:
`out/logs/uart/rgsp/rgsp_serial_exec_20260908_110825_115200.log` and
`out/logs/uart/rgsp/rgsp_serial_exec_20260908_110847_115200.log`.
The second diagnostic shell command ends with an echo and returns 0;
its explicit per-filesystem `FSCK_EXIT=4` is the data result, not a pass.

The next proposed operation is only journal replay on data, followed by a
read-only full fsck. This modifies data and is awaiting explicit user
confirmation. The original host recovery snapshot must remain unchanged.
Do not perform a general repairing fsck, format data, or prepare/reboot
Android while this gate remains open.

## Second RGSP Test Boundary

The user next allowed checking and proposed moving TF2 to another RGSP
whose TF1 is completely stock. Only read-only device checks were performed
at this checkpoint; journal replay was not treated as authorized by the
word "checking".

At 11:17, the original device still matched both pinned CIDs. All three
Android partitions remained unmounted, their PARTUUIDs matched, the base
boot and Fix67 ramdisk file hashes matched, and no one-shot marker existed.
Data still advertises `needs_recovery`. Its separate superblock state field
says `clean`; that field alone does not override the pending journal or
the preceding fsck exit 4.
UART: `out/logs/uart/rgsp/rgsp_serial_exec_20260908_111718_115200.log`.

The pinned Fix67 ramdisk was inspected read-only with the existing
`tools/patch_ramdisk.py` newc parser. Its actual top-level init:

- Hardcodes TF2 devices as `/dev/mmcblk1p1` through `p4`.
- Requires TF1 boot `/dev/mmcblk0p4`.
- Writes the pinned original-device Linux boot recovery image to TF1
  before consuming the one-shot marker.
- Does not itself check the new TF1 CID before that restoration write.

The host preparation wrapper separately checks the original TF1 CID and
boot/env hashes. Do not remove these guards or manually launch this ramdisk
on a different stock TF1. The recovery image must not be assumed correct
for another card solely because the handheld model is the same.

Testing with a stock TF1 present is a dual-card entry test, not proof of
TF2-only boot. Testing with TF1 physically absent is the separate boot-chain
qualification. Neither mode has been implemented/qualified by this fixed
one-shot package. Preserve the second stock TF1 unchanged; its identity,
layout and boot-chain evidence must be collected independently before
considering any preparation for that device.

## Journal Replay Attempt (Superseded)

The user explicitly authorized only data journal replay. This does not
authorize general repairing fsck, formatting, TF1 preparation, or reboot.

The initial `tools/replay_rgsp_data_journal.sh` had default `--check` and
explicit `--replay`. Guards verify original Linux root, both pinned CIDs,
data size/PARTUUID/filesystem UUID/type, external power, unmounted data,
TF1 boot/env hashes and the full original data preimage hash. Identity,
power and mount state are checked again immediately before replay.
The host must independently reverify the original recovery backup first;
that full size/hash verification succeeded in this session.

The intended limited invocation was `e2fsck -E journal_only -fy` on data.
The assumption that this combination remains journal-only was incorrect.
It is followed by `e2fsck -fn`, a pending-journal flag check and TF1
boot/env hash checks. Replay errors, readonly-check errors or a remaining
`needs_recovery` flag stop the script, without general repair or reboot.
A changed data preimage also prevents blind repeat execution.

Six mock tests were added for read-only default, explicit replay, wrong
identity/preimage, mounted/unknown mount state and error handling. All 37
host tests pass; `sh -n` also passes. These are host tests, not proof of the
device-side operation's outcome.

The script was staged only in tmpfs as
`/run/rgsp-data-journal-20260908.sh`, not on either card. Its SHA-256 was
verified before execution:
`34d6af0afdfb1db2c15cfe5c0a456652cf340b08e7998a336ef832029663289b`.
UART execution started at 11:26:58 with a full 16 GiB preimage hash.
Expected transcript:
`out/logs/uart/rgsp/rgsp_serial_exec_20260908_112658_115200.log`.
At this checkpoint completion is not yet claimed; wait for the actual
remote end marker. A lost host/serial connection would not prove the
device-side operation stopped and must not trigger an automatic retry.

## Journal Operation Outcome And Scope Violation

The UART command completed at 11:39:01 with remote exit 0, but its actual
behavior exceeded the authorized journal-only scope. The complete live
data preimage matched the original host backup before any repair.
Then `e2fsck -E journal_only -fy` replayed the journal AND ran all five
checking passes. The output shows two additional affirmative repairs:

- Free blocks: 4059578 changed to 4058875.
- Free inodes: 1046095 changed to 1045994.

The repairing invocation returned 1. The separate `e2fsck -fn` returned 0,
with 2582 files and 135429 used blocks. The journal recovery flag cleared.
These healthy post-checks do not negate the scope violation, and the old
`DATA_JOURNAL_REPLAY_VERIFIED` marker must not be used as evidence that the
operation respected journal-only limits.

The upstream e2fsprogs 1.46.5 `e2fsck/unix.c` function `check_if_skip()`
tests FORCE before its JOURNAL_ONLY early-exit condition. The initial mock
tests merely assumed the combined command was journal-only and failed to
test the tool's actual option precedence. This was an implementation and
validation error, not a user-authorized general repair.

Containment and verification:

- No further partition repairs, automatic rollback, boot preparation or
  reboot were performed.
- TF1 boot/env post-check hashes matched their pinned originals.
- A separate read-only device query at 11:44 confirmed data remains
  unmounted, its filesystem UUID/PARTUUID are unchanged, and there is no
  pending one-shot boot request. No formatting command was run.
- Original `data.before.img` and the verified recovery set remain intact.
  No application/settings-preservation claim is made before user-facing
  regression.
- The executed script is retained for audit as
  `out/tf2-fix72-deploy-20260907-current-v2/replay-data-journal-executed-20260908.sh`
  with SHA-256 `34d6af0afdfb1db2c15cfe5c0a456652cf340b08e7998a336ef832029663289b`.
- Current source rejects `--replay` with exit 3 before any probes and
  contains no e2fsck invocation. Its remaining `--check` is only a
  comparison against the ORIGINAL preimage and will reject changed data.
- The hash-verified execution copy was removed from `/run` at 11:47.
- All 38 host tests pass, including a real e2fsprogs test on a disposable
  64 MiB regular-file image that reproduces FORCE overriding JOURNAL_ONLY.
  That test does not qualify any replacement write/replay procedure.

Additional UART evidence:
`out/logs/uart/rgsp/rgsp_serial_exec_20260908_114443_115200.log` and
`out/logs/uart/rgsp/rgsp_serial_exec_20260908_114725_115200.log`.
The user was notified of the excess repairs immediately after the result
was observed. Further device writes/boot actions are paused, not inferred
from the earlier journal-only authorization.

## Ordered Continuation Authorized

The user's subsequent instruction explicitly resumes candidate regression,
startup qualification, persistence/stability, and hardware/button workflows.
This supersedes the pause above, not the incident record. No further data
repair is planned; preserve the original recovery images unchanged.

The boot-only helper now rechecks card/root/power identity, mount state,
TF1 boot/env/recovery hashes and marker absence after the lengthy content
verification and immediately before preparation writes. Unknown mount status
fails closed. All 40 host tests pass, including loss-of-power-after-build
and unknown-mount cases. Host tests do not replace hardware acceptance.

The helper was staged only under `/run`, SHA-256:
`f47678e6c08db80aeb66e63dfb0b1bdd6e42ec6c072faa9e2bfe4c0282a35307`.
The real `--check` completed successfully: all three read-only fscks passed,
complete system/vendor hashes matched, and the reconstructed boot matched
the pinned Fix67 handoff. Evidence:
`out/logs/uart/rgsp/rgsp_serial_exec_20260908_115403_115200.log`.

At 12:02:58 the same hash-verified helper was invoked with `--prepare`.
It repeats all checks before writing TF1 p4 and TF2 p1's one-shot marker.
It does not reboot, write env, or repair/write Android p2/p3/p4. Preparation
completion is pending at this checkpoint. Evidence will be retained at:
`out/logs/uart/rgsp/rgsp_serial_exec_20260908_120258_115200.log`.

That preparation subsequently returned `FIX72_BOOT_ONLY_PREPARED`, exit 0.
The separate warm boot, runtime verification and latest pending gates are
recorded in `H700_ANDROID10_FIX72_HARDWARE_REGRESSION_20260908.md`.
The user is currently away from the handheld. Preserve the running AT4K
session and wait for physical cooperation before power-off/card-move tests.

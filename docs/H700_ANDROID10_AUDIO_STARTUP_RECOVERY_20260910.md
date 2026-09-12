# Audio-Preserving Startup Recovery

Date: September 10, 2026, UTC+08:00.

## Authorization

The user explicitly authorized repairing the current startup issue and
entering Android for testing while preserving the deployed audio fix, and
appropriate D-drive cleanup. The workflow includes fresh complete data
backup, offline recovery validation, qualified p4 recovery, guarded TF1
one-shot startup and Android tests. It excludes formatting, historical
data-delta replay and replacement of the audio vendor.

Intent receipt:
`out/rgsp-audio-startup-recovery-20260910/authorization-and-intent.json`,
SHA256 `f4a468cbe6ad3bee533ebeeaa3180f4b47b9e0175154ee0846190bd610e4e2892`.
This is authorization, not evidence of completion.

## Entry State

Original Linux boot ID `d8ef7030-9213-4f29-b674-cd8ef8d1e685`, both pinned
card CIDs, USB power, p4 unmounted and no boot marker were reconfirmed.
The current p4 has pending journal recovery. P1 unmounted FAT and p2/p3
read-only filesystem checks passed in the preceding return check.

The SSH service was initially inactive. It was started temporarily without
enabling boot startup. Existing ed25519 host key matches the COM4 reading
and strict known-host entry. The capture helper was copied only to `/run`,
with SHA256 `7c0c7d5e6a2d0bd856a81bde118d2b55f52909182a30060008b7ab45d2d4c039`.
SSH must be returned to inactive after the recovery transfer work.

## Disk Cleanup

D initially had 74808393728 bytes free. Three historical 16 GiB expanded
data images were selected for lossless gzip archival, NOT deletion of
their only remaining data:

- `out/tf2-fix72-deploy-20260907-current-v2/data.before.img`
- `out/tf2-fix72-deploy-20260907-current-v2/data.journal-review.img`
- `out/tf2-data-backup-20260909-2359/offline-journal-trial/data.journal-replayed.img`

Archives are stored alongside their originals with suffix
`.archived-20260910.gz` and full-verification `.json` receipts.
The archiver verifies the complete decompressed size and SHA256. The
separate native PowerShell remover validates absolute workspace paths,
rejects reparse/tracked paths, rehashes the current raw images and retained
archives, and deletes only those explicit regular files. It never deletes
directories recursively. Prior documentation referring to these raw paths
can use the verified gzip archives for reconstruction after cleanup.

Current audio/codec/frozen candidates, current vendor rollback, latest p1
backup/repair evidence, historical compressed data backup and historical
qualified final data candidate are retained.

Cleanup completed in two native PowerShell batches at 12:40:25 and 12:43:40,
removing only the three verified expanded files (48 GiB logical total).
Retained archive raw hashes exactly match each deleted file. D had
126198800384 bytes free after the final batch, while the new backup was
already receiving compressed data. Receipts:
`out/cleanup-archived-data-20260910-124024.json` and
`out/cleanup-archived-data-20260910-124339.json`.
Do not repeat cleanup against these now-absent raw paths.

## Recovery Tooling

Planned fresh backup directory:
`out/tf2-data-backup-audio-20260910/`.
The unchanged capture helper retains its 80 GiB reserve and complete
two-source-read plus host-decompression verification requirements.

The copy analyzer now reads in 4 MiB batches while preserving exact 4 KiB
diff records; nine tests including real readonly loop mounts passed.
The existing data delta writer/collector retain their legacy defaults and
add an explicit hash-checked Audio recovery profile. This profile must be
derived from the NEW qualified copy before use. It selects exact image and
manifest hashes, block count and header counts, and checks the unchanged
audio vendor before and after recovery. No current profile or bundle is
qualified merely by adding this code.

Validation so far: four capture tests, nine copy tests, sixteen delta tests
(including the root loop-device integration test), seven collector tests,
and six new Audio profile tests passed.

An additional collector test now covers the complete Audio vendor
preflight-read progress before the authorized-start event. Eight collector
tests pass; incomplete/foreign progress or mismatched profile hashes fail.

## Current Backup

Fresh capture started at device 12:40:58 using the unchanged capture recipe
and strict SSH host-key verification. Source identity is the current boot
and card pair, p4 unmounted, 17179869184 bytes. The archive and progress log
are under `out/tf2-data-backup-audio-20260910/`.
At 12:44 the stream had passed 4 GiB. Completion still requires the second
complete device hash, host decompressed hash/size/CRC and final `capture.json`.

The first complete read subsequently finished with raw SHA256
`6993797e1b7927d805211b7c750ec3383fe7488f1ca0e6cb93554b7e97ef7355`.
At 13:02:43 the second independent read had reached offset 13365149696.
Device process I/O checks reported zero written bytes. The backup is not
qualified until the final receipt exists. A bounded host waiter will start
the root-only local-copy analyzer only after that receipt appears.
Both counter-correction tests passed, including rejection of unexpected
diagnostics; this does not imply the current data needs counter correction.

## Verified Backup And Offline Findings

Fresh capture completed at 13:05:46. Both full device reads and the host
decompressed hash/size/CRC agree on the raw hash above. Compressed size is
481430539 bytes, SHA256
`25d797aab69c822d6631609aaddd22fe96c9f9183bc9011e7a2f7420f14544a3`.
The immutable receipt is `capture.json` under the fresh backup directory.

Journal-only replay on the regular host copy completed at 13:14:31.
Subsequent strict readonly checking correctly rejected precisely two
remaining counter diagnostics: free blocks 4058631 versus counted 3976937,
and free inodes 1045965 versus counted 1045080. The recovery flag is gone;
no other diagnostics appeared in the five passes. No full repair or
physical partition write was attempted.

The counter-copy helper now independently records a readonly source
inventory when the journal analyzer stops before producing one. Existing
journal inventories, when present, must match. Four tests pass, including
missing-inventory handling and mismatch rejection. Original journal-stage
failure evidence is retained unchanged. The helper is creating a second
regular copy, with the 80 GiB reserve gate unchanged.

Review of the original and post-journal inventories found 13 changed
entries, confined to screen-on time, usage statistics, app-idle statistics
and their directories. No entries were removed. The new screen-on-time
backup has the old file's content hash. QQ Music, X-plore, AT4K and
LeanbackIME APKs, package settings and secure settings are unchanged.
Final counter-corrected inventory and complete block comparison remain
required before deployment qualification.

## Verified Physical Recovery

The preceding session completed the new recovery at 14:06:47 and collected
its receipt at 14:08:52. Evidence:
`out/tf2-data-backup-audio-20260910/deployment-audio-20260910-1332/physical-recovery-result.json`.
The matching device RAM log and complete reconstructed transcript are
retained alongside it. The receipt reports
`PHYSICAL_P4_RECOVERY_VERIFIED`, exactly 19 written 4096-byte blocks on
TF2 p4, full 17179869184-byte readback SHA256
`ecd96eed74ab31a213c127555613bcc37f5203a2546f25d5866f36a3ca7d7a1c`,
and a successful strict read-only filesystem check. Protected TF1 boot,
environment and complete audio vendor hashes matched. Data was unmounted
and no one-shot marker existed at completion.

This is the NEW audio recovery bundle, not the historical 24-block bundle.
The collector receipt explicitly records
`device_ram_log_hash_independently_checked: false`; do not describe that
optional independent check as completed.

## Session Handoff And Startup Retry

The original thread stopped after a 420-second UART timeout during
`--check audio`, started at 14:15:05. Its transcript ends during complete
system/vendor hashing and contains no success marker. This host timeout
does not establish a failed recovery or a completed boot preparation.

At 16:50-16:51 the replacement thread independently checked live SSH and
COM4: the same Linux boot ID and pinned card pair remain, USB power is
online, p2/p3/p4 are unmounted, no old prepare/hash/deploy process remains,
and no one-shot marker exists. P4 is clean without `needs_recovery`,
with free block/inode counts 3976937/1045080. The device `/run` boot helper
matches the local SHA256
`44984c390469bbf2cb84f09990d6bbf5277921fbd4c192858dba4024420428ac`.
Twenty boot-only tests and the Frozen/Codec/Audio runtime profile tests
passed again. D has approximately 88.23 GiB free; no further cleanup was
performed by the replacement thread.

At 16:52:01 the unchanged guarded helper began `--prepare audio`, with
a 1200-second UART timeout and the prior authorization still in scope.
All three strict read-only filesystem checks passed; full system/vendor
hashing then began. Evidence is under `out/rgsp-audio-resume-20260910/`.
The command subsequently returned `FIX72_BOOT_ONLY_CHECK_OK`,
`FIX72_BOOT_ONLY_PREPARED` and exit 0. Full system/audio vendor hashes
passed, and the 64 MiB TF1 p4 handoff write was fully read back. This
preparation did not write system/vendor/data.

At 17:09:11 independent UART gates reconfirmed the pinned card pair,
power, handoff boot hash, original Linux recovery-file/environment hashes,
exact one-shot marker and unmounted p2/p3/p4. The temporarily enabled SSH
service was stopped and confirmed inactive. TF1's first 4 MiB hash before
reboot was
`d34a52b70096df14e43aae719373bac16d9ec8dddc13889d3431bc87b1631682`.

Normal reboot was requested at approximately 17:09:23 with continuous
capture at
`out/logs/uart/rgsp/rgsp_uart_fix36_20260910_170923_115200.log`.
The legacy capture filename does not identify the candidate version.
Linux again reported failure to unmount `/mnt/vendor`; firmware again
reported DRAM retraining failures followed by success and a passing memory
test, then its own backup/main SPL writes and `update boot0 success`.
These remain unresolved observations, not clean hardware acceptance.
Android's UART shell appeared; runtime and playback acceptance follow
separately.

## Android Runtime And Playback

At 17:12 the full `check_rgsp_fix72_runtime.ps1 -Profile Audio` passed.
Evidence: `out/logs/uart/rgsp-fix72-runtime-20260910_171239/`.
Android boot ID is `89a3c7ad-f1b9-4c39-8469-67f8659a1509`.
All 23 component hashes matched, system/vendor were read-only, data was
read-write, p1 was mounted, and codec/audio paths had no temporary
overlays. Card-0 control/playback nodes were already system:audio 0660,
without a live permission repair or service restart. Original TF1 p4,
recovery file and environment hashes passed; the marker was consumed.
AT4K HOME, LeanbackIME and both active APK hashes were retained, with
firstboot still not-applied and the crash buffer empty.

The first 4 MiB of TF1 now hashes to
`d156143e3e800bb36b9936bd7612e86c2b1bb71003bda7dae7de58cdba66aa1a`,
different from the pre-reboot sample. Firmware logged boot0 writes, so
the successful p4/env checks must not be called an unchanged whole TF1.
Wi-Fi automatically reconnected at 192.168.31.164/24. The sampled kernel
log contained no `FAT-fs (mmcblk1p1)` lines.

The earlier temporary tone JAR was absent; the diagnostic command stopped
at that missing-file check, without playing audio. The existing local
1953-byte JAR was then uploaded to a new `/data/local/tmp` path and its
full device SHA256 checked:
`17622f0fce02ffb6c1e246d45df6dfa3e995f346fe24c0d3c4f9cb623c61d6c9`.
At 17:14:23 its two-second low-amplitude probe drained all 96000 frames
at the retained media volume 3/15. Audio HAL/audioserver PIDs stayed
1495/1503 and the crash buffer remained empty.

A generic LEANBACK launch intent failed despite package resolution.
The explicit resolved component
`com.tencent.qqmusictv/.app.activity.AppStarterActivity` launched
successfully at 17:16. No login, purchase, install, grant or key remapping
was performed. The verified UI XML is `qqmusic-open.xml` in the resume
directory. The first screenshot (`qqmusic.png`) shows the prior desktop,
not a successful QQ launch. The subsequent QQ screenshot transfer was
rejected because kernel messages interrupted its base64 stream; no
visually verified QQ screenshot is claimed.

At 17:28-17:29 QQ Music had an active playing session, and AudioFlinger
showed its PID 4011 active on `AUDIO_DEVICE_OUT_SPEAKER`. Two PCM samples
about three seconds apart were RUNNING with hardware pointers
37114368 and 37260544. Media volume was still 3/15, with non-muted track
gain reported. At uptime 1181.78 seconds, audio HAL/audioserver and
SurfaceFlinger/zygote/system_server PIDs remained
1495/1503 and 1507/1532/1942 respectively. Crash buffer and sampled p1
FAT diagnostics remained empty.

Playback evidence:
`out/rgsp-audio-resume-20260910/rgsp_serial_exec_20260910_171423_115200.log`,
`rgsp_serial_exec_20260910_172829_115200.log`, and
`rgsp_serial_exec_20260910_172909_115200.log`.
The device is left running QQ Music for user audible confirmation.
Software playback and persistent startup have passed this warm-boot
sample; acoustic output has not yet been confirmed by the user.

## Completion Boundary

The fresh backup and new 19-block physical recovery are verified.
Never replay either recovery bundle after a subsequent Android boot has
changed data. Preserve audio vendor SHA256
`9d0c8d4a95b69131a70db6aebdfa1d9b3967afa9dc7dc8e95932872ecb372cc2`.
The underlying cause of repeated unclean shutdown state, cold boot,
independent TF2 boot and audible application playback remain separate
acceptance items. This approximately 20-minute runtime sample is not the
formal 60-minute soak or a physical-button-only application workflow.

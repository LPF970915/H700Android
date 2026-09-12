# Fix72 Data Backup And Offline Recovery

Timestamps in this document use UTC+08:00 unless explicitly marked UTC.
The backup started on September 9 at 23:59 and continued after midnight.
Scope: preserve current TF2 p4 and test a NEW regular-file copy only.
Physical data recovery has not been authorized or performed in this step.

## Source And Transfer

The original handheld remained in TF1 Linux with the pinned TF1/TF2 CIDs,
USB power online, and TF2 p4 unmounted. Its ext4 UUID is
`45daaa6e-724e-4d20-981c-602b3f72b8a2`, PARTUUID
`734716ed-e7d9-e74f-9b3e-4f1cb8d448ed`, length 17179869184 bytes.

The existing SSH service was initially inactive. It was started temporarily,
without enabling startup or changing sshd configuration. The existing
ed25519 host key was checked against the public key obtained through COM4;
the transfer uses strict known-host verification, not an accept-any policy.
No new persistent SSH key or account was created.

`tools/capture_rgsp_data_readonly.py` was uploaded to tmpfs `/run` and its
hash checked before execution. It opens only the fixed p4 path with
`O_RDONLY|O_NOFOLLOW`, validates root/card/partition/power/mount identity,
compresses ALL bytes including free space, and calculates the raw hash.
It then seeks back and independently re-reads the source to verify the
hash and identity again. The host checks gzip integrity, expanded length
and hash, and compressed-file readback before writing the success receipt.
It neither mounts data nor repairs/replays its journal.

Output: `out/tf2-data-backup-20260909-2359/`.
The compressed backup is `data.before.img.gz`; progress and source receipt
are in `device-capture.jsonl`. Only `capture.json` with status
`HOST_ARCHIVE_AND_SOURCE_VERIFIED` establishes backup completion.
A partial archive or a transfer-phase hash is not sufficient.

The stream-phase raw hash was
`6eeea7bf7a5cd0b95c0540f378d290326805ff1c4feab95b52f3ffe9aa4b29ea`.
At 00:17:59, the independent re-read was still in progress at byte
9784262656; there was no success receipt yet.
UART evidence: `out/logs/uart/rgsp/rgsp_serial_exec_20260910_001759_115200.log`.

Backup subsequently completed at 00:23:26. Both source reads and the
host-expanded 17179869184 bytes matched the raw hash above.
The archive is 173429842 bytes, SHA-256
`a344cca509f29209add7e5378ab2bf590b31c25d964980768f76f2baa4a8b07a`.
Receipt: `out/tf2-data-backup-20260909-2359/capture.json`.
The executed capture recipe SHA-256 is
`7c0c7d5e6a2d0bd856a81bde118d2b55f52909182a30060008b7ab45d2d4c039`.

At 00:51:53, SSH was returned to inactive. UART confirmed p4 still
unmounted, unchanged boot ID, original TF1 p4/env hashes, and no boot
marker. Evidence:
`out/logs/uart/rgsp/rgsp_serial_exec_20260910_005153_115200.log`.

## Offline Procedure

`tools/analyze_rgsp_data_copy.py` requires the verified capture receipt,
compressed hash, exact size, and new output directory. It creates one
new working image and checks its full raw hash against the source.
The original compressed backup is never the writable target.

Before and after inventory uses a local regular-file loop mount with
`ro,noload,nodev,nosuid,noexec`, including file hashes, types, ownership,
modes, size/link counts, mtime/ctime and extended attributes. It checks
the image hash around read-only operations and unmounts before replay.

The only modifying experiment is:

```sh
e2fsck -E journal_only -y <new-local-copy>
```

No `-f`, physical path, format, or general repairing fsck is accepted.
Its complete output is retained and any full checking pass or unexpected
exit code prevents qualification. A separate `e2fsck -fn` plus explicit
header check must show no pending recovery and a clean state afterward.
The complete before/after 4096-byte block and file inventories are compared.

Host e2fsck is 1.47.0; device e2fsck is 1.46.5. The host copy result is
not a qualification of executing the same command on the handheld.
The historical device replay helper stays disabled.

## Journal-Only Result: Not Qualified

On the first local working copy, journal-only returned 0 and cleared
pending recovery. However, the subsequent `e2fsck -fn` still reported:

- Free blocks: 4058624, counted 4058631.
- Free inodes: 1045964, counted 1045965.

That check also returned 0 despite these diagnostics. A clean header and
zero exit code therefore remained insufficient even after clearing
`needs_recovery`. The analyzer was stopped during read-only block
comparison; it produced no successful `result.json`. No physical device
was involved in the experiment.

The executed analyzer is retained in the first trial directory as
`analyze-executed-before-diagnostic-guard.py`, SHA-256
`acc28ee8d9e909ad9964c2db0864f23d640512df380b5fb26806f95f328b2fe9`.
Both current host and boot checks now require all five read-only passes
and explicitly reject diagnostic questions/warnings/count errors even
when exit status is zero. The boot helper also retains its recovery-bit
gate. The revised host helpers and guards passed 40 tests, including
real-file counter corruption and correction tests.

Journal replay changed 13 file/directory inventory entries: six regular
file contents, six directories' metadata, and one file's timestamps.
These include runtime profile and usage/screen-time records. This is
not a claim that journal replay is byte-preserving for application data.
Complete before/after hashes and metadata are retained under
`offline-journal-trial/`; file contents are not published in this document.

## Separate Counter-Only Experiment

`tools/prepare_rgsp_data_counter_copy.py` creates a SECOND regular-file
copy and never overwrites the original archive or first replay copy.
It accepts exactly the two known counter diagnostics and rejects other
issues. Only `debugfs set_super_value` for `free_blocks_count` and
`free_inodes_count` may modify this second copy. It does not run a general
repairing fsck.

The second copy must pass explicit header and diagnostic checks, retain
exactly the first replay copy's full file inventory, and undergo a full
block comparison against the original compressed backup. Only its own
`offline-counter-trial/result.json` can establish success. This experiment
extends the offline study beyond journal replay alone; it does not extend
the scope of permitted writes to the physical handheld.

At entry, D: had about 107 GiB free. No Android build was started.
Backup and copy tools retain an 80 GiB reserve and check worst-case
allocation headroom; neither deletes historical recovery evidence.

## Verified Offline Candidate

The second trial completed at 01:30:04 on September 10, 2026.
Receipt: `out/tf2-data-backup-20260909-2359/offline-counter-trial/result.json`.
Status: `OFFLINE_RECOVERY_VERIFIED_NOT_DEPLOYED`.

- Original raw SHA-256:
  `6eeea7bf7a5cd0b95c0540f378d290326805ff1c4feab95b52f3ffe9aa4b29ea`.
- Retained journal-only copy SHA-256:
  `dfedcab7f6bb187f23a25be4e6699e020bf72edfcc9813990d473bcff23ff448`.
- Final candidate SHA-256:
  `b52bb83ef4c42a7cf6705526bd0f923a921f938e7a579621d9b23381832345a9`.
- All images represent exactly 17179869184 bytes.
- Counter-only changes: free blocks 4058624 -> 4058631, free inodes
  1045964 -> 1045965. No general repairing fsck was run.
- Final `e2fsck -fn`: all five passes, exit 0, no counter errors or
  repair questions. Summary: 2611 allocated inodes, 135673 used blocks.
- Header: original UUID, clean state, no `needs_recovery`.
- All 2602 file/directory inventory entries equal the journal-only copy.
  Counter correction introduced no additional file/inventory changes.
- The complete final image differs from the original archive in 24
  4096-byte blocks (98304 bytes covered by these blocks). This is a
  changed-block span, not a count of individual changed bytes.
  Per-block hashes and offsets are retained in `block-diff.json`.
- Final comparison reconfirmed the original expanded hash and unchanged
  compressed archive hash.

Both trial copies and the original archive are retained. No physical
deployment helper was executed. Host free space after the copies was
about 82.55 GiB, above this experiment's reserve; Android builds remain
paused under the project's separate build-space rules.

Source/test snapshots and hashes are in `recovery-tools-20260910/` under
the backup directory. The host helpers/guards passed 40 tests, including
the real ext4 counter-only correction. Existing historical errors and the
rejected journal-only trial remain available; no logs were cleared.

The newest boot helper was staged only in RAM at
`/run/prepare_rgsp_fix72_boot_only_diagnostics.sh`, SHA-256
`5351083c4f6c426002459207b7764b05b0d7184b20c1a474f8ea02057fbb4ccf`.
Its real read-only check correctly stopped at the ORIGINAL device data's
pending recovery state. Evidence:
`out/logs/uart/rgsp/rgsp_serial_exec_20260910_012149_115200.log`.
Do not use older on-card or RAM helpers to bypass the updated gate.

At 01:31:09, UART reconfirmed original card CIDs/boot ID and external
power, unmounted data, inactive SSH, no boot marker, unchanged TF1
Linux boot/env hashes, and zero TF2 p1 FAT error lines in the current
kernel buffer. Physical data still had its ORIGINAL recovery flag and
counters. Evidence:
`out/logs/uart/rgsp/rgsp_serial_exec_20260910_013109_115200.log`.

## Completion Boundary

Do not infer physical recovery from an offline result. Review the retained
file/block differences and choose a separately authorized, verified
physical operation only after the current backup and copy experiment pass.
Keep the original Linux boot/env and one-shot marker gate intact.

## Authorized Physical Deployment

At 02:13 on September 10, the user's "allow, continue to the next step"
authorization was recorded for ONLY the qualified TF2 p4 recovery.
Other partitions, boot preparation, reboot and formatting remain excluded.
Historical offline receipts above are unchanged.

Evidence directory:
`out/tf2-data-backup-20260909-2359/deployment-20260910-0211/`.
The host authorization/intent receipt was flushed before dispatch; its SHA:
`f5198de932a2700f8a3db9236ff34bd0a62730975c7156a0aefe90c66ffdb7ab`.
This receipt records authorization and intent, NOT completion.

`tools/deploy_rgsp_data_delta.py` was independently checked against the
complete original gzip and candidate image, reconfirming both full hashes
and the exact 24-block manifest. The compressed bundle includes all before
and after bytes and is archived on the host. Its SHA:
`e36bd4238f0a444cc83acd752f711bcea6000f646c49af62cc1b71b95a98ed96`.
Executed script SHA:
`fb22b7a3341dec7a07ea4407b1007428e0ba8b94814ba4ddfb16db9de0bc8d32`.
Both files were staged only under `/run` (tmpfs), not on either card.

The script defaults to read-only preflight; explicit authorized apply
requires pinned device identity, geometry, external power, unmounted p4,
original boot/env hashes, no marker, exact per-block preimages and a
complete live ORIGINAL hash before any byte write. It holds an exclusive
partition descriptor, never a whole-card writable descriptor. The block
containing the primary superblock is written last; this is NOT proof of
power-loss atomicity. Each write is synced and checked. After all writes,
the partition cache is flushed/invalidated and all 16 GiB are rehashed.

Short writes/readback failures restore touched blocks from the retained
old bytes without retrying the failed forward write. A complete ORIGINAL
hash is required to report restoration. Failed rollback is explicit and
blocks boot. No repairing fsck runs on the handheld.

The local loop-device test showed that e2fsck emits "in use" while our
exclusive descriptor is held. Therefore the writer closes AFTER complete
candidate readback, and strict `e2fsck -fn` runs between fresh unmounted
identity guards. No diagnostic exceptions were added. Post-fsck failure
retains the candidate and reports `POSTCHECK_FAILED_DO_NOT_BOOT`, without
additional automatic writes. Final read-only exclusive access rechecks the
header, all changed blocks and TF1 hashes.

Validation: 16 delta tests plus the existing 40 capture/copy/counter/journal/
boot tests passed, with output archived in `tests.txt`. The default real
preflight passed at 02:12:16, including all 24 old block hashes:
`out/logs/uart/rgsp/rgsp_serial_exec_20260910_021212_115200.log`.

The apply attempt started at 02:13:14. UART transcript:
`out/logs/uart/rgsp/rgsp_serial_exec_20260910_021310_115200.log`.
Device RAM log:
`/run/rgsp_data_delta_apply_20260910_0213.jsonl`.
This dispatch checkpoint alone established neither physical recovery
acceptance nor Fix72 runtime regression acceptance.

At 02:25:04 the entire live ORIGINAL hash matched the retained backup.
After fresh guards, all 24 blocks were written from 02:25:07 to 02:25:08,
with offset 0 last and every immediate block readback matching. The full
post-write read was still running at 02:28, having read 4 of 16 GiB.
No final whole-image or fsck acceptance existed at that intermediate point.
The live serial command was still running; this checkpoint was not a
reason to start another UART operation or repeat apply.

The separate host receipt collector additionally passed 7 tests. It rejects
missing/failed shell completion, incomplete reads/writes, incorrect hashes
or authorization, and fsck diagnostics. Source and test output are archived
in the deployment evidence directory. These tests do not replace real
device completion evidence.

## Physical Recovery Verified

On September 10, 2026 (UTC+08:00), complete candidate readback finished at
02:36:58. All 17179869184 bytes matched:
`b52bb83ef4c42a7cf6705526bd0f923a921f938e7a579621d9b23381832345a9`.
The five device `e2fsck -fn` passes completed at 02:37:03, exit 0, with no
warnings, count errors, recovery messages or repair questions. Device
e2fsck version was 1.46.5. The final success event was at 02:37:06 and the
serial command returned 0. No rollback was needed.

Header checks confirmed the original UUID, clean state, no
`needs_recovery`, journal start 0, 4058631 free blocks and 1045965 free
inodes. The fsck allocation summary was 2611 files and 135673 used blocks.
The writable descriptor was closed before fsck. Subsequent read-only
exclusive access reconfirmed all 24 candidate blocks and protected TF1
boot/env hashes.

The host collector accepted the complete sequence of 64 original-read
progress records, the original hash, 24 ordered writes, 64 candidate-read
records, candidate hash, strict fsck and the final successful shell exit.
Its output is `physical-recovery-result.json` in the deployment directory.
An independent UART read at 02:37:30 confirmed that the host-extracted
`device-apply.jsonl` exactly matches the device's RAM log, SHA-256:
`6924287a0dd49dc5cd2e9c43c53fd62ea8e6a2e13a6213603bbd2fc9a4dfde20`.
That later confirmation is recorded separately in `final-confirmation.json`;
the earlier collection-time receipt is preserved unchanged.

Final independent state evidence:
`out/logs/uart/rgsp/rgsp_serial_exec_20260910_023729_115200.log`.
Original CIDs, Linux root and boot ID remained unchanged; USB power was
online, p4 unmounted, SSH inactive and the one-shot marker absent. TF1
boot/env hashes matched their originals again. TF2 p1 remained mounted
with its existing `noatime` options and its current kernel FAT message
count was zero. No p1 unmount/remount/repair was done in this deployment.

This accepts ONLY the pinned p4 recovery. No boot preparation, reboot,
Android codec/WebView regression, independent boot or soak qualification
was performed. The next stage is the current helper's codec preflight,
then separately authorized TF1 one-shot boot preparation and reboot.
The live RAM helper remains:
`/run/prepare_rgsp_fix72_boot_only_diagnostics.sh`, SHA-256
`5351083c4f6c426002459207b7764b05b0d7184b20c1a474f8ea02057fbb4ccf`.
Do not rerun the original-preimage delta apply on the now-recovered data.

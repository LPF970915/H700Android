# TF2 P1 Repair After Audio Deployment

Date: September 10, 2026, UTC+08:00.

## Authorized Scope

After the verified audio vendor deployment, the user explicitly authorized
repair of TF2 p1 following a new backup and offline-copy verification.
No TF1, system, vendor, data or ROMS write is authorized by this repair.
No Android boot preparation or reboot is included.

The card was freshly identified as Disk 3, USB, 125069950976 bytes, with all
five partition GUIDs, offsets and sizes matching. The empty reader slot 2
and internal drives 0/1 were excluded. No drive letters were assigned.

## Fresh Backup

Directory: `out/tf2-p1-audio-repair-20260910-114004/`.

The locked raw-read-only capture completed at 11:40:26. It copied the full
268435456-byte p1 at physical offset 1048576, then reread the card and
verified the complete hash:

`ee4b9a7ad5164f2b411f2555b935332dccfda76f321863cf620c31c52a9cc1b6`.

This matches the post-audio-deployment state. It is a newly acquired copy,
not the historical September 9 p1 repair or the September 10 p4 recovery.
The full pre-repair image remains at `anboot-before.img` with its receipt.

## Offline Review

`tools/prepare_rgsp_p1_audio_repair.py` used new regular-file working copies
on the WSL filesystem, not physical devices. `fsck.fat -a -v` ran only on
the candidate copy. Subsequent `fsck.fat -n -v` exited zero with no dirty bit,
boot/backup mismatch, cluster-chain or free-cluster diagnostics.

The original and candidate were mounted read-only for independent full file
inventories. All 573 file/directory entries have identical paths, file
content hashes, file sizes, modes, ownership and modification timestamps.
The filesystem checker reports 574 entries including its volume/root
count. Both tools' before/after counts match. The pinned Linux recovery image is intact and there is no
`RGSP_ANDROID_TRY.ONCE` marker.

Candidate: `offline-review/anboot-repaired.img`.

SHA256:
`721ca44d984263f54f61cdf444d018ff733b4ff97ffd39ec81d791b88d13d887`.

The complete binary comparison found only 60 changed bytes in sectors
0, 1, 3030 and 7063 relative to the p1 start:

- Byte 65 changes from 01 to 00, clearing the dirty state and matching the
  existing backup boot sector.
- Byte 1000 changes the FSInfo free-cluster count.
- Two corresponding FAT sectors terminate the log file's excess chain and
  release its unused tail allocation. No file-content or directory-entry
  sectors change.

The file `RGSP_ANDROID_LOGCAT_BOUNDED.log` retains its full recorded
1134139-byte content. No boot image, configuration, application file or
logical log content was removed. The raw backup also retains the old FAT
allocation metadata and data-area bytes.

Evidence includes `before-fsck.log`, `copy-repair.log`, `after-fsck.log`,
both full file inventories, `byte-diff.json` and `review.json`.

## Write Gates

The existing p1 writer has a separate explicit `Audio` profile pinned to
the two hashes above and the deployed audio vendor hash. The legacy
profile does not accept this candidate or replace its old pinned images.

Before any write the Audio profile requires:

- Exact USB disk identity, five-partition geometry and fresh capture receipt.
- Full source/candidate local hashes and successful offline review.
- No prior Apply attempt or result.
- Full live p1 equality with the newly captured backup.
- Full pinned system, audio vendor and GPT head/tail hashes.
- Rechecked live disk identity and p1 equality immediately before writing.
- A successfully locked and dismounted p1, followed by another p1 preimage check.

The writer replaces only the 256 MiB p1 range using the existing transaction
helper with complete readback and automatic rollback on write/readback
failure. Although only 60 bytes differ, the physical transaction writes the
whole p1 image, not a four-sector delta. GPT/system/vendor are checked again.
A final raw p1 readback is exported while the volume remains locked, for an
independent offline FAT check after the writer exits.

Validation before Apply: Audio Plan passed, 24 memory-stream/identity tests
passed, and six FAT review tests passed. These include zero writes for a
changed live preimage, partial-write/readback rollback, rejecting nonzero
fsck results, and rejecting diagnostics even with exit zero.

Apply started at 11:48:42. Its completion is recorded below.
The repair addresses the observed filesystem inconsistencies, not yet the
cause of the preceding unclean state. A fresh device-side p4 journal/clean
state check still precedes Android startup; old recovery deltas must never
be replayed against data used since their capture.

## Completed Deployment

The physical p1 write began at 11:53:28. Complete p1 readback passed at
11:53:44. GPT, full system and full audio vendor postwrite hashes then
passed, and the additional 256 MiB raw p1 readback was exported.
The Apply receipt was recorded at 11:58:16 and the administrator process
exited zero. No automatic rollback was triggered.

`Apply-result.json` confirms p1 SHA256
`721ca44d984263f54f61cdf444d018ff733b4ff97ffd39ec81d791b88d13d887`,
unchanged GPT head/tail, system
`199c03bf5b46a81e26aab133d8310ae576690c99c926b1835d5f3e8ac3115faa`
and audio vendor
`9d0c8d4a95b69131a70db6aebdfa1d9b3967afa9dc7dc8e95932872ecb372cc2`.
No other partitions were written, and no reboot was requested.
Data/ROMS were not fully hashed, so this is not an entire-card comparison.

After the writer exited, the exported `Apply-p1-readback.img` was independently
hashed and checked with `fsck.fat -n -v`. Its hash matches the candidate,
and the check returned zero without the prior diagnostics. The check did
not change the readback image. Evidence: `Apply-readback-fsck.log`,
`P1Apply-admin.log`, `P1Apply-status.json`, `p1-repair-attempt.json`,
`Apply-result.json` and `postwrite-validation.json`.

All physical-device handles are closed. The card has not been ejected by
software; the user can now safely eject it through Windows and return it to
the powered-off handheld, retaining TF1. The next boundary is a fresh
device-side startup preflight, including p4 journal/clean state, followed by
separately controlled Android startup and persistent QQ Music audio checks.
This repair is not evidence of a successful new Android boot or audio test.

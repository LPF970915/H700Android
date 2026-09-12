# Fix72 TF2 Return Check

Date: 2026-09-09, UTC+08:00. Stage 1 remains open.

Update, September 10 at 07:53: after separately authorized p4 recovery and
guarded warm reboot, p1 mounted successfully as read-write `/rgsp-persist`
in Android with no current-kernel FAT error messages. The 20-component
codec runtime checks and actual Baidu HTTPS page passed. Original TF1
boot/env recovery and marker consumption passed. These results supersede
the waiting-for-boot boundary below, not its retained historical evidence.
See `H700_ANDROID10_FIX72_POST_RECOVERY_BOOT_20260910.md`. Independent
startup, cold cycles, sustained monitoring and hardware acceptance remain
open; the device currently remains in Android at AT4K.

## Physical State

The user returned TF2 to the original handheld. COM4 reached TF1 Linux,
not Android. Both pinned card CIDs matched and USB power was online.
TF2 p1 was mounted at `/mnt/sdcard`; p2/p3/p4 were unmounted.
No Android boot preparation or reboot was requested during this session.

## P1 Result

The earlier host Apply receipt records the repaired p1 readback at
12:05:22, with system/vendor/GPT checks passing:
`out/tf2-p1-readonly-20260909-r2/Apply-result.json`.

At 23:16, `fsck.fat -n` on the mounted p1 returned 1 for the dirty bit
and boot/backup byte 65 difference. This mounted observation was not
treated as an offline acceptance.

At 23:26, after checking open handles, a normal sync and unmount were
performed. `fsck.fat -n /dev/mmcblk1p1` returned 0 with 574 files and
424955/516190 clusters, without the previous diagnostics. The original
mount options were restored. No repairing fsck was used; ordinary
sync/unmount/remount can update filesystem metadata.

Evidence:
`out/logs/uart/rgsp/rgsp_serial_exec_20260909_232607_115200.log`.
This establishes a Linux-side unmounted FAT check, not an Android
`/rgsp-persist` regression or long-duration qualification.

## Data Gate

The previous boot helper (SHA-256
`a8f9e2298e84c7ccd58e7e0a491f6928b66e13d970efc3888e578cd932dcc8c0`)
returned `FIX72_BOOT_ONLY_CHECK_OK` during the 23:17 check. Full system
and codec vendor hashes passed, but its data fsck output explicitly
skipped journal recovery and reported free-block/inode discrepancies:
4058624 versus 4058630 blocks, and 1045964 versus 1045965 inodes.
Exit status alone was insufficient; this is NOT a clean data acceptance.

The independent 23:25 `tune2fs -l` query confirmed `needs_recovery`
despite the separate state field saying `clean`. TF1 p4 and env still
matched their pinned Linux originals, and no one-shot marker existed.
No data repair, journal replay, or data mount was performed.

Evidence:
`out/logs/uart/rgsp/rgsp_serial_exec_20260909_231701_115200.log` and
`out/logs/uart/rgsp/rgsp_serial_exec_20260909_232524_115200.log`.

The host boot helper now requires a readable, recognized ext4 header,
clean state, and no pending recovery before each read-only fsck and again
before preparation writes. A hash-verified copy was staged in RAM only:
`/run/prepare_rgsp_fix72_boot_only_20260909.sh`, SHA-256
`ac5579ae1074245ae7499cb1a75db29b7aa499702114136eaba02769a20cf887`.
Its real `--check codec` correctly exited 1 at p4 before boot preparation.
Evidence: `out/logs/uart/rgsp/rgsp_serial_exec_20260909_232800_115200.log`.
The older helper on TF2 was NOT overwritten; do not use it to bypass this
gate. The RAM copy disappears on reboot.

Validation: shell syntax and 24 boot/journal guard tests passed, including
a real 64 MiB ext4 regular-file test that sets `needs_recovery`, verifies
rejection, and confirms the header check does not change the file hash.
These host tests do not qualify any physical data recovery procedure.

## Next Boundary

The fresh backup and offline recovery study required by this return check
subsequently completed. At 02:37 on September 10, separately authorized
physical p4 recovery also completed: only the qualified 24 blocks were
written, the full 16 GiB readback matched the candidate, and device
`e2fsck -fn` passed all five stages without diagnostics. Full evidence is in
`H700_ANDROID10_DATA_COPY_RECOVERY_20260910.md` and
`out/tf2-data-backup-20260909-2359/deployment-20260910-0211/`.

Retain Linux and the current cards. The data gate is now resolved, but a
fresh codec boot preflight and separately authorized one-shot TF1 boot
preparation/reboot still precede Android runtime regression. The old replay
helper remains disabled; do not use forced general fsck, format, discard
data, repeat the original-preimage delta apply, or bypass the boot gate.

Linux also reported pre-existing TF1 p5 ext4 and p8 FAT warnings.
They were recorded but not repaired; they are separate from TF2 p1.
Android codec/WebView, HOME/IME, Wi-Fi and runtime regression still await
the next controlled Android boot. The 02:37 independent check reconfirmed
unmounted data, unchanged TF1 boot/env, inactive SSH and no boot marker.
No Android boot was prepared or requested during the p4 recovery.

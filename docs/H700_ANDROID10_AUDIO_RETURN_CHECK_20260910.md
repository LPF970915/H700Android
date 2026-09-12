# Audio Candidate Return Check

Date: September 10, 2026, UTC+08:00. Inspection completed at 12:19.

The user returned TF2 to the original handheld. COM4 reached original TF1
Linux (root `/dev/mmcblk0p5`), not Android. Boot ID:
`d8ef7030-9213-4f29-b674-cd8ef8d1e685`.
Both pinned card CIDs matched and USB power was online.
TF2 p1 was mounted at `/mnt/sdcard`; p2/p3/p4 were unmounted.

## Passed Checks

- TF1 p4 and the Linux recovery file both retain
  `d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5`.
- TF1 environment retains
  `d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396`.
- No `RGSP_ANDROID_TRY.ONCE` marker exists.
- No p1 FAT errors were found in the sampled current kernel log.
- P1 was normally synced and unmounted, then `fsck.fat -n -v` returned 0
  without diagnostics (574 entries, 420694/516190 clusters).
- Original p1 mount options were restored and independently printed in full.
- Unmounted system and audio vendor each passed all five `e2fsck -fn`
  stages without diagnostic issues.

The normal p1 sync/unmount/remount can update filesystem metadata. It is not
a repairing fsck or a guarantee that p1 stays byte-identical to the PC image
while Linux mounts it read-write. Full system/vendor hashes were verified
in the preceding PC deployment; this return check did not repeat those
whole-partition hashes.

## Data Blocks Startup

The currently unmounted data partition still has its expected UUID
`45daaa6e-724e-4d20-981c-602b3f72b8a2`. Its header says `Filesystem state:
clean`, but the feature list includes `needs_recovery`.
Last mount and write timestamps both read September 10 at 07:45:20.
Reported free blocks/inodes are 4058631/1045965.

The exact `require_clean_ext4_header` function from the current guarded
boot helper was run against live p4, after identity and unmounted-state
checks. It returned exit 1 with
`EXT4_RECOVERY_OR_STATE_REVIEW_REQUIRED`.
Only that read-only gate was executed; the full Audio boot helper was not
uploaded or run, and no boot preparation or reboot occurred.

This identifies pending journal recovery, not proven loss of user files.
Do not bypass the gate by mounting data, invoke the disabled historical
replay script, or apply the earlier 24-block delta. The user has installed
and run applications since that historical data backup.

Next work requires a NEW complete backup of current p4 and verification
of recovery on a separate copy. Any subsequent physical p4 write requires
its own reviewed scope and authorization. The preceding p1 repair
authorization does not authorize p4 modification.

## Evidence And Exit State

Directory: `out/rgsp-audio-return-20260910/`.

- `01-identity/rgsp_serial_exec_20260910_121629_115200.log`
- `02-storage/rgsp_serial_exec_20260910_121652_115200.log`
- `03-p1-unmounted/rgsp_serial_exec_20260910_121739_115200.log`
- `04-data-gate/rgsp_serial_exec_20260910_121833_115200.log`
- `05-final-storage/rgsp_serial_exec_20260910_121911_115200.log`

The final check confirms the same Linux boot ID, restored p1 mount options,
unmounted data and no boot marker. No system/vendor/data repairs, SSH
service changes, Android preparation or reboot were requested.
Persistent QQ Music playback remains untested.

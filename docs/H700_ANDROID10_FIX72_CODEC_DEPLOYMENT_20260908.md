# Fix72 Codec Deployment Procedure

Date: 2026-09-08, 23:21 CST. Status: vendor Apply completed; return TF2 to
the original handheld is required. The physical backup and narrow vendor
deployment succeeded; no boot preparation or reboot has yet been performed.

## Scope And Inputs

The candidate adds only three XML files to the frozen vendor. Only TF2 p3
may be written; system, data, ROM, TF1 and boot selection are out of scope
for the dedicated Windows writer. The historical two-partition writer is
not used for this update.

- Candidate vendor SHA-256:
  `1e1c90ffdc6fc08e7e40d333d3fab4ea065c19a34df38b4a0889bcc83a8dc891`.
- Frozen vendor / rollback SHA-256:
  `cb65140203807d0d80408e314f0c76554f2f81cd13fc76bf8ef07a4e46243c34`.
- Both are 2147483648-byte local images. Their hashes were verified by the
  new writer's default `Plan` mode, without opening a device or writing files.
- Candidate and independent diff evidence remain under
  `out/rgsp-fix72-codec-candidate-20260908/`.

## Guarded Writer

`tools/invoke_rgsp_codec_vendor_deploy.ps1` provides separate explicit
`Plan`, `Backup`, `Apply` and `Restore` modes, with no default disk number.
`tools/rgsp_vendor_io.ps1` contains the tested stream and identity helpers.

The operator must discover the CURRENT USB disk number after insertion.
Never reuse a remembered disk number. Before opening a physical disk, the
wrapper verifies USB/non-system/non-boot identity, exact capacity and all
five partition offsets, sizes and GUIDs, original Linux recovery payload
on ANBOOT, and absence of the one-shot marker. It locks p1/p2/p3 volumes
and checks the full live system hash. Backup/Apply require exact frozen
vendor content. Reader identity alone is not treated as card identity;
these content/partition checks also apply. Windows reader access does not
provide an independently verified silicon CID.

`Backup` requires a NEW directory inside workspace out and at least 5 GiB
free. It captures/rechecks GPT head/tail, ANBOOT and current vendor, then
creates an immutable receipt. System is fully hashed but not recopied.
The current data/ROM partitions are not backed up or fully hashed by this
procedure; the older data snapshot remains historical recovery material.
No filesystem repair is included.

`Apply` validates the fresh receipt, all backup file sizes/hashes, current
boot ranges and pinned system/vendor. It opens candidate and recovery
sources against concurrent writers, rechecks disk identity, writes a
durable attempt receipt, and transfers exactly p3. Full vendor readback,
protected GPT/ANBOOT checks and a full system hash follow.

On a write/readback failure, the stream transaction attempts to restore
the verified original vendor and checks the restored hash. It reports
either `VENDOR_ROLLBACK_VERIFIED` or `VENDOR_ROLLBACK_FAILED`, never a
successful Apply after a failed attempt. Loss of reader connectivity or
power can prevent rollback: retain the card, backups and logs, and do not
boot an unverified result. Do not automatically retry a failed Apply.

`Restore` requires the same backup and its matching prior Apply-attempt
receipt. It deliberately supports restoration after a partial write,
rather than requiring a complete candidate hash. All card/system/protected
range and backup checks still apply. Only p3 is restored. A previous
successful restore receipt blocks unreviewed repeated restores.

## Boot And Runtime Qualification

At 23:20:42 CST, the administrator-run Apply completed with
`CODEC_VENDOR_Apply_READBACK_VERIFIED`. The result records:

- TF2 p3 only, candidate vendor SHA-256
  `1e1c90ffdc6fc08e7e40d333d3fab4ea065c19a34df38b4a0889bcc83a8dc891`.
- Full system hash still matches
  `199c03bf5b46a81e26aab133d8310ae576690c99c926b1835d5f3e8ac3115faa`.
- GPT head/tail and ANBOOT protected ranges verified unchanged.
- `data_rom_written: false`, `reboot_requested: false`.

Apply log and receipt are in
`out/tf2-fix72-codec-backup-20260908/`. The original vendor rollback image
is retained with SHA-256
`cb65140203807d0d80408e314f0c76554f2f81cd13fc76bf8ef07a4e46243c34`.
No rollback was needed.

The existing boot-only helper now accepts an explicit second argument:

```sh
sh prepare_rgsp_fix72_boot_only.sh --check codec
sh prepare_rgsp_fix72_boot_only.sh --prepare codec
```

Run these separately only on original RGSP Linux with the original pinned
TF1/TF2 pair, AFTER successful deployment and return of TF2 to the device.
The omitted/default profile remains `frozen`; unknown profiles fail before
probes. Each profile accepts exactly one pinned vendor hash, not arbitrary
image hashes. Existing CID, power, mount, read-only fsck, system, TF1
boot/env/recovery and failed-preparation rollback checks remain intact.
This does not make the TF1-dependent handoff portable or TF2-only.

After a separately reviewed reboot, run
`tools/check_rgsp_fix72_runtime.ps1 -Profile Codec`. It checks all 17 frozen
components plus the three XMLs, rejects codec-directory overlays, and checks
media services. The crash-buffer gate remains; never clear historical crash
logs to manufacture a pass. Reopen Baidu HTTPS and inspect the actual page.
The candidate's `/vendor/etc` lookup still needs this persistent test.

## Host Verification And Evidence

- Python host suite: 64 tests passed, including exact-profile and wrong-profile
  boot rejection. The existing boot image still reconstructs to its pinned hash.
- PowerShell stream/identity suite: 18 tests passed. These use in-memory
  streams and temporary regular receipt files, never physical devices.
- Covered: partial write, corrupt readback, successful/failed rollback,
  corrupt/truncated source, corrupt recovery, adjacent-byte preservation,
  internal/system/read-only disks, wrong geometry/GUID and receipt overwrite.
- PowerShell parsing, shell syntax and `git diff --check` passed (existing
  LF/CRLF warning in the older two-partition writer remains).
- These tests do NOT qualify Windows USB volume locking, physical write
  readback, power-loss behavior or hardware boot.

Six source/test files are retained in
`out/rgsp-fix72-codec-candidate-20260908/deployment-tools-20260908-1353.zip`.
Archive SHA-256:
`ced6bf0e0c2d65d1d5454582878d361e3b9ef09ee70ee884a134d07204f3f82f`.
It is an evidence archive, not an autorun installer.

At 13:52:51 CST a read-only UART pre-removal query passed: original card
CIDs, completed Android boot, original TF1 boot/recovery/env hashes and no
pending marker. Uptime 6013.86 seconds; core PIDs still 1498/1520/1937;
USB power online. Evidence:
`out/logs/uart/rgsp/rgsp_serial_exec_20260908_135251_115200.log`.
This does not prove unchanged boot0 or formal continuous-soak acceptance.

## Required Physical Step

Normally shut down the original handheld completely, then move only TF2
to the computer's USB reader. Do not hot-remove the card, format it, accept
Windows repair prompts, swap TF1, or start the second stock-card test.
After insertion, inspect identity, make and verify the new backup, and
review its receipt before the separately invoked Apply. This is still
stage 1 of the user's plan; independent-startup qualification follows it.

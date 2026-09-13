# v5c Development Baseline

Date: 2026-09-13, Asia/Shanghai.
This checkpoint freezes the current bootable candidate before live fixes.
It is not a release qualification or a claim that every source was rebuilt.

## Candidate and Acceptance

`image-manifest.json` is an unchanged copy of the local v5c image manifest.
Its `physical_boot_verified=false` records the offline artifact gate; the
subsequent user report confirms desktop startup, not full physical acceptance.
See `../../H700_V5C_USER_ACCEPTANCE_20260913.md` for the current failures.
The 32,434,554,368-byte image and raw UART remain local under `out/`.

## Source Capture

The three files under
`android/h700-android10/snapshots/settings-v5c/packages/apps/Settings/`
are exact copies of the active WSL files used by the documented v5c Settings
fix. They retain upstream license headers. They are not automatically applied.
Compare them with the active tree before preparing further changes.
The extracted WSL Settings checkout does not currently resolve as a usable
Git repository, so no upstream commit or complete original diff is claimed.

The existing mainline overlay, adapted tracked AT4K prebuilt, firstboot
helpers, compact-image tools and capacity tests are included in this baseline.
WSL source and incremental build artifacts must remain intact.
Two clean rebuilds and full source-to-image reproducibility remain open.

## Tool Limitations

The retained direct writer succeeded historically for v5/v5b. Later v5c
attempts failed and the current card was flashed manually with Rufus.
Read `../../H700_V5C_RUFUS_BOOT_HANDOFF_20260913.md` before using older
direct-flash instructions. Hard-coded disk identities are historical, not
permission to write a newly attached disk.

The current build wrapper has an existing 40 GiB disk-space floor,
TasksMax=2048, one-CPU quota, 6 GiB memory and 512 MiB swap limit.
These are captured settings, not a claim that 40 GiB suffices for a clean
Android rebuild. Do not raise resource limits or clear caches in this task.

Machine-local diagnostic/cleanup experiments and the unverified
`rgsp-enable-dpad-focus.sh` are not promoted as baseline repair tools.
The latter selects a different IME component from the actual LeanbackIME
service and must not be used as a proven generic focus fix.

## Next Gate

Before rebuilding or flashing, validate narrowly scoped, backed-up runtime
changes through UART and physical user checks. Preserve HOME, language and
IME selections for rollback. Do not turn uncertain symptoms into confirmed
root causes, silently remap every application, or format ROMS.

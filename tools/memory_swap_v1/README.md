# Default 2GiB TF1 swap candidate

The actual Test8 4.9.170 kernel supports swap but does not include zram. Its
existing `zramsize=75%` fstab line therefore creates no usable swap. Read-only
ADB on the connected 1GiB RG35XX H reported `SwapTotal: 0 kB`. The observed
crash buffer did not establish an OOM cause for every application failure.

The composed early helper adds an optional, default-enabled 2GiB disk swap
file at `/data/roc-swap/swapfile-2g`. It runs for all models before any stick
or model gate, after TF1 ext4 userdata is mounted and before the Android
policy handoff. The original sampling-v2 input helper is an unchanged byte
suffix. The boot init, kernel, Android security policy and signing keys do
not change. This consumes 2GiB of TF1 space, uses TF1 IO under memory pressure,
and is not equivalent to adding physical RAM.

New creation requires 2GiB plus 512MiB free. The directory must be root-owned
0700 and the file root-owned 0600, ordinary, and single-link. Sequential `dd`
writes plus fsync allocate the whole file before mkswap; a validated staging
file is renamed only after its header is complete. Existing files are never
reformatted. Symlinks, hardlinks, wrong modes, sizes or headers are retained
and refused. An active staging file is never deleted. A valid private staging
file left by an interrupted create can be removed and recreated next boot.

The expected 4KiB-page header is version 1, last_page 524287. Successful
activation must appear as a file with 2097148KiB usable swap in `/proc/swaps`.
The 300-second guard bounds waiting for the initial dd child. It is not a
strict overall IO deadline: D-state IO cannot be guaranteed to terminate
immediately, and mkswap, sync and swapon use their normal kernel operations.
All reported failures continue through the original input helper to Android.

`audit_boot.py` reads bounded ordinary-file Test8 boot ranges and executes
only the retained BusyBox's applet listing under qemu. `test_swap.py` exercises
the actual composed shell with a scaled 8MiB real file and actual mother
BusyBox dd/fsync/mkswap/metadata operations. Swapon is always intercepted;
host swap is never activated. A separate sparse 2GiB ordinary file verifies
the real mkswap's 64-bit header boundary only; it does not prove a usable
fully allocated swap file. Space values, sync and expected fixture UID/GID
are explicit test boundaries. Hardware performance and activation still
require the new image's runtime evidence.

Rollback to Test8 stops activating this file on the next boot. Its allocated
space remains until the inactive file is removed offline or userdata is
reflashed. No live swapoff or deletion is performed by these tools.

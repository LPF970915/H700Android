# Test9 stick sampling and default 2 GiB swap candidate packaging

These tools operate on ordinary image files only. They do not use ADB, serial,
block devices, mounts, flashing, signing keys, network uploads, or Git writes.
The Test8 sources, artifacts and acceptance records remain immutable inputs.

`package.py prepare` pins the entire Test8 parent, freezes three replacement
payloads and the new driver/host/ABI/loader receipts, changes one CPIO payload,
and changes exactly two vendor filesystem payloads. The ramdisk is compressed
at level 9 and padded with zero bytes to its **original compressed length**.
Python and the inherited kernel's `unpack_to_rootfs` zero-byte path permit this
tail padding. Preparation
fails if it cannot fit; it does not move the kernel DTB, change the Android boot
header or edit boot environment commands. Every prefix byte outside the original
ramdisk byte range must remain identical to Test8.

`package.py package` copies the exact parent sparse raw image, installs only the
prepared prefix/vendor ranges and creates a complete gzip. `verify.py` imports
read-only parsers from the prior independent verifier, never the new producer.
It independently expands the full gzip, compares every byte to the producer raw,
checks all range digests, GPT, original boot component offsets, every CPIO member,
the complete vendor tree and its modes/owners/labels/timestamps, and all frozen
input identities. System/userdata/GPT equality carries the accepted Test8
Navigation18/framework/ART/Lid4/time/USB/security state forward byte for byte.

The explicit manifest contract is:

```json
{
  "schema": "roc.h700.stick-memory-inputs.v1",
  "inputs": {
    "module": {"path": "/absolute/h700_stick_axes.ko", "sha256": "..."},
    "early_helper": {"path": "/absolute/h700_optional_axes.sh", "sha256": "..."},
    "android_loader": {"path": "/absolute/rgsp-stick-axes.sh", "sha256": "..."}
  },
  "candidate_receipt": {"path": "/absolute/result.json", "sha256": "..."}
}
```

The candidate receipt must be `roc.h700.stick-memory-candidate.v1`, with
`passed=true`, exact `module_path/module_sha256`, an `artifacts` dictionary
identical to the three manifest inputs, nonempty absolute-path `controls`, and
`proofs` containing exactly `host`, `build`, `abi`, `kernel_binding`, `loaders`,
and `memory`.
Each proof is `{path, sha256}`. Host/build/loaders must report `passed=true`;
host must report flat `actual_C_host_test=true`, `kernel_APIs_mocked=true`,
and positive `checks` and `scenarios` after executing the actual C with mocked
hardware APIs; ABI must bind the exact module and have at least the
original 410 reference CRCs and all actual module imports matched. Kernel binding
must bind the exact Test8 kernel SHA and preserve exports/CRC/relocation/names.
Build, loaders, and candidate must all bind the same module SHA. Candidate must
explicitly keep `physical_acceptance=false`, `no_RAM_identity_gate=true`, and
all twelve catalog models. All source/helper/proof inputs must be frozen before
prepare. The package validates the receipt rather than manufacturing one.

The `memory` proof must be `roc.h700.swap2g-host.v1`, `passed=true`, with
`swap_bytes=2147483648`, `default_enabled=true`, `physical_acceptance=false`,
`actual_host_swapon=false`, and the final installed early helper's SHA in
`helper_sha256`. It must report `reuse_size_or_space_guard=true`,
`failure_nonfatal=true`, `no_RAM_identity_gate=true`, and freeze its executed
sources plus actual BusyBox/kernel evidence in nonempty `controls` path/hash
pairs. The final early helper must appear there. All memory controls are also
copied into preparation's frozen controls and checked throughout packaging and
independent verification. Neither the wrapper nor verifier executes swapon.

Run each phase separately using `run.ps1 -Phase prepare|package|verify -Execute`.
Only prepare takes `-Manifest /mnt/d/.../inputs.json`. The wrapper uses
`systemd-run --wait --pipe`, one CPU on CPUs 0-1, nice 19, RAM high 5 GiB/max
6 GiB, swap 512 MiB, idle IO, a three-hour cap, and the existing global flock.
The parent agent schedules heavy phases serially. No new image is deliverable
until full independent verification and the host gzip hash check pass. These
tools never promote an accepted baseline or claim physical stick success.

`validate_tools.py` is a lightweight fixture runner. Its fresh 16 MiB ext4 file
checks the actual inherited debugfs replacement path, owner/mode/label and
nonzero timestamp-extra preservation, all affected parent/root timestamps,
read-only fsck, imports, and Python gzip zero-tail decoding. It never reads a
Test8/card/device image. This is tool validation, not the complete image review.

#!/usr/bin/env python3
"""Pinned 24-block TF2 p4 recovery. Default device mode is read-only."""
import argparse
import base64
from datetime import datetime, timezone
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess

DATA = "/dev/mmcblk1p4"
SIZE = 17179869184
BLOCK = 4096
CHUNK = 1024 * 1024
ORIGINAL = "6eeea7bf7a5cd0b95c0540f378d290326805ff1c4feab95b52f3ffe9aa4b29ea"
CANDIDATE = "b52bb83ef4c42a7cf6705526bd0f923a921f938e7a579621d9b23381832345a9"
ARCHIVE = "a344cca509f29209add7e5378ab2bf590b31c25d964980768f76f2baa4a8b07a"
MANIFEST = "91e54b041f88b69f6a3cab552ecf9a827c1a1b160a9a31b0fd81cca05fb5f4c1"
BOOT = "d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5"
ENV = "d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396"
UUID = "45daaa6e-724e-4d20-981c-602b3f72b8a2"
BLKFLSBUF = 0x1261
BASE = Path(__file__).resolve().parents[1] / "out/tf2-data-backup-20260909-2359"
BLOCK_COUNT = 24
ARCHIVE_BYTES = 173429842
TRIAL = "offline-counter-trial"
CANDIDATE_FILE = "data.recovery-candidate.img"
QUALIFIED_STATUS = "OFFLINE_RECOVERY_VERIFIED_NOT_DEPLOYED"
FREE_BLOCKS = "4058631"
FREE_INODES = "1045965"
BUNDLE_LIMIT = 512 * 1024
PROFILE_SHA = None
EXTRA_PROTECTED = ()


def configure_audio_profile(path, expected):
    global BASE, ORIGINAL, CANDIDATE, ARCHIVE, MANIFEST, BLOCK_COUNT
    global ARCHIVE_BYTES, TRIAL, CANDIDATE_FILE, QUALIFIED_STATUS
    global FREE_BLOCKS, FREE_INODES, BUNDLE_LIMIT, PROFILE_SHA, EXTRA_PROTECTED
    regular(path)
    raw = Path(path).read_bytes()
    if len(raw) > 16384 or not re.fullmatch("[0-9a-f]{64}", expected or "") or sha(raw) != expected:
        raise ValueError("Explicit matching audio recovery profile hash required")
    value = json.loads(raw)
    if value["schema"] != "rgsp-audio-data-recovery-v1" or value["bytes"] != SIZE:
        raise ValueError("Unrecognized audio recovery profile")
    for key in ("original_sha256", "candidate_sha256", "archive_sha256", "manifest_sha256"):
        if not re.fullmatch("[0-9a-f]{64}", value[key]):
            raise ValueError("Invalid profile image hash")
    if value["original_sha256"] == value["candidate_sha256"]:
        raise ValueError("Recovery must change the image")
    count = value["blocks"]
    if type(count) is not int or not 1 <= count <= 8192:
        raise ValueError("Recovery delta exceeds reviewed metadata bound")
    if type(value["archive_bytes"]) is not int or not 0 < value["archive_bytes"] <= SIZE + CHUNK:
        raise ValueError("Invalid archive length")
    for key, maximum in (("free_blocks", 4194304), ("free_inodes", 1048576)):
        if type(value[key]) is not int or not 0 < value[key] <= maximum:
            raise ValueError("Invalid post-recovery free count")
    trials = {
        "offline-journal-trial": ("data.journal-replayed.img", "OFFLINE_JOURNAL_REPLAY_VERIFIED_NOT_DEPLOYED"),
        "offline-counter-trial": ("data.recovery-candidate.img", "OFFLINE_RECOVERY_VERIFIED_NOT_DEPLOYED"),
    }
    if value["trial"] not in trials or value["audio_vendor_sha256"] != (
            "9d0c8d4a95b69131a70db6aebdfa1d9b3967afa9dc7dc8e95932872ecb372cc2"):
        raise ValueError("Unexpected trial or audio vendor")
    BASE = Path(__file__).resolve().parents[1] / "out/tf2-data-backup-audio-20260910"
    ORIGINAL, CANDIDATE = value["original_sha256"], value["candidate_sha256"]
    ARCHIVE, MANIFEST = value["archive_sha256"], value["manifest_sha256"]
    BLOCK_COUNT, ARCHIVE_BYTES = count, value["archive_bytes"]
    TRIAL = value["trial"]
    CANDIDATE_FILE, QUALIFIED_STATUS = trials[TRIAL]
    FREE_BLOCKS, FREE_INODES = str(value["free_blocks"]), str(value["free_inodes"])
    BUNDLE_LIMIT = max(512 * 1024, count * 16384 + 1024 * 1024)
    PROFILE_SHA = expected
    EXTRA_PROTECTED = (("/dev/mmcblk1p3", 2147483648, value["audio_vendor_sha256"]),)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def save_json(path, value):
    with Path(path).open("x", encoding="ascii") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def regular(path, size=None):
    info = Path(path).lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("A single-link regular file is required")
    if size is not None and info.st_size != size:
        raise ValueError("File size mismatch")


def manifest(raw):
    if sha(raw) != MANIFEST:
        raise ValueError("Unapproved block manifest")
    records = json.loads(raw)
    validate_records(records)
    return records


def validate_records(records):
    if not isinstance(records, list) or len(records) != BLOCK_COUNT:
        raise ValueError("Exactly the profile's approved block count is required")
    previous = -1
    for row in records:
        offset = row["offset"]
        if (type(offset) is not int or offset <= previous or offset % BLOCK or
                not 0 <= offset <= SIZE - BLOCK or row["bytes"] != BLOCK):
            raise ValueError("Invalid block offset/size/order")
        for key in ("before_sha256", "after_sha256"):
            if not re.fullmatch("[0-9a-f]{64}", row[key]):
                raise ValueError("Invalid block hash")
        if row["before_sha256"] == row["after_sha256"]:
            raise ValueError("Unchanged block in delta")
        previous = offset
    if records[0]["offset"] != 0:
        raise ValueError("Expected superblock-containing block")


def load_bundle(path, expected):
    regular(path)
    packed = Path(path).read_bytes()
    if len(packed) > BUNDLE_LIMIT or sha(packed) != expected:
        raise ValueError("Bundle size/hash mismatch")
    with gzip.open(path, "rb") as source:
        raw = source.read(BUNDLE_LIMIT + 1)
    if len(raw) > BUNDLE_LIMIT:
        raise ValueError("Expanded bundle too large")
    value = json.loads(raw)
    if value["original_sha256"] != ORIGINAL or value["candidate_sha256"] != CANDIDATE:
        raise ValueError("Bundle image identity mismatch")
    rows = manifest(base64.b64decode(value["manifest"], validate=True))
    payload = value["payload"]
    if len(payload) != len(rows):
        raise ValueError("Payload count mismatch")
    blocks = []
    for row, pair in zip(rows, payload):
        old, new = [base64.b64decode(pair[k], validate=True) for k in ("before", "after")]
        if (len(old) != BLOCK or len(new) != BLOCK or
                sha(old) != row["before_sha256"] or sha(new) != row["after_sha256"]):
            raise ValueError("Payload bytes/hash mismatch")
        blocks.append((row["offset"], old, new))
    return blocks


def build(output):
    output = Path(output).absolute()
    if output.resolve() != output or not output.is_relative_to(BASE.resolve()):
        raise ValueError("Bundle output must stay inside backup directory")
    if output.exists():
        raise ValueError("Do not replace existing bundle")
    source = BASE / "data.before.img.gz"
    candidate = BASE / TRIAL / CANDIDATE_FILE
    raw_manifest = (BASE / TRIAL / "block-diff.json").read_bytes()
    rows = manifest(raw_manifest)
    regular(source, ARCHIVE_BYTES)
    regular(candidate, SIZE)
    if sha(source.read_bytes()) != ARCHIVE:
        raise ValueError("Original archive hash mismatch")
    receipt = json.loads((BASE / TRIAL / "result.json").read_text())
    if (receipt["status"] != QUALIFIED_STATUS or
            receipt["candidate_sha256"] != CANDIDATE or receipt["original_sha256"] != ORIGINAL):
        raise ValueError("Offline qualification missing")
    original_hash, candidate_hash = hashlib.sha256(), hashlib.sha256()
    found, payload = [], []
    with gzip.open(source, "rb") as before, candidate.open("rb") as after:
        for offset in range(0, SIZE, CHUNK):
            a, b = before.read(CHUNK), after.read(CHUNK)
            if len(a) != CHUNK or len(b) != CHUNK:
                raise ValueError("Incomplete full image comparison")
            original_hash.update(a)
            candidate_hash.update(b)
            if a != b:
                for i in range(0, CHUNK, BLOCK):
                    old, new = a[i:i + BLOCK], b[i:i + BLOCK]
                    if old != new:
                        found.append({"offset": offset + i, "bytes": BLOCK,
                                      "before_sha256": sha(old), "after_sha256": sha(new)})
                        payload.append({"before": base64.b64encode(old).decode(),
                                        "after": base64.b64encode(new).decode()})
            if (offset + CHUNK) % (1024**3) == 0:
                print("HOST_FULL_COMPARISON_BYTES=" + str(offset + CHUNK), flush=True)
        if before.read(1) or after.read(1):
            raise ValueError("Images exceed approved length")
    if original_hash.hexdigest() != ORIGINAL or candidate_hash.hexdigest() != CANDIDATE or found != rows:
        raise ValueError("Full comparison does not match approved delta")
    value = {"original_sha256": ORIGINAL, "candidate_sha256": CANDIDATE,
             "manifest": base64.b64encode(raw_manifest).decode(), "payload": payload}
    packed = gzip.compress(json.dumps(value, sort_keys=True).encode("ascii"), mtime=0)
    with output.open("xb") as stream:
        stream.write(packed)
        stream.flush()
        os.fsync(stream.fileno())
    load_bundle(output, sha(packed))
    save_json(str(output) + ".json", {
        "status": "BUNDLE_FULL_IMAGES_VERIFIED", "created": timestamp(),
        "original_sha256": ORIGINAL, "candidate_sha256": CANDIDATE,
        "manifest_sha256": MANIFEST, "bundle_sha256": sha(packed),
        "bundle_bytes": len(packed), "blocks": len(rows), "device_writes": False,
    })
    print("BUNDLE_SHA256=" + sha(packed), flush=True)


def run(*args):
    return subprocess.run(args, capture_output=True, text=True, timeout=600,
                          env={**os.environ, "LC_ALL": "C"})


def command(*args):
    result = run(*args)
    if result.returncode:
        raise ValueError("Command failed: " + repr(args) + ": " + result.stderr)
    return result.stdout.strip()


def guard(filesystem=True):
    if os.geteuid() != 0 or command("findmnt", "-rn", "-o", "SOURCE", "--target", "/") != "/dev/mmcblk0p5":
        raise ValueError("Original Linux root required")
    for path, expected in {
        "/sys/block/mmcblk0/device/cid": "1d414455534400002000009f9401a1e7",
        "/sys/block/mmcblk1/device/cid": "fe3432534400000020000005bc01896b",
        "/sys/class/power_supply/axp2202-usb/online": "1",
        "/sys/block/mmcblk1/mmcblk1p4/start": str(11006902272 // 512),
        "/sys/block/mmcblk1/mmcblk1p4/size": str(SIZE // 512),
    }.items():
        if Path(path).read_text().strip() != expected:
            raise ValueError("Device identity/power/geometry mismatch: " + path)
    info = os.stat(DATA, follow_symlinks=False)
    if not stat.S_ISBLK(info.st_mode) or command("blockdev", "--getsize64", DATA) != str(SIZE):
        raise ValueError("Fixed p4 block device required")
    devno = "{}:{}".format(os.major(info.st_rdev), os.minor(info.st_rdev))
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        if line.split()[2] == devno:
            raise ValueError("Data partition is mounted")
    if run("findmnt", "-rn", "-S", DATA).returncode != 1:
        raise ValueError("Unknown or mounted data")
    if command("findmnt", "-rn", "-o", "SOURCE", "--target", "/mnt/sdcard") != "/dev/mmcblk1p1":
        raise ValueError("Boot marker location unavailable")
    if os.path.lexists("/mnt/sdcard/RGSP_ANDROID_TRY.ONCE"):
        raise ValueError("Pending boot marker")
    if filesystem:
        for key, expected in {"UUID": UUID, "TYPE": "ext4",
                              "PARTUUID": "734716ed-e7d9-e74f-9b3e-4f1cb8d448ed"}.items():
            if command("blkid", "-p", "-s", key if key != "PARTUUID" else "PART_ENTRY_UUID",
                       "-o", "value", DATA) != expected:
                raise ValueError("Filesystem/partition identity mismatch: " + key)
    return {"boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
            "rdev": info.st_rdev}


def hash_fd(fd, length, phase, log):
    result = hashlib.sha256()
    for offset in range(0, length, CHUNK):
        data = os.pread(fd, min(CHUNK, length - offset), offset)
        if len(data) != min(CHUNK, length - offset):
            raise IOError("Short read during " + phase)
        result.update(data)
        if (offset + len(data)) % (256 * 1024**2) == 0:
            log(phase=phase, bytes=offset + len(data), total=length)
    return result.hexdigest()


def protected_hashes(log, full=False):
    found = {}
    ranges = (("/dev/mmcblk0p4", 67108864, BOOT), ("/dev/mmcblk0p3", 131072, ENV))
    if full:
        ranges += EXTRA_PROTECTED
    for path, length, expected in ranges:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            actual = hash_fd(fd, length, "protected_hash", log)
        finally:
            os.close(fd)
        if actual != expected:
            raise ValueError("Protected TF1 hash changed: " + path)
        found[path] = actual
    return found


def strict_fsck(result):
    text = result.stdout + result.stderr
    if (result.returncode != 0 or
            re.findall(r"^Pass ([1-5]):", text, re.MULTILINE) != list("12345") or
            re.search(r"\?|warning|wrong|corrupt|error|recover|modified|invalid|abort", text, re.I)):
        raise ValueError("Device read-only fsck is not diagnostically clean")


def strict_header(text):
    fields = {}
    for line in text.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            if key in fields:
                raise ValueError("Duplicate header key")
            fields[key] = value.strip()
    for key, expected in {"Filesystem UUID": UUID, "Filesystem state": "clean",
                          "Free blocks": FREE_BLOCKS, "Free inodes": FREE_INODES,
                          "Block count": "4194304", "Block size": "4096"}.items():
        if fields.get(key) != expected:
            raise ValueError("Header mismatch: " + key)
    if "Filesystem features" not in fields or "needs_recovery" in fields["Filesystem features"].split():
        raise ValueError("Pending/unknown recovery state")


def flush_device(fd):
    os.fsync(fd)
    fcntl.ioctl(fd, BLKFLSBUF)


def ordered(blocks):
    return sorted(blocks, key=lambda row: (row[0] == 0, row[0]))


def apply_blocks(fd, blocks, verify, still_same, flush, log, original_check):
    touched = []
    try:
        still_same()
        for offset, old, _ in blocks:
            if os.pread(fd, BLOCK, offset) != old:
                raise ValueError("Live preimage mismatch at " + str(offset))
        for row in ordered(blocks):
            offset, old, new = row
            still_same()
            if os.pread(fd, BLOCK, offset) != old:
                raise ValueError("Preimage changed immediately before write")
            touched.append(row)  # Include a block even if its write fails partway.
            if os.pwrite(fd, new, offset) != BLOCK:
                raise IOError("Short device write; no retry")
            os.fsync(fd)
            if os.pread(fd, BLOCK, offset) != new:
                raise IOError("Immediate block readback mismatch")
            log(phase="block_written", offset=offset, count=len(touched))
        flush()
        verify()
    except BaseException as failure:
        log(status="APPLY_FAILED", error=repr(failure), touched=len(touched))
        if not touched:
            raise
        try:
            still_same()
            for offset, old, _ in ordered(touched):
                still_same()
                if os.pwrite(fd, old, offset) != BLOCK:
                    raise IOError("Short rollback write; no retry")
                os.fsync(fd)
                if os.pread(fd, BLOCK, offset) != old:
                    raise IOError("Rollback block readback mismatch")
                log(phase="rollback_block", offset=offset)
            flush()
            original_check()
            log(status="APPLY_FAILED_ORIGINAL_RESTORED", original_sha256=ORIGINAL)
        except BaseException as rollback_failure:
            log(status="ROLLBACK_FAILED_DO_NOT_BOOT", error=repr(rollback_failure))
            raise RuntimeError("Rollback not verified; preserve device and all evidence") from rollback_failure
        raise RuntimeError("Apply failed; original full image restored") from failure


def device(args):
    blocks = load_bundle(args.bundle, args.bundle_sha256)
    if not re.fullmatch("[A-Za-z0-9_-]{1,80}", args.attempt):
        raise ValueError("Invalid attempt ID")
    if args.apply_authorized_p4 and not re.fullmatch("[0-9a-f]{64}", args.authorization_sha256 or ""):
        raise ValueError("Host authorization receipt hash required")
    if command("findmnt", "-rn", "-o", "FSTYPE", "--target", "/run") != "tmpfs":
        raise ValueError("Device logs must stay in RAM")
    logfile = Path("/run/rgsp_data_delta_" + args.attempt + ".jsonl")
    with logfile.open("x", encoding="ascii", buffering=1) as stream:
        def log(**value):
            value["time"] = timestamp()
            line = json.dumps(value)
            stream.write(line + "\n")
            stream.flush()
            try:
                print(line, flush=True)
            except OSError:
                pass  # The RAM log remains authoritative if UART disconnects.
        fd = None
        try:
            before = guard()
            protected = protected_hashes(log, full=True)
            log(status="AUTHORIZED_APPLY_START" if args.apply_authorized_p4 else "READONLY_CHECK_START",
                identity=before, bundle_sha256=args.bundle_sha256,
                authorization_sha256=args.authorization_sha256, protected=protected,
                script_sha256=sha(Path(__file__).read_bytes()), blocks=len(blocks),
                recovery_profile_sha256=PROFILE_SHA)
            mode = os.O_RDWR if args.apply_authorized_p4 else os.O_RDONLY
            fd = os.open(DATA, mode | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            def still_same():
                if guard(filesystem=False) != before or os.fstat(fd).st_rdev != before["rdev"]:
                    raise ValueError("Live identity changed")
            still_same()
            for offset, old, _ in blocks:
                if os.pread(fd, BLOCK, offset) != old:
                    raise ValueError("Live block differs from approved original: " + str(offset))
            if not args.apply_authorized_p4:
                log(status="READONLY_PREFLIGHT_PASSED", full_source_hash_checked=False)
                return
            # Reject unsupported cache invalidation before any p4 bytes are changed.
            flush_device(fd)
            actual = hash_fd(fd, SIZE, "full_original_hash", log)
            if actual != ORIGINAL:
                raise ValueError("Full live original SHA mismatch: " + actual)
            log(phase="full_original_verified", sha256=actual)
            still_same()
            protected_hashes(log)
            def verify():
                actual = hash_fd(fd, SIZE, "full_candidate_readback", log)
                if actual != CANDIDATE:
                    raise ValueError("Full candidate readback mismatch: " + actual)
                log(phase="full_candidate_verified", sha256=actual)
                still_same()
                header = command("dumpe2fs", "-h", DATA)
                log(phase="header", output=header)
                strict_header(header)
                still_same()
                protected_hashes(log)
            def original_check():
                actual = hash_fd(fd, SIZE, "rollback_full_original_hash", log)
                if actual != ORIGINAL:
                    raise ValueError("Full rollback hash mismatch: " + actual)
                still_same()
            apply_blocks(fd, blocks, verify, still_same, lambda: flush_device(fd), log, original_check)
            # e2fsck reports "in use" while our O_EXCL descriptor is held.
            # Close every writable descriptor before the separately guarded -fn.
            os.close(fd)
            fd = None
            log(status="CANDIDATE_BYTES_VERIFIED_FSCK_PENDING", sha256=CANDIDATE)
            try:
                if guard() != before:
                    raise ValueError("Identity changed before standalone read-only fsck")
                result = run("e2fsck", "-fn", DATA)
                log(phase="readonly_fsck", output=result.stdout + result.stderr,
                    exit_code=result.returncode)
                strict_fsck(result)
                if guard() != before:
                    raise ValueError("Identity changed after standalone read-only fsck")
                fd = os.open(DATA, os.O_RDONLY | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC)
                still_same()
                strict_header(command("dumpe2fs", "-h", DATA))
                for offset, _, new in blocks:
                    if os.pread(fd, BLOCK, offset) != new:
                        raise ValueError("Candidate block changed during read-only fsck")
                protected_hashes(log)
            except BaseException as failure:
                log(status="POSTCHECK_FAILED_DO_NOT_BOOT", error=repr(failure),
                    disposition="Candidate full hash was verified; no automatic post-fsck writes")
                raise
            final_protected = protected_hashes(log, full=True)
            if final_protected != protected:
                raise ValueError("Protected image hashes changed across recovery")
            log(status="PHYSICAL_P4_RECOVERY_VERIFIED", sha256=CANDIDATE, bytes=SIZE,
                strict_readonly_fsck_clean=True, boot_marker=False, data_unmounted=True,
                protected=final_protected, modified_partition=DATA, written_blocks=BLOCK_COUNT,
                recovery_profile_sha256=PROFILE_SHA)
        except BaseException as failure:
            log(status="ATTEMPT_FAILED", error=repr(failure))
            raise
        finally:
            if fd is not None:
                os.close(fd)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio-profile")
    parser.add_argument("--audio-profile-sha256")
    sub = parser.add_subparsers(dest="mode", required=True)
    host = sub.add_parser("build")
    host.add_argument("--output", required=True)
    target = sub.add_parser("device")
    target.add_argument("--bundle", required=True)
    target.add_argument("--bundle-sha256", required=True)
    target.add_argument("--attempt", required=True)
    target.add_argument("--authorization-sha256")
    target.add_argument("--apply-authorized-p4", action="store_true")
    args = parser.parse_args()
    if bool(args.audio_profile) != bool(args.audio_profile_sha256):
        parser.error("Both explicit audio profile path and hash are required")
    if args.audio_profile:
        configure_audio_profile(args.audio_profile, args.audio_profile_sha256)
    if args.mode == "build":
        build(args.output)
    else:
        signal.signal(signal.SIGHUP, signal.SIG_IGN)
        device(args)

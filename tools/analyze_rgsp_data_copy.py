#!/usr/bin/env python3
"""Journal-only experiment on a NEW regular-file copy of a verified backup."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile

from capture_rgsp_data_readonly import DATA_BYTES, FLOOR, digest
from compare_rgsp_image_files import inventory

REPLAY_ARGS = ["e2fsck", "-E", "journal_only", "-y"]


def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def regular(path, size=None):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("Only single-link regular files are accepted")
    if size is not None and info.st_size != size:
        raise ValueError("Unexpected file length")


def sha(path):
    regular(path)
    with path.open("rb") as stream:
        return digest(stream, path.stat().st_size)


def run_log(args, path):
    result = subprocess.run(args, capture_output=True, text=True,
                            env={**os.environ, "LC_ALL": "C"}, timeout=600)
    with path.open("x") as stream:
        stream.write("$ " + " ".join(args) + "\n")
        stream.write(result.stdout + result.stderr)
        stream.write("\nEXIT_CODE=" + str(result.returncode) + "\n")
    return result


def check_replay_result(result):
    text = result.stdout + result.stderr
    if result.returncode not in (0, 1) or re.search(r"Pass [1-5]:", text):
        raise ValueError("Replay failed or entered full filesystem-check passes")


def check_readonly_result(result):
    text = result.stdout + result.stderr
    passes = re.findall(r"^Pass ([1-5]):", text, re.MULTILINE)
    if (result.returncode != 0 or passes != list("12345") or
            re.search(r"\?|warning|wrong|corrupt|error|recover|modified|invalid|abort",
                      text, re.IGNORECASE)):
        raise ValueError("Read-only fsck diagnostics are not clean, regardless of exit code")


def header_fields(text):
    values = {}
    for line in text.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            if key in values:
                raise ValueError("Duplicate filesystem header field")
            values[key] = value.strip()
    if not {"Filesystem UUID", "Filesystem features", "Filesystem state"} <= values.keys():
        raise ValueError("Incomplete filesystem header")
    return values


def expand_verified(archive, candidate, size, expected):
    total = 0
    h = hashlib.sha256()
    with gzip.open(archive, "rb") as source, candidate.open("xb") as target:
        while True:
            block = source.read(1024 * 1024)
            if not block:
                break
            total += len(block)
            if total > size:
                raise ValueError("Archive exceeds expected size")
            h.update(block)
            if block == bytes(len(block)):
                target.seek(len(block), 1)
            else:
                target.write(block)
        target.truncate(total)
        target.flush()
        os.fsync(target.fileno())
    if total != size or h.hexdigest() != expected or sha(candidate) != expected:
        raise ValueError("Expanded backup failed byte/hash verification")


@contextmanager
def readonly_mount(image):
    regular(image, DATA_BYTES)
    mountpoint = tempfile.mkdtemp(prefix="rgsp-data-readonly-")
    mounted = False
    try:
        subprocess.run(["mount", "-t", "ext4", "-o", "loop,ro,noload,nodev,nosuid,noexec",
                        str(image), mountpoint], check=True, capture_output=True)
        mounted = True
        yield Path(mountpoint)
    finally:
        if mounted:
            subprocess.run(["umount", mountpoint], check=True, capture_output=True)
        os.rmdir(mountpoint)


def snapshot(image):
    with readonly_mount(image) as mounted:
        def fail_walk(error):
            raise error
        for _ in os.walk(mounted, followlinks=False, onerror=fail_walk):
            pass
        entries = inventory(mounted)
        info = mounted.stat()
        entries["."] = {"directory": True, "mode": stat.S_IMODE(info.st_mode),
                        "uid": info.st_uid, "gid": info.st_gid}
        for name, entry in entries.items():
            path = mounted / name
            metadata = path.lstat()
            entry.update({"size": metadata.st_size, "links": metadata.st_nlink,
                          "mtime_ns": metadata.st_mtime_ns, "ctime_ns": metadata.st_ctime_ns})
            entry["xattrs"] = {key: os.getxattr(path, key, follow_symlinks=False).hex()
                               for key in sorted(os.listxattr(path, follow_symlinks=False))}
        return entries


def block_changes(archive, candidate):
    changes = []
    offset = 0
    with gzip.open(archive, "rb") as before, candidate.open("rb") as after:
        while True:
            a, b = before.read(4 * 1024 * 1024), after.read(4 * 1024 * 1024)
            if len(a) != len(b):
                raise ValueError("Block comparison length mismatch")
            if not a:
                break
            if a != b:
                for index in range(0, len(a), 4096):
                    old, new = a[index:index + 4096], b[index:index + 4096]
                    if old != new:
                        changes.append({"offset": offset + index, "bytes": len(old),
                                        "before_sha256": hashlib.sha256(old).hexdigest(),
                                        "after_sha256": hashlib.sha256(new).hexdigest()})
            offset += len(a)
    if offset != DATA_BYTES:
        raise ValueError("Incomplete block comparison")
    return changes


def analyze(directory):
    root = Path(__file__).resolve().parents[1] / "out"
    folder = Path(directory).absolute()
    if folder.resolve() != folder or not folder.is_relative_to(root.resolve()):
        raise ValueError("Backup must remain in workspace out without symlinks")
    archive, receipt_path = folder / "data.before.img.gz", folder / "capture.json"
    regular(archive)
    regular(receipt_path)
    receipt = json.loads(receipt_path.read_text())
    if (receipt["status"] != "HOST_ARCHIVE_AND_SOURCE_VERIFIED" or
            receipt["bytes"] != DATA_BYTES or
            receipt["sha256"] != receipt["independent_sha256"] or
            receipt["archive_bytes"] != archive.stat().st_size or
            receipt["archive_sha256"] != sha(archive)):
        raise ValueError("Verified capture receipt/archive required")
    if os.geteuid() != 0:
        raise ValueError("Read-only local loop inventory requires root")
    if shutil.disk_usage(folder).free < FLOOR + DATA_BYTES:
        raise ValueError("Insufficient worst-case working-copy headroom")
    out = folder / "offline-journal-trial"
    out.mkdir()
    candidate = out / "data.journal-replayed.img"
    print("EXPANDING_AND_VERIFYING_COMPLETE_BACKUP", flush=True)
    expand_verified(archive, candidate, DATA_BYTES, receipt["sha256"])
    version = run_log(["e2fsck", "-V"], out / "e2fsck-version.txt")
    if version.returncode != 0:
        raise ValueError("Cannot record e2fsck version")
    before_header = run_log(["tune2fs", "-l", str(candidate)], out / "header-before.txt")
    if before_header.returncode != 0:
        raise ValueError("Cannot read initial filesystem header")
    before_fields = header_fields(before_header.stdout)
    if before_fields["Filesystem UUID"] != "45daaa6e-724e-4d20-981c-602b3f72b8a2":
        raise ValueError("Wrong data filesystem UUID")
    run_log(["e2fsck", "-fn", str(candidate)], out / "readonly-fsck-before.txt")
    before = snapshot(candidate)
    save(out / "files-before.json", before)
    if sha(candidate) != receipt["sha256"]:
        raise ValueError("Read-only prechecks changed candidate")
    print("REPLAY_ON_LOCAL_REGULAR_COPY_ONLY", flush=True)
    replay = run_log(REPLAY_ARGS + [str(candidate)], out / "journal-only.txt")
    check_replay_result(replay)
    replay_sha = sha(candidate)
    after_header = run_log(["tune2fs", "-l", str(candidate)], out / "header-after.txt")
    if after_header.returncode != 0:
        raise ValueError("Cannot read resulting filesystem header")
    after_fields = header_fields(after_header.stdout)
    after_fsck = run_log(["e2fsck", "-fn", str(candidate)], out / "readonly-fsck-after.txt")
    check_readonly_result(after_fsck)
    if (after_fsck.returncode != 0 or
            after_fields["Filesystem UUID"] != before_fields["Filesystem UUID"] or
            after_fields["Filesystem state"] != "clean" or
            "needs_recovery" in after_fields["Filesystem features"].split()):
        raise ValueError("Copy is not clean after journal-only replay; no full repair attempted")
    after = snapshot(candidate)
    save(out / "files-after.json", after)
    file_delta = [{"path": name, "before": before.get(name), "after": after.get(name)}
                  for name in sorted(before.keys() | after.keys())
                  if before.get(name) != after.get(name)]
    save(out / "file-diff.json", file_delta)
    print("COMPARING_ALL_ORIGINAL_AND_RECOVERED_BLOCKS", flush=True)
    delta = block_changes(archive, candidate)
    save(out / "block-diff.json", delta)
    if sha(candidate) != replay_sha or sha(archive) != receipt["archive_sha256"]:
        raise ValueError("Backup or replay image changed during verification")
    save(out / "result.json", {
        "status": "OFFLINE_JOURNAL_REPLAY_VERIFIED_NOT_DEPLOYED",
        "original_sha256": receipt["sha256"], "candidate_sha256": replay_sha,
        "bytes": DATA_BYTES, "journal_only_exit": replay.returncode,
        "readonly_fsck_after_exit": after_fsck.returncode,
        "changed_4096_byte_blocks": len(delta), "changed_file_entries": len(file_delta),
        "before_entries": len(before), "after_entries": len(after),
        "tool_version": (version.stdout + version.stderr).strip(),
        "device_writes": False, "physical_recovery_authorized": False,
        "recipe_sha256": sha(Path(__file__)),
        "completed": datetime.now(timezone.utc).isoformat(),
    })
    print((out / "result.json").read_text(), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True)
    analyze(parser.parse_args().directory)

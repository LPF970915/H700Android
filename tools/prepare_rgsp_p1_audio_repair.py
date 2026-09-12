#!/usr/bin/env python3
"""Repair only a new local FAT copy, then verify contents and every byte delta."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile

from analyze_rgsp_data_copy import regular, run_log, save, sha
from compare_rgsp_image_files import inventory

SIZE = 268435456
SOURCE_SHA = "ee4b9a7ad5164f2b411f2555b935332dccfda76f321863cf620c31c52a9cc1b6"
LINUX_SHA = "d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5"


def require_clean(result):
    text = result.stdout + result.stderr
    if result.returncode or re.search(
        r"dirty bit|differences|wrong|truncat|corrupt|error|fixing|correcting|"
        r"reclaim|unconnected|bad cluster|modified|invalid|abort", text, re.I
    ):
        raise ValueError("Read-only FAT check is not clean")


@contextmanager
def mounted_readonly(image):
    regular(image, SIZE)
    mountpoint = tempfile.mkdtemp(prefix="rgsp-p1-readonly-")
    mounted = False
    try:
        subprocess.run(["mount", "-t", "vfat", "-o", "loop,ro,nodev,nosuid,noexec",
                        str(image), mountpoint], check=True, capture_output=True)
        mounted = True
        yield Path(mountpoint)
    finally:
        if mounted:
            subprocess.run(["umount", mountpoint], check=True, capture_output=True)
        os.rmdir(mountpoint)


def snapshot(image):
    with mounted_readonly(image) as root:
        def fail(error):
            raise error
        for _ in os.walk(root, onerror=fail):
            pass
        entries = inventory(root)
        for name, entry in entries.items():
            info = (root / name).stat()
            if stat.S_ISREG(info.st_mode):
                entry["size"] = info.st_size
            entry["mtime_ns"] = info.st_mtime_ns
        if entries["rgsp-linux-boot-original.img"]["sha256"] != LINUX_SHA:
            raise ValueError("Linux recovery hash changed")
        if "RGSP_ANDROID_TRY.ONCE" in entries:
            raise ValueError("Pending one-shot startup marker")
        return entries


def byte_changes(before, after):
    changes = []
    with before.open("rb") as a, after.open("rb") as b:
        offset = 0
        while True:
            x, y = a.read(4 * 1024 * 1024), b.read(4 * 1024 * 1024)
            if len(x) != len(y):
                raise ValueError("Image size changed")
            if not x:
                break
            if x != y:
                changes.extend({"offset": offset + i, "before": u, "after": v}
                               for i, (u, v) in enumerate(zip(x, y)) if u != v)
            offset += len(x)
    if len(changes) > 4096:
        raise ValueError("Unexpectedly broad FAT changes; preserve copy for review")
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    directory = args.directory.resolve(strict=True)
    source = directory / "anboot-before.img"
    regular(source, SIZE)
    receipt = json.loads((directory / "anboot-backup.json").read_text(encoding="utf-8-sig"))
    if (receipt["sha256"] != SOURCE_SHA or receipt["offset"] != 1048576
            or receipt["bytes"] != SIZE or sha(source) != SOURCE_SHA):
        raise ValueError("Fresh backup does not match this reviewed inspection")
    output = directory / "offline-review"
    output.mkdir()
    with tempfile.TemporaryDirectory(prefix="rgsp-p1-audio-copy-") as temporary:
        temp = Path(temporary)
        original, fixed = temp / "original.img", temp / "fixed.img"
        shutil.copyfile(source, original)
        shutil.copyfile(source, fixed)
        if sha(original) != SOURCE_SHA or sha(fixed) != SOURCE_SHA:
            raise ValueError("Working-copy verification failed")
        before_check = run_log(["fsck.fat", "-n", "-v", str(original)],
                               output / "before-fsck.log")
        if before_check.returncode != 1:
            raise ValueError("Expected the previously observed non-clean FAT state")
        result = run_log(["fsck.fat", "-a", "-v", str(fixed)], output / "copy-repair.log")
        if result.returncode not in (0, 1):
            raise ValueError("Copy repair failed")
        require_clean(run_log(["fsck.fat", "-n", "-v", str(fixed)], output / "after-fsck.log"))
        snapshots = [snapshot(image) for image in (original, fixed)]
        save(output / "before-files.json", snapshots[0])
        save(output / "after-files.json", snapshots[1])
        if snapshots[0] != snapshots[1]:
            raise ValueError("File contents, names, sizes or timestamps changed")
        if sha(original) != SOURCE_SHA or sha(source) != SOURCE_SHA:
            raise ValueError("Read-only source image changed")
        differences = byte_changes(original, fixed)
        save(output / "byte-diff.json", differences)
        target = output / "anboot-repaired.img"
        if target.exists():
            raise ValueError("Output already exists")
        shutil.copyfile(fixed, target)
        candidate_sha = sha(fixed)
        if sha(target) != candidate_sha:
            raise ValueError("Exported copy verification failed")
        save(output / "review.json", {
            "status": "OFFLINE_COPY_VERIFIED_NOT_DEPLOYED",
            "source_sha256": SOURCE_SHA, "candidate_sha256": candidate_sha,
            "bytes": SIZE, "changed_bytes": len(differences),
            "changed_sectors": sorted({entry["offset"] // 512 for entry in differences}),
            "entries": len(snapshots[0]), "all_file_contents_and_metadata_unchanged": True,
            "readonly_fat_check_clean": True, "device_writes": False,
        })
        print(f"P1_OFFLINE_COPY_VERIFIED SHA256={candidate_sha} CHANGED_BYTES={len(differences)}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Read-only file-content comparison between two local ext4 or FAT images."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile


def inventory(root):
    result = {}
    for base, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(base) / name
            info = path.lstat()
            entry = {"mode": stat.S_IMODE(info.st_mode), "uid": info.st_uid, "gid": info.st_gid}
            if stat.S_ISLNK(info.st_mode):
                entry["symlink"] = os.readlink(path)
            elif stat.S_ISREG(info.st_mode):
                h = hashlib.sha256()
                with path.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                        h.update(chunk)
                entry["sha256"] = h.hexdigest()
            elif stat.S_ISDIR(info.st_mode):
                entry["directory"] = True
            else:
                entry["device"] = info.st_rdev
            result[str(path.relative_to(root))] = entry
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--filesystem", choices=("ext4", "vfat"), default="ext4")
    args = parser.parse_args()
    images = [p.resolve(strict=True) for p in (args.before, args.after)]
    if not all(p.is_file() for p in images):
        raise ValueError("Only regular image files are accepted")
    with tempfile.TemporaryDirectory(prefix="rgsp-readonly-diff-") as temp:
        snapshots = []
        for index, image in enumerate(images):
            mountpoint = Path(temp) / str(index)
            mountpoint.mkdir()
            options = "loop,ro,noload" if args.filesystem == "ext4" else "loop,ro"
            subprocess.run(["mount", "-t", args.filesystem, "-o", options,
                            str(image), str(mountpoint)], check=True)
            try:
                snapshots.append(inventory(mountpoint))
            finally:
                subprocess.run(["umount", str(mountpoint)], check=True)
    before, after = snapshots
    changes = [{"path": p, "before": before.get(p), "after": after.get(p)}
               for p in sorted(before.keys() | after.keys()) if before.get(p) != after.get(p)]
    report = {"before": str(images[0]), "after": str(images[1]),
              "before_files": len(before), "after_files": len(after), "changes": changes}
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    for change in changes:
        print(change["path"])
    print(f"CHANGED_ENTRIES={len(changes)}")


if __name__ == "__main__":
    main()

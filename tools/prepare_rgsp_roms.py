#!/usr/bin/env python3
"""Apply pinned RGSP storage patches and sync their product inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = {
    "model/Disk.cpp": "13295efad5fdd9463005fc620d5efc5b346e9070594b4fccc06ec04eb76c2660",
    "model/PublicVolume.cpp": "6a2a44774b00d5c95412f710e3bb3ad73b52fc2bd220bedd310d428cae016431",
}
PATCHED = {
    "model/Disk.cpp": "334a59b13051b485a115660e71c4d6196d105a0986cadabf0577fede0727cf16",
    "model/PublicVolume.cpp": "3fbbe4e16dd00be3e0f3eac8bb682cd7d565a3dab12adecf5ec8bff8fe86ba88",
}
DEVICE_FILES = ("fstab.sun50iw9p1", "rgsp-kmsg-start.sh", "rgsp-firstboot.sh",
                "rgsp-roms-handoff.sh", "rgsp-roms-handoff.rc", "h700_rgsp.mk")
FRAMEWORK_FILE = "services/core/java/com/android/server/StorageManagerService.java"
FRAMEWORK_ORIGINAL = "36686a943f8a2c32df5f15e7e67a02078bfc80e592d999cf7e13acb9c7985830"
FRAMEWORK_PATCHED = "e60a5e7341a8f5a44c18fb6a6ab9e6fb82dffea2ada84f7ec0379b719925bc81"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(source):
    vold = source/"system/vold"
    patch = ROOT/"tools/rgsp-vold-roms.patch"
    receipt = ROOT/"out/rgsp-roms-source-sync.json"
    previous = {}
    if receipt.exists():
        saved = json.loads(receipt.read_text())
        if saved.get("source") == str(source):
            previous = saved.get("device_files", {})
    # First live trial before the source-sync receipt was introduced.
    previous.setdefault("rgsp-roms-handoff.sh",
                        "24ebddc6da8452de2588e9457cb58dc50e717a6b49c4919fac830b462f86cef8")
    framework = source/"frameworks/base"
    framework_patch = ROOT/"tools/rgsp-roms-visible.patch"
    framework_hash = digest(framework/FRAMEWORK_FILE)
    if framework_hash not in (FRAMEWORK_ORIGINAL, FRAMEWORK_PATCHED):
        raise ValueError("Unrecognized StorageManagerService changes preserved")
    if framework_hash == FRAMEWORK_ORIGINAL:
        subprocess.run(["patch", "--batch", "--forward", "--dry-run", "-p1",
                        "-i", str(framework_patch)], cwd=framework, check=True)
    already = all(digest(vold/name) == expected for name, expected in PATCHED.items())
    if not already:
        for name, expected in ORIGINAL.items():
            if digest(vold/name) != expected:
                raise ValueError(f"Unrecognized vold source changes preserved: {name}")
        subprocess.run(["patch", "--batch", "--forward", "--dry-run", "-p1", "-i", str(patch)],
                       cwd=vold, check=True)
    device = Path("device/roc/rgsp")
    for name in DEVICE_FILES:
        local = ROOT/"android/h700-android10"/device/name
        target = source/device/name
        if target.is_symlink():
            raise ValueError(f"Refusing source symlink: {target}")
        if target.exists() and digest(target) != digest(local):
            if digest(target) == previous.get(name):
                continue
            old = subprocess.check_output(["git", "-C", str(ROOT), "show",
                                          f"HEAD:android/h700-android10/{device}/{name}"])
            if target.read_text() != old.decode().replace("\r\n", "\n"):
                raise ValueError(f"Unrecognized device edits preserved: {target}")
    if not already:
        subprocess.run(["patch", "--batch", "--forward", "-p1", "-i", str(patch)],
                       cwd=vold, check=True)
    for name, expected in PATCHED.items():
        if digest(vold/name) != expected:
            raise ValueError(f"Patched source identity failed: {name}")
    if framework_hash == FRAMEWORK_ORIGINAL:
        subprocess.run(["patch", "--batch", "--forward", "-p1", "-i", str(framework_patch)],
                       cwd=framework, check=True)
    if digest(framework/FRAMEWORK_FILE) != FRAMEWORK_PATCHED:
        raise ValueError("StorageManagerService patched identity failed")
    for name in DEVICE_FILES:
        local = ROOT/"android/h700-android10"/device/name
        target = source/device/name
        if not target.exists() or digest(local) != digest(target):
            shutil.copyfile(local, target)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps({"source": str(source),
        "device_files": {name: digest(source/device/name) for name in DEVICE_FILES}}, indent=2)+"\n")
    for name in ORIGINAL:
        print(digest(vold/name), name)
    print("RGSP_ROMS_BUILD_INPUTS_SYNCHRONIZED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    prepare(parser.parse_args().source.resolve())

#!/usr/bin/env python3
"""Synchronize the RGSP overlay and verified local assets, without device access."""
import argparse
import hashlib
import json
import lzma
from pathlib import Path
import shutil
import subprocess

from prepare_rgsp_wifi_deployment import sha


def sync_overlay(workspace, source, previous=None):
    previous = previous or {}
    relative = Path("android/h700-android10/device/roc")
    names = subprocess.check_output(
        ["git", "-C", str(workspace), "ls-files", "--cached", "--others",
         "--exclude-standard", "-z", "--", str(relative)], text=True).split("\0")
    planned = []
    for name in sorted(set(filter(None, names))):
        local = workspace / name
        target = source / "device/roc" / Path(name).relative_to(relative)
        if target.is_symlink():
            raise ValueError(f"Refusing source symlink: {target}")
        if target.exists() and sha(target) != sha(local):
            old = subprocess.run(["git", "-C", str(workspace), "show", f"HEAD:{name}"],
                                 capture_output=True)
            previously_synced = previous.get(str(target.relative_to(source)))
            if sha(target) != previously_synced and (
                    old.returncode or hashlib.sha256(old.stdout).hexdigest() != sha(target)):
                raise ValueError(f"Unrecognized source-tree edits, preserved: {target}")
        planned.append((local, target))
    # Validate the entire overlay before changing any file.
    for local, target in planned:
        if not target.exists() or sha(target) != sha(local):
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(local, target)
    return {str(t.relative_to(source)): sha(t) for _, t in planned}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    root, source = args.workspace.resolve(), args.source.resolve()
    if not (source / "build/envsetup.sh").is_file() or str(source).startswith("/mnt/"):
        raise ValueError("Expected an Android source tree on the WSL Linux filesystem")
    payload = root / "out/h700-android10-b2"
    hashes = {}
    for line in (root / "docs/baselines/fix67-payload.sha256").read_text().splitlines():
        digest, name = line.split()
        hashes[name] = digest
    names = ("mali_kbase.h700.r20p0.ko.xz", "rgsp_fix63_graphics.rc", "rgsp-graphics-diag.sh")
    for name in names:
        if sha(payload / name) != hashes[name]:
            raise ValueError(f"Verified Fix67 input changed: {name}")
    module = lzma.decompress((payload / names[0]).read_bytes())
    if hashlib.sha256(module).hexdigest() != "987e2feb5621f455c139c9e93c0c2a972f6eee0478b755b2cdfecfeb249970a9":
        raise ValueError("Mali module mismatch")
    report = root / "out/rgsp-fix72-build-inputs.json"
    previous = {}
    if report.is_file():
        saved = json.loads(report.read_text())
        if saved["source"] != str(source):
            raise ValueError("Previous sync report belongs to another source tree")
        previous = saved["files"]
    files = sync_overlay(root, source, previous)
    dest = source / "device/roc/rgsp/prebuilts/local"
    generated = {
        "mali_kbase.ko": module,
        # Diagnostic screenshots must not capture a future password session.
        "rgsp_fix63_graphics.rc": (payload / names[1]).read_bytes().replace(
            b"    start rgsp-graphics-diag\n", b""),
        "rgsp-graphics-diag.sh": (payload / names[2]).read_bytes(),
        "set_rgsp_home.sh": (root / "tools/set_rgsp_home.sh").read_bytes(),
    }
    for name, data in generated.items():
        target = dest / name
        if target.is_symlink():
            raise ValueError(f"Refusing generated symlink: {target}")
        if target.exists() and sha(target) not in (
                hashlib.sha256(data).hexdigest(), previous.get(str(target.relative_to(source)))):
            raise ValueError(f"Unrecognized local generated edits, preserved: {target}")
    dest.mkdir(parents=True, exist_ok=True)
    for name, data in generated.items():
        target = dest / name
        target.write_bytes(data)
        files[str(target.relative_to(source))] = sha(target)
    report.write_text(json.dumps({"device_writes": False, "source": str(source),
                                 "files": files}, indent=2) + "\n")
    print(f"BUILD_INPUTS={report}")


if __name__ == "__main__":
    main()

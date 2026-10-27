#!/usr/bin/env python3
"""Refresh only p4 of an unqualified local v5d candidate, never a card."""
import argparse
import hashlib
import json
import os
from pathlib import Path

from build_rgsp_compact_image import IMAGE_SIZE, V5C_SHA
from verify_rgsp_compact_image import sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--boot", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    args = parser.parse_args()
    image = args.image.resolve()
    assert args.image.is_file() and not args.image.is_symlink()
    assert image.name == "H700_Android_SingleCard_v5d_BootInput.img"
    assert image.stat().st_size == IMAGE_SIZE
    metadata = image.with_suffix(".json")
    manifest = json.loads(metadata.read_text())
    assert manifest["release"] == "v5d BootInput"
    assert manifest["baseline"]["sha256"] == V5C_SHA
    assert manifest["status"] == "BUILT_PENDING_OFFLINE_FSCK_AND_PHYSICAL_TEST"
    assert not manifest["physical_boot_verified"]
    assert not image.with_suffix(".partial").exists()
    assert args.boot.is_file() and not args.boot.is_symlink()
    boot = args.boot.read_bytes()
    assert len(boot) == 64 * 1024**2
    assert hashlib.sha256(boot).hexdigest() == \
        "5e5a7245d90317b2c7ec2312fb8cc43cafdd1f27c0d7ff9969a6481200c4cf57"
    with image.open("rb") as stream:
        prefix = bytearray(stream.read(212 * 1024**2))
    record, = [item for item in manifest["ranges"] if item["name"] == "prefix"]
    assert hashlib.sha256(prefix).hexdigest() == record["sha256"]
    old = bytes(prefix[148 * 1024**2:212 * 1024**2])
    assert hashlib.sha256(old).hexdigest() == \
        "040f757d42391921ab7d5af38e90c81643a38d82f21f0fb278573469baafde60"
    args.backup.mkdir(parents=True, exist_ok=False)
    (args.backup/"manifest.before.json").write_bytes(metadata.read_bytes())
    (args.backup/"boot.before.img").write_bytes(old)
    manifest["status"] = "BOOT_REFRESH_IN_PROGRESS_NOT_FLASHABLE"
    metadata.write_text(json.dumps(manifest, indent=2) + "\n")
    prefix[148 * 1024**2:212 * 1024**2] = boot
    with image.open("r+b") as stream:
        stream.seek(148 * 1024**2)
        stream.write(boot)
        stream.flush()
        os.fsync(stream.fileno())
        stream.seek(0)
        assert stream.read(len(prefix)) == prefix
    record["sha256"] = hashlib.sha256(prefix).hexdigest()
    manifest["boot_refresh"] = {
        "before_sha256": hashlib.sha256(old).hexdigest(),
        "after_sha256": hashlib.sha256(boot).hexdigest(),
        "reason": "Package and execute qualified ARM dosfstools 4.2 plus CP850 conversion",
    }
    manifest["sha256"] = sha(image, progress=True)
    manifest["status"] = "BUILT_PENDING_OFFLINE_FSCK_AND_PHYSICAL_TEST"
    metadata.write_text(json.dumps(manifest, indent=2) + "\n")
    print("BOOT_REFRESHED_FULL_IMAGE_HASHED_GATE_STILL_REQUIRED", flush=True)


if __name__ == "__main__":
    main()

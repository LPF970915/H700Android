#!/usr/bin/env python3
"""Repack and verify the ROMS handoff without reading/building a complete image."""
import hashlib
from pathlib import Path
import shutil
import tempfile

from build_rgsp_compact_image import baseline_identity, default_baseline, ramdisk
from verify_rgsp_compact_image import verify_ramdisk


def main():
    baseline = default_baseline()
    with baseline.open("rb") as stream:
        original = stream.read(212 * 1024**2)
    assert hashlib.sha256(original).hexdigest() == baseline_identity(baseline)[1]
    tools = Path("/home/lpf/rgsp-grow-build")
    runtime = Path("/home/lpf/rgsp-grow-runtime/runtime")
    with tempfile.TemporaryDirectory(prefix="roms-boot-", dir=tools) as directory:
        build = Path(directory)
        for name in ("rgsp-grow-gpt", "rgsp-grow-fat"):
            shutil.copyfile(tools/name, build/name)
        prefix = ramdisk(bytearray(original), build, runtime, roms_vold=True)
        assert prefix[:148 * 1024**2] == original[:148 * 1024**2]
        verify_ramdisk(prefix, original, build, expected_roms_vold=True)
        print("ROMS_RAMDISK_KERNEL_DTB_GROW_RUNTIME_AND_MOUNT_ORDER_VERIFIED")


if __name__ == "__main__":
    main()

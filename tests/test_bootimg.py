#!/usr/bin/env python3
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "android_bootimg.py"


def align(v, p):
    return (v + p - 1) // p * p


def make_fixture(path: Path):
    page = 2048
    kernel = b"KERNEL" * 100
    ramdisk = b"RAMDISK" * 80
    second = b"SECOND"
    dtb = b"DTB" * 20
    header = bytearray(1632)
    header[:8] = b"ANDROID!"
    import struct
    struct.pack_into("<10I", header, 8, len(kernel), 0x40080000, len(ramdisk), 0x42000000,
                     len(second), 0x43000000, 0x40000100, page, len(dtb), 0)
    header[48:48 + 8] = b"sun50i_arm64"
    header[64:64 + 10] = b"console=ttyS0"
    out = bytearray(header)
    for blob in (kernel, ramdisk, second, dtb):
        out.extend(b"\0" * (align(len(out), page) - len(out)))
        out.extend(blob)
    out.extend(b"\0" * (align(len(out), page) - len(out)))
    out.extend(b"\xff" * (16384 - len(out)))
    path.write_bytes(out)
    return kernel, ramdisk, second, dtb


def run(*args):
    return subprocess.run([sys.executable, str(TOOL), *map(str, args)], check=True, capture_output=True, text=True)


def main():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        base = root / "boot.img"
        kernel, ramdisk, second, dtb = make_fixture(base)
        info = json.loads(run("inspect", base).stdout)
        assert info["page_size"] == 2048
        assert info["kernel_addr"] == 0x40080000
        extracted = root / "extract"
        run("extract", base, extracted)
        assert (extracted / "kernel").read_bytes() == kernel
        assert (extracted / "ramdisk").read_bytes() == ramdisk
        replacement = root / "kernel.new"
        replacement.write_bytes(b"NEW-KERNEL")
        packed = root / "probe.img"
        out = json.loads(run("pack", base, packed, "--kernel", replacement).stdout)
        info2 = json.loads(run("inspect", packed).stdout)
        assert info2["kernel_size"] == len(b"NEW-KERNEL")
        # Component sizes are page-aligned, so replacing a payload can keep the
        # total image size unchanged even though the kernel bytes changed.
        assert out["bytes"] == base.stat().st_size
        assert packed.read_bytes()[-64:] == base.read_bytes()[-64:]
        print("bootimg tests: ok")


if __name__ == "__main__":
    main()

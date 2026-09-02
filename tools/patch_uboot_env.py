#!/usr/bin/env python3
"""Patch a legacy U-Boot environment image with a reversible TF2 bootcmd."""

from __future__ import annotations

import argparse
import struct
import zlib
from pathlib import Path


ENV_SIZE = 0x20000

TF2_SCRIPT = (
    "if mmc dev 2; then "
    "if fatload mmc 2:1 44000000 RGSP_ANDROID_TRY.ONCE; then "
    "if fatload mmc 2:1 45000000 rgsp-android11-handoff-boot.img; then "
    "run setargs_nand; "
    'setenv bootargs "${bootargs} androidboot.hardware=rgsp androidboot.console=ttyS0 androidboot.selinux=permissive panic=10"; '
    "bootm 45000000; fi; fi; fi; "
    "mmc dev 0; run setargs_nand; run boot_normal"
)


def parse_env(raw: bytes) -> tuple[dict[str, str], str]:
    if len(raw) < ENV_SIZE:
        raise ValueError(f"environment input must be at least {ENV_SIZE} bytes")
    image = raw[:ENV_SIZE]
    stored = struct.unpack_from("<I", image, 0)[0]
    actual = zlib.crc32(image[4:]) & 0xFFFFFFFF
    if stored != actual:
        raise ValueError(f"CRC mismatch: stored=0x{stored:08x} actual=0x{actual:08x}")
    fields = image[4:].split(b"\0")
    env: dict[str, str] = {}
    for field in fields:
        if not field or field == b"\xff" * len(field):
            continue
        if b"=" not in field:
            continue
        key, value = field.split(b"=", 1)
        env[key.decode("ascii")] = value.decode("utf-8", "replace")
    return env, image[ENV_SIZE:]


def build_env(env: dict[str, str]) -> bytes:
    payload = bytearray(b"\xff" * (ENV_SIZE - 4))
    encoded = b"".join(f"{k}={v}".encode("utf-8") + b"\0" for k, v in env.items())
    if len(encoded) + 1 > len(payload):
        raise ValueError("environment variables exceed U-Boot environment size")
    payload[: len(encoded)] = encoded
    crc = zlib.crc32(payload) & 0xFFFFFFFF
    return struct.pack("<I", crc) + bytes(payload)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    raw = args.input.read_bytes()
    env, _tail = parse_env(raw)
    original = env.get("bootcmd")
    if not original:
        raise ValueError("bootcmd is missing")
    env["rgsp_bootcmd_orig"] = original
    env["rgsp_tf2_boot"] = TF2_SCRIPT
    env["bootcmd"] = "run rgsp_tf2_boot"
    args.output.write_bytes(build_env(env) + raw[ENV_SIZE:])
    print(f"original bootcmd: {original}")
    print(f"new bootcmd: {env['bootcmd']}")
    print(f"tf2 script bytes: {len(TF2_SCRIPT)}")
    print(f"output bytes: {args.output.stat().st_size}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import argparse
import hashlib
from pathlib import Path


EXPECTED_SOURCE_SHA256 = (
    "fac1800b68852e92c90e05a03ae27987c6d926ed3b1f1a96d4497d81e76f3e46"
)

PATCH_RANGES = (
    (0xE9B0, 0xE9DC),
    (0xF390, 0xF39C),
    (0xFF38, 0xFF5C),
    (0x10350, 0x10374),
    (0x11770, 0x11794),
    (0x11A80, 0x11A88),
    (0x11AF8, 0x11B1C),
    (0x11BA0, 0x11BA8),
    (0x11C18, 0x11C20),
    (0x11CA0, 0x11CA8),
    (0x12420, 0x12428),
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("stubs", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    source = args.source.read_bytes()
    stubs = args.stubs.read_bytes()
    source_sha = sha256(source)
    if source_sha != EXPECTED_SOURCE_SHA256:
        raise SystemExit(
            f"unexpected source SHA-256: {source_sha}; expected {EXPECTED_SOURCE_SHA256}"
        )

    patched = bytearray(source)
    for start, end in PATCH_RANGES:
        if end > len(source) or end > len(stubs):
            raise SystemExit(f"patch range 0x{start:x}-0x{end:x} is out of bounds")
        replacement = stubs[start:end]
        if not replacement or replacement == b"\x00" * len(replacement):
            raise SystemExit(f"empty stub at 0x{start:x}-0x{end:x}")
        patched[start:end] = replacement

    args.output.write_bytes(patched)
    print(f"source_sha256={source_sha}")
    print(f"patched_sha256={sha256(patched)}")
    for start, end in PATCH_RANGES:
        print(f"patched_range=0x{start:x}-0x{end:x}")


if __name__ == "__main__":
    main()

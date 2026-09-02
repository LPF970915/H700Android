#!/usr/bin/env python3
import argparse
import hashlib
from pathlib import Path


EXPECTED_SOURCE_SHA256 = (
    "bf45a5ae0bd61cd9ce43640ceaca5eca3bd83030c152da737ac42e594fa3f984"
)

PATCH_START = 0x10918
PATCH_END = 0x1093C
EXPECTED_ORIGINAL = bytes.fromhex(
    "ff0301d1fe0b00f9f65702a9f44f03a956d03bd5f30301aac81640f9e80700f93f0000f9"
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
            f"unexpected source SHA-256: {source_sha}; "
            f"expected {EXPECTED_SOURCE_SHA256}"
        )

    original = source[PATCH_START:PATCH_END]
    if original != EXPECTED_ORIGINAL:
        raise SystemExit(
            f"unexpected lgetfilecon bytes: {original.hex()} != "
            f"{EXPECTED_ORIGINAL.hex()}"
        )

    replacement = stubs[PATCH_START:PATCH_END]
    if len(replacement) != PATCH_END - PATCH_START:
        raise SystemExit("lgetfilecon stub is incomplete")
    if not replacement or replacement == b"\x00" * len(replacement):
        raise SystemExit("lgetfilecon stub is empty")

    patched = bytearray(source)
    patched[PATCH_START:PATCH_END] = replacement
    args.output.write_bytes(patched)

    print(f"source_sha256={source_sha}")
    print(f"patched_sha256={sha256(patched)}")
    print(f"patched_symbol=lgetfilecon offset=0x{PATCH_START:x}")


if __name__ == "__main__":
    main()

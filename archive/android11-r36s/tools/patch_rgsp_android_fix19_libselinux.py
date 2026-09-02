#!/usr/bin/env python3
import argparse
import hashlib
from pathlib import Path


EXPECTED_SOURCE_SHA256 = (
    "b80d7e10192a923126b5e9f82278b3a7603231722a1c546134fe6c13bbca7f61"
)

# AArch64: mov w0, #0; ret
RETURN_ZERO = bytes.fromhex("00008052c0035fd6")

PATCHES = (
    (0x11F08, bytes.fromhex("fe4fbfa948000090"), "selinux_status_updated"),
    (0x11FB0, bytes.fromhex("fd7bbca9f85f01a9"), "selinux_status_open"),
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    source = args.source.read_bytes()
    source_sha = sha256(source)
    if source_sha != EXPECTED_SOURCE_SHA256:
        raise SystemExit(
            f"unexpected source SHA-256: {source_sha}; "
            f"expected {EXPECTED_SOURCE_SHA256}"
        )

    patched = bytearray(source)
    for offset, expected, symbol in PATCHES:
        actual = source[offset : offset + len(expected)]
        if actual != expected:
            raise SystemExit(
                f"unexpected bytes for {symbol} at 0x{offset:x}: "
                f"{actual.hex()} != {expected.hex()}"
            )
        patched[offset : offset + len(RETURN_ZERO)] = RETURN_ZERO

    args.output.write_bytes(patched)
    print(f"source_sha256={source_sha}")
    print(f"patched_sha256={sha256(patched)}")
    for offset, _, symbol in PATCHES:
        print(f"patched_symbol={symbol} offset=0x{offset:x}")


if __name__ == "__main__":
    main()

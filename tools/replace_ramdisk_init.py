#!/usr/bin/env python3
"""Replace only the init entry in a gzip cpio-newc ramdisk."""

from __future__ import annotations

import argparse
import gzip
from pathlib import Path


def align4(value: int) -> int:
    return (value + 3) & ~3


def field(value: int) -> bytes:
    return f"{value:08x}".encode("ascii")


def replace_entry(blob: bytes, init_data: bytes) -> bytes:
    out = bytearray()
    offset = 0
    while offset + 110 <= len(blob):
        if blob[offset : offset + 6] != b"070701":
            raise ValueError(f"invalid cpio magic at offset {offset}")
        header = bytearray(blob[offset : offset + 110])
        namesize = int(header[94:102], 16)
        filesize = int(header[54:62], 16)
        name_start = offset + 110
        name_end = name_start + namesize
        data_start = align4(name_end)
        data_end = data_start + filesize
        next_offset = align4(data_end)
        name_raw = blob[name_start:name_end]
        name = name_raw[:-1].decode("utf-8", "replace") if name_raw.endswith(b"\0") else name_raw.decode("utf-8", "replace")
        if name == "init":
            header[54:62] = field(len(init_data))
            out.extend(header)
            out.extend(name_raw)
            out.extend(b"\0" * (align4(len(out)) - len(out)))
            out.extend(init_data)
            out.extend(b"\0" * (align4(len(out)) - len(out)))
        else:
            out.extend(blob[offset:next_offset])
        offset = next_offset
        if name == "TRAILER!!!":
            break
    if offset > len(blob):
        raise ValueError("cpio entry extends beyond archive")
    return bytes(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("init", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with gzip.open(args.source, "rb") as stream:
        original = stream.read()
    rebuilt = replace_entry(original, args.init.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=6, mtime=0) as stream:
            stream.write(rebuilt)
    print(f"ramdisk: {args.output} ({args.output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

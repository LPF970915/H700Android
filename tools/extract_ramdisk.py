#!/usr/bin/env python3
"""Extract a gzip-compressed cpio newc ramdisk without external cpio tools."""

from __future__ import annotations

import argparse
import gzip
import os
import stat
from pathlib import Path, PurePosixPath


HEADER_SIZE = 110


def align4(value: int) -> int:
    return (value + 3) & ~3


def safe_target(root: Path, name: str) -> Path:
    rel = PurePosixPath(name)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"unsafe archive path: {name!r}")
    return root.joinpath(*rel.parts)


def extract(archive: Path, out: Path) -> None:
    raw = gzip.decompress(archive.read_bytes())
    out.mkdir(parents=True, exist_ok=True)
    offset = 0

    while offset + HEADER_SIZE <= len(raw):
        header = raw[offset:offset + HEADER_SIZE]
        if header[:6] not in (b"070701", b"070702"):
            raise ValueError(f"invalid newc header at offset {offset}")
        values = [int(header[pos:pos + 8], 16) for pos in range(6, 110, 8)]
        mode = values[1]
        file_size = values[6]
        name_size = values[11]
        offset += HEADER_SIZE

        name_blob = raw[offset:offset + name_size]
        if len(name_blob) != name_size or not name_blob.endswith(b"\0"):
            raise ValueError("truncated newc filename")
        name = name_blob[:-1].decode("utf-8")
        offset = align4(offset + name_size)

        data = raw[offset:offset + file_size]
        if len(data) != file_size:
            raise ValueError(f"truncated newc payload: {name}")
        offset = align4(offset + file_size)

        if name == "TRAILER!!!":
            return
        if name == ".":
            os.chmod(out, stat.S_IMODE(mode))
            continue

        target = safe_target(out, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        if stat.S_ISDIR(mode):
            target.mkdir(exist_ok=True)
            os.chmod(target, stat.S_IMODE(mode))
        elif stat.S_ISLNK(mode):
            target.symlink_to(data.decode("utf-8"))
        elif stat.S_ISREG(mode):
            target.write_bytes(data)
            os.chmod(target, stat.S_IMODE(mode))
        else:
            raise ValueError(f"unsupported ramdisk entry type: {name}")

    raise ValueError("newc trailer not found")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    extract(args.archive, args.out)
    print(f"extracted: {args.archive} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

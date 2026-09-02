#!/usr/bin/env python3
"""Create a gzip-compressed cpio newc archive for the early boot probe."""

from __future__ import annotations

import argparse
import gzip
import os
import stat
import time
from pathlib import Path


def field(value: int) -> bytes:
    return f"{value:08x}".encode("ascii")


def record(name: str, mode: int, data: bytes, ino: int) -> bytes:
    name_b = name.encode("utf-8") + b"\0"
    header = b"070701" + b"".join([
        field(ino), field(mode), field(0), field(0), field(1), field(int(time.time())),
        field(len(data)), field(0), field(0), field(0), field(0), field(len(name_b)), field(0)
    ])
    blob = header + name_b
    blob += b"\0" * ((-len(blob)) % 4)
    blob += data
    blob += b"\0" * ((-len(blob)) % 4)
    return blob


def build(root: Path) -> bytes:
    out = bytearray()
    ino = 1
    paths = [root] + sorted(root.rglob("*"), key=lambda p: (len(p.relative_to(root).parts), str(p)))
    for path in paths:
        rel = "." if path == root else str(path.relative_to(root)).replace(os.sep, "/")
        st = path.lstat()
        mode = st.st_mode
        if stat.S_ISDIR(mode):
            data = b""
        elif stat.S_ISLNK(mode):
            data = os.readlink(path).encode("utf-8")
        elif stat.S_ISREG(mode):
            data = path.read_bytes()
        else:
            raise ValueError(f"unsupported ramdisk entry: {path}")
        out.extend(record(rel, mode, data, ino))
        ino += 1
    out.extend(record("TRAILER!!!", stat.S_IFREG, b"", ino))
    return bytes(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    if not args.root.is_dir():
        parser.error(f"missing ramdisk root: {args.root}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=6, mtime=0) as stream:
            stream.write(build(args.root))
    print(f"ramdisk: {args.out} ({args.out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Patch one file in a gzip cpio newc ramdisk while preserving metadata."""

from __future__ import annotations

import argparse
import gzip
import stat
import struct
from pathlib import Path


def align(v: int) -> int:
    return (v + 3) // 4 * 4


def parse(blob: bytes):
    entries = []
    off = 0
    while off + 110 <= len(blob) and blob[off:off + 6] == b"070701":
        fields = [int(blob[off + i:off + i + 8], 16) for i in range(6, 110, 8)]
        ino, mode, uid, gid, nlink, mtime, size, devmajor, devminor, rdevmajor, rdevminor, namesize, check = fields
        name_end = off + 110 + namesize
        name = blob[off + 110:name_end - 1].decode("utf-8", "replace")
        data_start = align(name_end)
        data = blob[data_start:data_start + size]
        entries.append({"name": name, "ino": ino, "mode": mode, "uid": uid, "gid": gid, "nlink": nlink,
                        "mtime": mtime, "data": data, "devmajor": devmajor, "devminor": devminor,
                        "rdevmajor": rdevmajor, "rdevminor": rdevminor, "check": check})
        off = align(data_start + size)
        if name == "TRAILER!!!":
            break
    if not entries or entries[-1]["name"] != "TRAILER!!!":
        raise ValueError("invalid or incomplete cpio newc archive")
    return entries


def emit(entry):
    name = entry["name"].encode("utf-8") + b"\0"
    data = entry["data"]
    fields = [entry["ino"], entry["mode"], entry["uid"], entry["gid"], entry["nlink"], entry["mtime"],
              len(data), entry["devmajor"], entry["devminor"], entry["rdevmajor"], entry["rdevminor"], len(name), entry["check"]]
    header = b"070701" + b"".join(f"{x:08x}".encode("ascii") for x in fields)
    blob = header + name
    blob += b"\0" * (align(len(blob)) - len(blob))
    blob += data
    blob += b"\0" * (align(len(blob)) - len(blob))
    return blob


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--init", type=Path, required=True)
    args = parser.parse_args()
    source = gzip.open(args.source, "rb").read()
    entries = parse(source)
    replacement = args.init.read_bytes()
    found = False
    for entry in entries:
        if entry["name"] == "init":
            entry["data"] = replacement
            entry["mode"] = stat.S_IFREG | 0o755
            found = True
            break
    if not found:
        raise ValueError("ramdisk has no top-level init entry")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    raw = b"".join(emit(entry) for entry in entries)
    with args.out.open("wb") as stream:
        with gzip.GzipFile(fileobj=stream, mode="wb", compresslevel=6, mtime=0) as gz:
            gz.write(raw)
    print(f"patched ramdisk: {args.out} ({args.out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

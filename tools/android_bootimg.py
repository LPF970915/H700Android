#!/usr/bin/env python3
"""Inspect, extract and conservatively repack legacy Android boot images.

The RGSP report identifies a legacy Android boot image with 2048-byte pages.
This tool preserves unknown header bytes and non-replaced components so it can
be used as a local probe builder without guessing the vendor image layout.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import struct
import sys
from pathlib import Path

MAGIC = b"ANDROID!"
LEGACY_HEADER_SIZE = 1632


def align(value: int, page: int) -> int:
    return (value + page - 1) // page * page


def read_header(path: Path) -> tuple[bytearray, dict]:
    data = path.read_bytes()
    if len(data) < LEGACY_HEADER_SIZE or data[:8] != MAGIC:
        raise ValueError(f"not a legacy Android boot image: {path}")
    fields = struct.unpack_from("<10I", data, 8)
    kernel_size, kernel_addr, ramdisk_size, ramdisk_addr, second_size, second_addr, tags_addr, page_size, dt_size, unused = fields
    if page_size < 512 or page_size > 65536 or page_size & (page_size - 1):
        raise ValueError(f"invalid page size {page_size}")
    name = bytes(data[48:64]).split(b"\0", 1)[0].decode("ascii", "replace")
    cmdline = bytes(data[64:576]).split(b"\0", 1)[0].decode("ascii", "replace")
    extra = bytes(data[608:1632]).split(b"\0", 1)[0].decode("ascii", "replace")
    header = {
        "kernel_size": kernel_size,
        "kernel_addr": kernel_addr,
        "ramdisk_size": ramdisk_size,
        "ramdisk_addr": ramdisk_addr,
        "second_size": second_size,
        "second_addr": second_addr,
        "tags_addr": tags_addr,
        "page_size": page_size,
        "dt_size": dt_size,
        "unused": unused,
        "name": name,
        "cmdline": cmdline,
        "extra_cmdline": extra,
        "header_size": LEGACY_HEADER_SIZE,
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    # Some Allwinner images keep the legacy dt_size field at 2 while appending
    # a normal FDT blob. Detect and preserve that vendor layout instead of
    # truncating the DTB during extraction or repacking.
    offsets = component_offsets(header)
    if offsets["dtb"] + 8 <= len(data) and data[offsets["dtb"]:offsets["dtb"] + 4] == b"\xd0\x0d\xfe\xed":
        fdt_size = struct.unpack_from(">I", data, offsets["dtb"] + 4)[0]
        if 40 <= fdt_size <= len(data) - offsets["dtb"]:
            header["dt_size_detected"] = fdt_size
            header["dt_format"] = "fdt"
    header["header_blob_size"] = align(LEGACY_HEADER_SIZE, page_size)
    return bytearray(data[:header["header_blob_size"]]), header


def component_offsets(h: dict) -> dict[str, int]:
    page = h["page_size"]
    kernel = align(h.get("header_blob_size", h["header_size"]), page)
    ramdisk = align(kernel + h["kernel_size"], page)
    second = align(ramdisk + h["ramdisk_size"], page)
    dtb = align(second + h["second_size"], page)
    return {"kernel": kernel, "ramdisk": ramdisk, "second": second, "dtb": dtb}


def extract(args: argparse.Namespace) -> None:
    image = Path(args.image)
    data, h = read_header(image)
    offsets = component_offsets(h)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    raw = image.read_bytes()
    dtb_size = h.get("dt_size_detected", h["dt_size"])
    for name, size in (("kernel", h["kernel_size"]), ("ramdisk", h["ramdisk_size"]), ("second", h["second_size"]), ("dtb", dtb_size)):
        if not size:
            continue
        start = offsets[name]
        payload = raw[start:start + size]
        (out / name).write_bytes(payload)
        if name == "ramdisk" and payload[:2] == b"\x1f\x8b":
            (out / "ramdisk.gz").write_bytes(payload)
    (out / "header.json").write_text(json.dumps({"image": str(image), "header": h, "offsets": offsets}, indent=2), encoding="utf-8")
    print(json.dumps({"image": str(image), "header": h, "offsets": offsets}, indent=2))


def inspect(args: argparse.Namespace) -> None:
    _, h = read_header(Path(args.image))
    h["offsets"] = component_offsets(h)
    print(json.dumps(h, indent=2))


def pack(args: argparse.Namespace) -> None:
    template = Path(args.template)
    header, h = read_header(template)
    offsets = component_offsets(h)
    original = template.read_bytes()

    def payload(name: str, override: str | None) -> bytes:
        if override:
            return Path(override).read_bytes()
        size = h.get("dt_size_detected", h["dt_size"]) if name == "dtb" else h[f"{name}_size"]
        return original[offsets[name]:offsets[name] + size] if size else b""

    kernel = payload("kernel", args.kernel)
    ramdisk = payload("ramdisk", args.ramdisk)
    second = payload("second", args.second)
    dtb = payload("dtb", args.dtb)
    h["kernel_size"], h["ramdisk_size"] = len(kernel), len(ramdisk)
    h["second_size"] = len(second)
    # Preserve the vendor's raw dt_size value. The detected FDT length is
    # carried in the payload and is reported by inspect/extract.
    if "dt_size_detected" not in h:
        h["dt_size"] = len(dtb)
    struct.pack_into("<I", header, 8, len(kernel))
    struct.pack_into("<I", header, 16, len(ramdisk))
    struct.pack_into("<I", header, 24, len(second))
    if "dt_size_detected" not in h:
        struct.pack_into("<I", header, 40, len(dtb))

    page = h["page_size"]
    result = bytearray(header)
    for blob in (kernel, ramdisk, second, dtb):
        result.extend(b"\0" * (align(len(result), page) - len(result)))
        result.extend(blob)
    result.extend(b"\0" * (align(len(result), page) - len(result)))
    # The captured RGSP partition is a fixed-size 64 MiB block device image
    # whose unused area is 0xff (erased storage), not zero-filled. Preserve
    # that tail so a generated probe remains safe to write to the same-sized
    # partition and an identity repack can be byte-for-byte reproducible.
    if len(result) > len(original):
        raise ValueError(f"repacked image exceeds template size ({len(result)} > {len(original)})")
    if len(result) < len(original):
        tail = original[len(result):]
        fill = 0xFF if tail.count(0xFF) > len(tail) * 0.9 else 0x00
        result.extend(bytes([fill]) * (len(original) - len(result)))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(result)
    print(json.dumps({"out": str(out), "bytes": len(result), "sha256": hashlib.sha256(result).hexdigest(), "header": h}, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("inspect",):
        p = sub.add_parser(command)
        p.add_argument("image")
        p.set_defaults(func=inspect)
    p = sub.add_parser("extract")
    p.add_argument("image")
    p.add_argument("out")
    p.set_defaults(func=extract)
    p = sub.add_parser("pack")
    p.add_argument("template")
    p.add_argument("out")
    p.add_argument("--kernel")
    p.add_argument("--ramdisk")
    p.add_argument("--second")
    p.add_argument("--dtb")
    p.set_defaults(func=pack)
    args = parser.parse_args()
    try:
        args.func(args)
    except (OSError, ValueError, struct.error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

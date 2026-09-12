#!/usr/bin/env python3
"""Stream an Android sparse image to one explicit block device.

The target is deliberately restricted to an mmc partition. DONT_CARE chunks
are skipped, while every RAW chunk is read back and verified after fsync.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import struct
import sys
import urllib.request


SPARSE_MAGIC = 0xED26FF3A
CHUNK_RAW = 0xCAC1
CHUNK_FILL = 0xCAC2
CHUNK_DONT_CARE = 0xCAC3
CHUNK_CRC32 = 0xCAC4


def read_exact(stream, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        piece = stream.read(size - len(data))
        if not piece:
            raise RuntimeError(f"unexpected EOF: wanted {size} bytes")
        data.extend(piece)
    return bytes(data)


def write_all(fd: int, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        written = os.write(fd, data[offset:])
        if written <= 0:
            raise RuntimeError("short block-device write")
        offset += written


def device_size(path: str) -> int:
    name = os.path.basename(path)
    with open(f"/sys/class/block/{name}/size", "r", encoding="ascii") as stream:
        return int(stream.read().strip()) * 512


def flash(url: str, device: str) -> None:
    if not device.startswith("/dev/mmcblk1p"):
        raise RuntimeError(f"refusing non-RGSP-TF2 target: {device}")

    with urllib.request.urlopen(url, timeout=60) as source:
        header = read_exact(source, 28)
        magic, major, minor, file_header, chunk_header, block_size, total_blocks, total_chunks, checksum = struct.unpack(
            "<I4H4I", header
        )
        if magic != SPARSE_MAGIC or major != 1:
            raise RuntimeError("unsupported Android sparse image")
        if file_header < 28 or chunk_header < 12 or block_size == 0:
            raise RuntimeError("invalid sparse header")
        if file_header > 28:
            read_exact(source, file_header - 28)

        expanded_size = total_blocks * block_size
        capacity = device_size(device)
        if expanded_size > capacity:
            raise RuntimeError(f"image is larger than target: {expanded_size} > {capacity}")
        print(f"image_bytes={expanded_size} target_bytes={capacity} chunks={total_chunks} checksum=0x{checksum:08x}")

        raw_ranges: list[tuple[int, int, str]] = []
        position = 0
        fd = os.open(device, os.O_WRONLY)
        try:
            for index in range(total_chunks):
                chunk = read_exact(source, chunk_header)
                chunk_type, _reserved, blocks, total_size = struct.unpack("<2H2I", chunk[:12])
                payload_size = total_size - chunk_header
                chunk_bytes = blocks * block_size
                if total_size < chunk_header:
                    raise RuntimeError(f"chunk {index}: invalid size")

                if chunk_type == CHUNK_RAW:
                    if payload_size != chunk_bytes:
                        raise RuntimeError(f"chunk {index}: RAW size mismatch")
                    digest = hashlib.sha256()
                    os.lseek(fd, position, os.SEEK_SET)
                    remaining = payload_size
                    while remaining:
                        piece = read_exact(source, min(1024 * 1024, remaining))
                        write_all(fd, piece)
                        digest.update(piece)
                        remaining -= len(piece)
                    raw_ranges.append((position, payload_size, digest.hexdigest()))
                elif chunk_type == CHUNK_FILL:
                    if payload_size != 4:
                        raise RuntimeError(f"chunk {index}: FILL size mismatch")
                    read_exact(source, 4)
                elif chunk_type == CHUNK_DONT_CARE:
                    if payload_size != 0:
                        raise RuntimeError(f"chunk {index}: DONT_CARE payload")
                elif chunk_type == CHUNK_CRC32:
                    if payload_size != 4 or blocks != 0:
                        raise RuntimeError(f"chunk {index}: CRC32 size mismatch")
                    read_exact(source, 4)
                else:
                    raise RuntimeError(f"chunk {index}: unknown type 0x{chunk_type:04x}")

                position += chunk_bytes
                print(f"chunk={index + 1}/{total_chunks} expanded={position}", flush=True)
        finally:
            os.fsync(fd)
            os.close(fd)

    read_fd = os.open(device, os.O_RDONLY)
    try:
        for position, length, expected in raw_ranges:
            os.lseek(read_fd, position, os.SEEK_SET)
            digest = hashlib.sha256()
            remaining = length
            while remaining:
                piece = os.read(read_fd, min(1024 * 1024, remaining))
                if not piece:
                    raise RuntimeError("short block-device readback")
                digest.update(piece)
                remaining -= len(piece)
            actual = digest.hexdigest()
            if actual != expected:
                raise RuntimeError(f"readback mismatch at {position}: {actual} != {expected}")
    finally:
        os.close(read_fd)

    print(f"SPARSE_FLASH_OK raw_chunks_verified={len(raw_ranges)}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("device")
    args = parser.parse_args()
    try:
        flash(args.url, args.device)
    except (OSError, RuntimeError, urllib.error.URLError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

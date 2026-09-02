#!/usr/bin/env python3
"""Convert an Android sparse image to a raw, filesystem-sparse image."""

from __future__ import annotations

import argparse
import os
import struct
import sys


SPARSE_MAGIC = 0xED26FF3A
CHUNK_RAW = 0xCAC1
CHUNK_FILL = 0xCAC2
CHUNK_DONT_CARE = 0xCAC3
CHUNK_CRC32 = 0xCAC4


def read_exact(stream, size: int) -> bytes:
    data = stream.read(size)
    if len(data) != size:
        raise ValueError(f"unexpected EOF: wanted {size} bytes, got {len(data)}")
    return data


def convert(source_path: str, output_path: str) -> None:
    with open(source_path, "rb") as source:
        header = read_exact(source, 28)
        (
            magic,
            major,
            minor,
            file_header_size,
            chunk_header_size,
            block_size,
            total_blocks,
            total_chunks,
            image_checksum,
        ) = struct.unpack("<I4H4I", header)

        if magic != SPARSE_MAGIC:
            raise ValueError(f"not an Android sparse image: magic=0x{magic:08x}")
        if major != 1:
            raise ValueError(f"unsupported sparse major version: {major}.{minor}")
        if file_header_size < len(header) or chunk_header_size < 12:
            raise ValueError("invalid sparse header sizes")
        if block_size == 0 or block_size % 4 != 0:
            raise ValueError(f"invalid sparse block size: {block_size}")

        source.seek(file_header_size)
        output_blocks = 0
        counts = {CHUNK_RAW: 0, CHUNK_FILL: 0, CHUNK_DONT_CARE: 0, CHUNK_CRC32: 0}

        with open(output_path, "wb") as output:
            for chunk_index in range(total_chunks):
                chunk_header = read_exact(source, chunk_header_size)
                chunk_type, reserved, chunk_blocks, total_size = struct.unpack(
                    "<2H2I", chunk_header[:12]
                )
                del reserved
                data_size = total_size - chunk_header_size
                expanded_size = chunk_blocks * block_size

                if total_size < chunk_header_size:
                    raise ValueError(f"chunk {chunk_index}: invalid total size")
                if chunk_type == CHUNK_RAW:
                    if data_size != expanded_size:
                        raise ValueError(f"chunk {chunk_index}: invalid RAW size")
                    remaining = data_size
                    while remaining:
                        piece = read_exact(source, min(1024 * 1024, remaining))
                        output.write(piece)
                        remaining -= len(piece)
                elif chunk_type == CHUNK_FILL:
                    if data_size != 4:
                        raise ValueError(f"chunk {chunk_index}: invalid FILL size")
                    pattern = read_exact(source, 4)
                    piece = pattern * (min(expanded_size, 1024 * 1024) // 4)
                    remaining = expanded_size
                    while remaining:
                        write_size = min(len(piece), remaining)
                        output.write(piece[:write_size])
                        remaining -= write_size
                elif chunk_type == CHUNK_DONT_CARE:
                    if data_size != 0:
                        raise ValueError(f"chunk {chunk_index}: invalid DONT_CARE size")
                    output.seek(expanded_size, os.SEEK_CUR)
                elif chunk_type == CHUNK_CRC32:
                    if data_size != 4 or chunk_blocks != 0:
                        raise ValueError(f"chunk {chunk_index}: invalid CRC32 size")
                    read_exact(source, 4)
                else:
                    raise ValueError(f"chunk {chunk_index}: unknown type 0x{chunk_type:04x}")

                counts[chunk_type] += 1
                output_blocks += chunk_blocks

            if output_blocks != total_blocks:
                raise ValueError(
                    f"block count mismatch: expected {total_blocks}, got {output_blocks}"
                )
            output.truncate(total_blocks * block_size)

        trailing = source.read(1)
        if trailing:
            raise ValueError("unexpected trailing data after sparse chunks")

    print(f"sparse_version={major}.{minor}")
    print(f"block_size={block_size}")
    print(f"total_blocks={total_blocks}")
    print(f"total_chunks={total_chunks}")
    print(f"raw_size={total_blocks * block_size}")
    print(f"image_checksum=0x{image_checksum:08x}")
    print(
        "chunk_counts="
        f"raw:{counts[CHUNK_RAW]},fill:{counts[CHUNK_FILL]},"
        f"dont_care:{counts[CHUNK_DONT_CARE]},crc32:{counts[CHUNK_CRC32]}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("output")
    args = parser.parse_args()

    try:
        convert(args.source, args.output)
    except (OSError, ValueError, struct.error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

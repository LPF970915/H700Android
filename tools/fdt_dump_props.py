#!/usr/bin/env python3
"""Print selected flattened-device-tree properties without requiring dtc."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


FDT_BEGIN_NODE = 1
FDT_END_NODE = 2
FDT_PROP = 3
FDT_NOP = 4
FDT_END = 9


def align4(value: int) -> int:
    return (value + 3) & ~3


def display(data: bytes) -> str:
    if data and data[-1] == 0 and all(byte == 0 or 32 <= byte < 127 for byte in data):
        return repr(data.rstrip(b'\0').decode('ascii', 'replace'))
    if len(data) % 4 == 0:
        values = struct.unpack(f'>{len(data) // 4}I', data)
        return ' '.join(f'0x{value:x} ({value})' for value in values)
    return data.hex()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('dtb')
    parser.add_argument('terms', nargs='+')
    args = parser.parse_args()

    blob = Path(args.dtb).read_bytes()
    header = struct.unpack_from('>10I', blob)
    if header[0] != 0xD00DFEED:
        raise SystemExit('not an FDT blob')
    struct_offset, strings_offset = header[2], header[3]
    pos = struct_offset
    stack: list[str] = []
    terms = tuple(term.lower() for term in args.terms)

    while True:
        token = struct.unpack_from('>I', blob, pos)[0]
        pos += 4
        if token == FDT_BEGIN_NODE:
            end = blob.index(0, pos)
            stack.append(blob[pos:end].decode('ascii', 'replace'))
            pos = align4(end + 1)
        elif token == FDT_END_NODE:
            stack.pop()
        elif token == FDT_PROP:
            length, name_offset = struct.unpack_from('>II', blob, pos)
            pos += 8
            data = blob[pos:pos + length]
            pos = align4(pos + length)
            name_end = blob.index(0, strings_offset + name_offset)
            name = blob[strings_offset + name_offset:name_end].decode('ascii', 'replace')
            path = '/' + '/'.join(part for part in stack if part)
            haystack = f'{path}/{name}'.lower()
            if any(term in haystack for term in terms):
                print(f'{path}: {name} = {display(data)}')
        elif token == FDT_NOP:
            continue
        elif token == FDT_END:
            break
        else:
            raise SystemExit(f'unknown token {token} at 0x{pos - 4:x}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

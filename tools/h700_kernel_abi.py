"""Validate a locally built add-on against the pinned H700 4.9.170 kernel.

No loading or version rewriting. Boot/kernel and reference modules stay local.
The Image table locations belong only to the SHA pinned below; a different
kernel requires a new profile, never a best-effort offset or CRC substitution.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import struct

from android_bootimg import read_header, component_offsets

KERNEL_SHA = '3328c2fab9f19f7ea6a80e34b0a76238cf594bc631f77e05fec32f8adabad042'
BASE = 0xffffff8008080000
EXPORT_START, EXPORT_END, CRC_START = 0xc59b08, 0xc7bbb8, 0xc7bbb8


def elf_sections(path):
    data = path.read_bytes()
    if data[:6] != b'\x7fELF\x02\x01':
        raise ValueError('Expected little-endian ELF64: ' + str(path))
    offset = struct.unpack_from('<Q', data, 0x28)[0]
    size, count, names = struct.unpack_from('<HHH', data, 0x3a)
    sections = [struct.unpack_from('<IIQQQQIIQQ', data, offset + i * size) for i in range(count)]
    name_section = sections[names]
    strings = data[name_section[4]:name_section[4] + name_section[5]]
    return data, sections, {strings[s[0]:].split(b'\0')[0].decode(): s for s in sections}


def versions(path):
    data, _, sections = elf_sections(path)
    section = sections['__versions']
    content = data[section[4]:section[4] + section[5]]
    assert len(content) % 64 == 0
    return {content[i + 8:i + 64].split(b'\0')[0].decode(): struct.unpack_from('<Q', content, i)[0]
            for i in range(0, len(content), 64)}


def undefined_symbols(path):
    data, sections, named = elf_sections(path)
    symbols = named['.symtab']
    names = sections[symbols[6]]
    strings = data[names[4]:names[4] + names[5]]
    result = set()
    for offset in range(symbols[4], symbols[4] + symbols[5], symbols[9]):
        name, info, _, index, _, _ = struct.unpack_from('<IBBHQQ', data, offset)
        if name and index == 0 and info >> 4 != 2:  # optional weak imports are not required
            result.add(strings[name:].split(b'\0')[0].decode())
    return result


def exports(boot):
    _, header = read_header(boot)
    offset = component_offsets(header)['kernel']
    kernel = boot.read_bytes()[offset:offset + header['kernel_size']]
    if kernel.startswith(b'\x1f\x8b'):
        kernel = gzip.decompress(kernel)
    digest = hashlib.sha256(kernel).hexdigest()
    if digest != KERNEL_SHA:
        raise ValueError('Unsupported kernel SHA-256: ' + digest)
    expanded = bytearray(kernel)
    # R_AARCH64_RELATIVE records in this Image use 24-byte RELA entries. Their
    # location/alignment is pinned by the kernel hash, and destination writes
    # apply only to this offline bytearray, never a device or boot image.
    applied = 0
    for match in re.finditer(re.escape(struct.pack('<Q', 0x403)), kernel):
        where = match.start() - 8
        if where < 0 or (where - 0xebe8f8) % 24:
            continue
        target, kind, value = struct.unpack_from('<QQQ', kernel, where)
        if BASE <= target <= BASE + len(kernel) - 8:
            struct.pack_into('<Q', expanded, target - BASE, value)
            applied += 1
    assert applied == 93585
    result = {}
    for i, where in enumerate(range(EXPORT_START, EXPORT_END, 16)):
        _, pointer = struct.unpack_from('<QQ', expanded, where)
        assert BASE <= pointer < BASE + len(kernel)
        name = bytes(expanded[pointer - BASE:pointer - BASE + 150]).split(b'\0')[0]
        assert re.fullmatch(rb'[A-Za-z_][A-Za-z_0-9]*', name)
        name = name.decode()
        assert name not in result
        result[name] = struct.unpack_from('<Q', expanded, CRC_START + i * 8)[0]
    assert len(result) == 8715
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--boot', required=True, type=Path)
    parser.add_argument('--reference-module', action='append', required=True, type=Path)
    parser.add_argument('--symvers', required=True, type=Path)
    parser.add_argument('--module', required=True, type=Path)
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    kernel = exports(args.boot)
    reference = {}
    for path in args.reference_module:
        for name, crc in versions(path).items():
            assert reference.get(name, crc) == crc, 'Reference modules disagree: ' + name
            assert kernel.get(name) == crc, 'Reference/kernel mismatch: ' + name
            reference[name] = crc
    assert len(reference) >= 400, 'Need both known working Wi-Fi and Mali references'
    local = {parts[1]: int(parts[0], 16) for line in args.symvers.read_text().splitlines()
             if (parts := line.split())}
    for name, crc in local.items():
        assert kernel.get(name) == crc, 'Local headers/kernel mismatch: ' + name
    module = versions(args.module)
    assert 'module_layout' in module
    assert undefined_symbols(args.module) <= module.keys(), 'Unversioned required module imports'
    for name, crc in module.items():
        assert kernel.get(name) == local.get(name) == crc, 'Module ABI mismatch: ' + name
    result = {'kernel_sha256': KERNEL_SHA, 'kernel_exports': len(kernel),
              'reference_crcs_matched': len(reference), 'local_crcs_matched': len(local),
              'module_imports_matched': len(module),
              'module_sha256': hashlib.sha256(args.module.read_bytes()).hexdigest()}
    if args.receipt:
        args.receipt.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

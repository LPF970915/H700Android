"""Read-only audit of the Test6 production and integrated Java/ART closure.

Run through tools/public_build/run-limited.sh.  This is an on-disk format and
dependency audit, not an ART verifier, Android boot test, or physical input test.
Only a new JSON receipt is written; archives and executable artifacts are read.
"""
from pathlib import Path, PurePosixPath
import argparse
import collections
import hashlib
import json
import os
import re
import stat
import struct
import subprocess
import sys
import time
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[2]
NATIVE = Path('/home/lpf/h700-android10/android')
OUT = Path('/home/lpf/roc-os-user-20261104/out')
WORK = Path('/home/lpf/roc-os-navigation-test6-build-20261115-v1')
DELIVERY = ROOT / 'out/nav-test6-production-20261115'
MANIFEST_SHA = 'c48f7f5dd07c73916ad5b5b10b0c215ab87e254a81453749393a15575761d8b9'
FRAMEWORK_SHA = 'e8110bc34ac032346b2da3fb625799420a72b278cc9e58e7d4b2aadf2b2044b3'
LID = '/system/priv-app/ROCReleaseLid/ROCReleaseLid.apk'
LID3_SHA = '8b79b5f78914db5db250e3daa9410dab3d469cc6867d2189faded19cebd2b724'
OATDUMP = OUT / 'soong/host/linux-x86/bin/oatdump'
HIDDENAPI_SOURCE_SHA = '23f277953dafbf08e6100692eb06714bbd314ad33a04c8becb817250410a9965'
D8_JAR_SHA = '9b6750442852f290e07998e20b09c07d56071dc6190405cad73ecebf64cff396'
PARSER_SOURCES = {
    'art/runtime/oat.h': '0f09f3dae000f8807315a0ab29cd804fff4d8bd2c1b410731445f850059bff77',
    'art/runtime/oat_file.cc': '6abf9a14f65d8d7786d475071179940d3c6b3813b822febd913a01a1dc3ebf20',
    'art/runtime/vdex_file.h': '19b780a98f7dfc9bf3f8b6bc040b10f70d1c69215d72b2baf01862a028787a86',
    'art/runtime/image.h': 'ab620b618b0bb908b4a564bceed49af5a0c2be35998ae5862c7694a2d84cc267',
    'art/runtime/gc/space/image_space.cc': '8767bdac2dbede1520fedd12803988024c32648a4d00711fabb33541497b7f95',
    'art/runtime/class_loader_context.cc': '31fda49eda54e0f66175e4f79f7eaa5945e6d197bcd0e423f6acdc992c6b9198',
    'art/libdexfile/dex/dex_file_loader.cc': '4cfea115807fd9434ecdb518bd1d27aaa27c8c30c7f3299222d06cee2daadb5d',
    'art/tools/hiddenapi/hiddenapi.cc': HIDDENAPI_SOURCE_SHA,
    'art/libdexfile/dex/dex_file_verifier.cc': 'b3afca47627709c80398f8bdac5499ed9c599c2f40dad0239a0bcf10e19064d0',
    'art/libartbase/arch/instruction_set.h': '49f7a3eaca5cd4a955eb65746622e56450a775bee2acb4871418d19fc55d7358',
    'prebuilts/sdk/tools/linux/lib/d8.jar': D8_JAR_SHA,
}
FRAMEWORK_CLASSES = {
    'Landroid/view/ViewRootImpl$RocJoystickGuard;',
    'Landroid/view/ViewRootImpl$RocDpadKeyGuard;',
}
FRAMEWORK_METHODS = {
    'rocShouldBlockDpad', 'rocFinishDpadInputEvent',
    'rocShouldBlockJoystick', 'rocFinishJoystickEvent',
}
NAV_CLASSES = {
    'Lcom/roc/rgsp/navtrial/KeyNavigation;',
    'Lcom/roc/rgsp/navtrial/AxisNavigation;',
    'Lcom/roc/rgsp/navtrial/NavigationService;',
}
ORPHAN_APK = '/system/priv-app/ROCProvisioning/ROCProvisioning.apk'
ORPHAN_PREOPT = [
    '/system/priv-app/ROCProvisioning/oat/arm64/ROCProvisioning.odex',
    '/system/priv-app/ROCProvisioning/oat/arm64/ROCProvisioning.vdex',
]


class AuditError(ValueError):
    pass


def check(condition, message):
    if not condition:
        raise AuditError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def take(data, offset, size, label):
    check(0 <= offset <= len(data) and 0 <= size <= len(data) - offset,
          'Truncated/out-of-range ' + label)
    return data[offset:offset + size]


def unpack(fmt, data, offset, label):
    return struct.unpack(fmt, take(data, offset, struct.calcsize(fmt), label))


def text(data, label):
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise AuditError('Invalid UTF-8 ' + label) from exc


def regular(path):
    path = Path(path)
    check(path.is_file() and not path.is_symlink(), 'Regular file required: ' + str(path))
    return path


def elf_oat(data, label):
    check(data[:4] == b'\x7fELF' and data[5:7] == b'\x01\x01', 'Unsupported ELF: ' + label)
    bits = data[4]
    if bits == 2:
        header = unpack('<HHIQQQIHHHHHH', data, 16, label + ' ELF64')
        section_offset, entry_size, count, names_index = header[5], header[10], header[11], header[12]
        section_fmt, min_size = '<IIQQQQIIQQ', 64
    else:
        check(bits == 1, 'Unsupported ELF class: ' + label)
        header = unpack('<HHIIIIIHHHHHH', data, 16, label + ' ELF32')
        section_offset, entry_size, count, names_index = header[5], header[10], header[11], header[12]
        section_fmt, min_size = '<IIIIIIIIII', 40
    check(entry_size == min_size and 0 < count < 4096 and names_index < count,
          'Invalid ELF section table: ' + label)
    sections = [unpack(section_fmt, data, section_offset + i * entry_size, label + ' section')
                for i in range(count)]
    names = take(data, sections[names_index][4], sections[names_index][5], label + ' section names')
    selected = []
    for row in sections:
        check(row[0] < len(names), 'Bad ELF section name: ' + label)
        end = names.find(b'\0', row[0])
        check(end >= 0, 'Unterminated ELF section name: ' + label)
        if names[row[0]:end] == b'.rodata':
            selected.append(row)
    check(len(selected) == 1, 'Unique .rodata required: ' + label)
    section = selected[0]
    oat = take(data, section[4], section[5], label + ' .rodata')
    check(oat[:8] == b'oat\n170\0', 'Unsupported OAT magic/version: ' + label)
    fields = unpack('<12I', oat, 8, label + ' OAT header')
    checksum, isa, features, dex_count, table_offset = fields[:5]
    check(isa in (1, 2, 3) and header[1] == {1: 40, 2: 183, 3: 40}[isa],
          'ELF/OAT ISA mismatch: ' + label)
    check(bits == {1: 1, 2: 2, 3: 1}[isa], 'ELF/OAT word-size mismatch: ' + label)
    check(0 < dex_count < 4096 and table_offset >= 56 + fields[11], 'Bad OAT DEX table: ' + label)
    raw_kv = take(oat, 56, fields[11], label + ' OAT keys')
    pairs = raw_kv.split(b'\0') if raw_kv else [b'']
    check(pairs[-1] == b'' and len(pairs) % 2 == 1, 'Malformed OAT key/value store: ' + label)
    kv = {}
    for i in range(0, len(pairs) - 1, 2):
        key, value = text(pairs[i], label), text(pairs[i + 1], label)
        check(key and key not in kv, 'Empty/duplicate OAT key: ' + label)
        kv[key] = value
    records, cursor = [], table_offset
    for i in range(dex_count):
        size, = unpack('<I', oat, cursor, label + ' DEX location size')
        cursor += 4
        check(0 < size < 65536, 'Invalid OAT DEX location length: ' + label)
        location = text(take(oat, cursor, size, label + ' DEX location'), label)
        cursor += size
        row = unpack('<8I', oat, cursor, label + ' DEX record')
        cursor += 32
        check('\0' not in location, 'NUL OAT location: ' + label)
        records.append({'location': location, 'checksum': row[0], 'dex_offset': row[1]})
    check(len({r['location'] for r in records}) == dex_count, 'Duplicate OAT DEX locations: ' + label)
    return {'version': '170', 'elf_class': 32 if bits == 1 else 64,
            'isa': 'arm64' if isa == 2 else 'arm',
            'instruction_set': {1: 'arm', 2: 'arm64', 3: 'thumb2'}[isa], 'checksum': checksum,
            'instruction_set_features': features, 'keys': kv, 'dex': records}


def vdex_header(data, label):
    check(data[:8] == b'vdex021\0' and data[8:12] in (b'000\0', b'002\0'),
          'Unsupported VDEX magic/version: ' + label)
    count, deps_size, bcp_size, context_size = unpack('<4I', data, 12, label + ' VDEX header')
    check(0 < count < 4096, 'Invalid VDEX DEX count: ' + label)
    checksums = list(unpack('<' + 'I' * count, data, 28, label + ' VDEX checksums'))
    cursor = 28 + 4 * count
    has_dex = data[8:12] == b'002\0'
    quick_size = 0
    if has_dex:
        dex_size, shared_size, quick_size = unpack('<3I', data, cursor, label + ' VDEX DEX section')
        cursor += 12 + dex_size + shared_size
    cursor += deps_size + quick_size
    bcp = text(take(data, cursor, bcp_size, label + ' VDEX BCP'), label)
    cursor += bcp_size
    context = text(take(data, cursor, context_size, label + ' VDEX context'), label)
    check(cursor + context_size == len(data), 'VDEX file-size/layout mismatch: ' + label)
    return {'version': '021', 'dex_section_version': data[8:11].decode(),
            'checksums': checksums, 'bootclasspath_checksums': bcp,
            'classloader_context': context, 'has_embedded_dex': has_dex}


def art_header(data, label):
    check(data[:8] == b'art\n074\0', 'Unsupported ART magic/version: ' + label)
    row = unpack('<14I', data, 8, label + ' ART header')
    check(row[13] in (4, 8) and row[3] >= 64, 'Invalid ART dimensions: ' + label)
    check(row[6] <= row[7] <= row[8] <= row[9], 'Invalid ART OAT ranges: ' + label)
    return {'version': '074', 'reservation_size': row[0], 'component_count': row[1],
            'image_begin': row[2], 'image_size': row[3], 'image_checksum': row[4],
            'oat_checksum': row[5], 'pointer_size': row[13],
            'boot_image_begin': row[10], 'boot_image_size': row[11]}


def uleb(data, offset, label):
    value = 0
    for shift in range(0, 35, 7):
        byte = take(data, offset, 1, label)[0]
        offset += 1
        value |= (byte & 127) << shift
        if not byte & 128:
            return value, offset
    raise AuditError('Overlong ULEB128: ' + label)


def hiddenapi_section(data, row, label):
    check(data[:8] == b'dex\n039\0', 'Official hiddenapi path requires DEX039: ' + label)
    map_offset = row[5]
    check(map_offset >= 112 and map_offset % 4 == 0, 'Invalid DEX map offset: ' + label)
    count, = unpack('<I', data, map_offset, label + ' DEX map size')
    check(0 < count < 65536, 'Invalid DEX map size: ' + label)
    take(data, map_offset + 4, count * 12, label + ' DEX map')
    entries, kinds = [], set()
    for i in range(count):
        kind, unused, size, offset = unpack('<HHII', data, map_offset + 4 + 12 * i, label + ' map item')
        check(unused == 0 and kind not in kinds and size > 0 and offset < len(data),
              'Invalid/duplicate DEX map item: ' + label)
        kinds.add(kind)
        if kind == 0xf000:
            entries.append((size, offset))
    check(len(entries) == 1 and entries[0][0] == 1 and entries[0][1] % 4 == 0,
          'Unique aligned hiddenapi section required: ' + label)
    offset = entries[0][1]
    size, = unpack('<I', data, offset, label + ' hiddenapi size')
    header_size = 4 + 4 * row[16]
    check(offset >= 112 and header_size <= size and offset + size <= map_offset,
          'Hiddenapi section overlaps/exceeds DEX map: ' + label)
    for i in range(row[16]):
        class_offset, = unpack('<I', data, offset + 4 + 4 * i, label + ' hiddenapi class offset')
        check(class_offset == 0 or header_size <= class_offset < size,
              'Hiddenapi class offset outside section: ' + label)
    return {'type': '0xf000', 'offset': offset, 'bytes': size, 'class_offset_count': row[16]}


def dex_header(data, label, inspect_classes=False, hiddenapi=False, pinned_d8=False):
    check(data[:4] == b'dex\n' and data[4:8] in (b'035\0', b'037\0', b'038\0', b'039\0'),
          'Unsupported DEX magic/version: ' + label)
    check(len(data) >= 112, 'Truncated DEX: ' + label)
    row = unpack('<20I', data, 32, label + ' DEX header')
    check(row[0] == len(data) and row[1] == 112 and row[2] == 0x12345678,
          'DEX size/endian/header mismatch: ' + label)
    checksum, = unpack('<I', data, 8, label + ' DEX Adler32')
    check(checksum == zlib.adler32(data[12:]) & 0xffffffff, 'DEX Adler32 mismatch: ' + label)
    sha1_matches = data[12:32] == hashlib.sha1(data[32:]).digest()
    # Android 10 hiddenapi encode updates Adler32 only, retaining the original
    # pre-encode SHA1. Restrict this path to the configured boot JARs, require
    # the actual encoded section, and bind the resulting full artifact SHA.
    encoded = hiddenapi_section(data, row, label) if hiddenapi else None
    # This pinned D8 writer supplies EOF-84 as MessageDigest.update's length,
    # yielding SHA1(data[32:-52]) for every supported DEX version. Do not
    # normalize installed bytes; the exact producer pattern is recorded.
    truncated52_matches = (pinned_d8 and len(data) >= 164
                           and data[12:32] == hashlib.sha1(data[32:-52]).digest())
    check(sha1_matches or encoded is not None or truncated52_matches, 'DEX SHA1 mismatch: ' + label)
    string_count, strings_offset, type_count, types_offset = row[6:10]
    method_count, methods_offset, class_count, classes_offset = row[14:18]
    for count, offset, size in ((string_count, strings_offset, 4), (type_count, types_offset, 4),
                                (method_count, methods_offset, 8), (class_count, classes_offset, 32)):
        take(data, offset, count * size, label + ' DEX ID table')
    result = {'version': data[4:7].decode(), 'bytes': len(data), 'adler32': checksum,
              'sha256': hashlib.sha256(data).hexdigest(), 'class_count': class_count,
              'standard_sha1_matches': sha1_matches,
              'pinned_D8_truncated52_sha1_matches': truncated52_matches,
              'postprocessor': 'android10-hiddenapi-encode' if hiddenapi else None}
    if truncated52_matches:
        result['producer_signature_rule'] = 'pinned-D8:SHA1(data[32:-52])'
    if encoded is not None:
        result['hiddenapi_section'] = encoded
    if not inspect_classes:
        return result, set(), set()
    cache = {}

    def string(index):
        check(index < string_count, 'Invalid DEX string index: ' + label)
        if index not in cache:
            offset, = unpack('<I', data, strings_offset + 4 * index, label)
            _, offset = uleb(data, offset, label)
            end = data.find(b'\0', offset)
            check(end >= offset, 'Unterminated DEX string: ' + label)
            cache[index] = data[offset:end]
        return cache[index]

    classes, methods = set(), set()
    for i in range(class_count):
        type_index, = unpack('<I', data, classes_offset + 32 * i, label)
        check(type_index < type_count, 'Invalid DEX class type: ' + label)
        string_index, = unpack('<I', data, types_offset + 4 * type_index, label)
        descriptor = text(string(string_index), label + ' class descriptor')
        check(descriptor not in classes, 'Duplicate DEX class: ' + descriptor)
        classes.add(descriptor)
    for i in range(method_count):
        _, _, name_index = unpack('<HHI', data, methods_offset + 8 * i, label)
        value = string(name_index)
        if value.isascii():
            methods.add(value.decode())
    return result, classes, methods


class SystemReader:
    def __init__(self, root, hiddenapi_locations=()):
        self.root = regular_root(root)
        self.installed = {}
        self.archives = {}
        self.hiddenapi_locations = frozenset(hiddenapi_locations)

    def path(self, location):
        base = location.split('!', 1)[0]
        p = PurePosixPath(base)
        check(p.is_absolute() and '..' not in p.parts, 'Unsafe device location: ' + location)
        if base.startswith('/system/'):
            candidate = self.root / base[len('/system/'):]
        elif base.startswith('/product/'):
            candidate = self.root / 'product' / base[len('/product/'):]
        elif base.startswith('/apex/'):
            parts = p.parts
            candidates = [x for x in (self.root / 'apex').iterdir()
                          if x.name == parts[2] or x.name.startswith(parts[2] + '.')]
            check(len(candidates) == 1, 'Ambiguous/missing APEX: ' + base)
            candidate = candidates[0].joinpath(*parts[3:])
        else:
            raise AuditError('Location outside audited system/APEX: ' + location)
        return self.safe(candidate)

    def safe(self, path):
        path = Path(path)
        check(path.resolve().is_relative_to(self.root), 'Rootfs link escapes audit root: ' + str(path))
        return path

    def read(self, path):
        path = self.safe(path)
        device = '/system/' + path.relative_to(self.root).as_posix()
        if path.is_symlink():
            info = {'kind': 'link', 'target': os.readlink(path)}
            prior = self.installed.setdefault(device, info)
            check(prior == info, 'Input link changed during audit: ' + device)
            return self.read(path.resolve())
        regular(path)
        data = path.read_bytes()
        info = {'kind': 'file', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        prior = self.installed.setdefault(device, info)
        check(prior == info, 'Input changed during audit: ' + device)
        return data

    def archive(self, location, inspect_classes=False):
        base = location.split('!', 1)[0]
        if base in self.archives and (not inspect_classes or self.archives[base].get('_inspected')):
            return self.archives[base]
        path = self.path(base)
        self.read(path)
        records, classes, methods = {}, set(), set()
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            check(len(names) == len(set(names)), 'Duplicate ZIP entries: ' + base)
            dex_names = sorted((n for n in names if re.fullmatch(r'classes(?:[1-9][0-9]*)?\.dex', n)),
                               key=lambda n: 1 if n == 'classes.dex' else int(n[7:-4]))
            check(dex_names, 'Original DEX missing from archive: ' + base)
            expected_names = ['classes.dex'] + ['classes%d.dex' % i for i in range(2, len(dex_names) + 1)]
            check(dex_names == expected_names, 'Noncontiguous multidex entries: ' + base)
            for name in dex_names:
                info, data = archive.getinfo(name), archive.read(name)
                check(zlib.crc32(data) & 0xffffffff == info.CRC, 'ZIP CRC mismatch: ' + base)
                hiddenapi = base in self.hiddenapi_locations
                dex, defined, declared = dex_header(data, base + '!' + name, inspect_classes,
                                                   hiddenapi=hiddenapi, pinned_d8=not hiddenapi)
                check(not classes.intersection(defined), 'Class duplicated across DEX files: ' + base)
                classes.update(defined)
                methods.update(declared)
                dex['zip_crc32'] = info.CRC
                records[name] = dex
        result = {'device_location': base, 'installed_path': '/system/' + path.relative_to(self.root).as_posix(),
                  'dex': records, '_classes': classes, '_methods': methods, '_inspected': inspect_classes}
        self.archives[base] = result
        return result

    def dex_crc(self, location):
        parts = location.split('!')
        check(len(parts) <= 2, 'Invalid multidex location: ' + location)
        archive = self.archive(parts[0])
        entry = parts[1] if len(parts) == 2 else 'classes.dex'
        check(entry in archive['dex'], 'OAT/context references absent DEX: ' + location)
        return archive['dex'][entry]['zip_crc32']


def regular_root(path):
    path = Path(path)
    check(path.is_dir() and not path.is_symlink(), 'Ordinary system directory required: ' + str(path))
    return path.resolve()


def file_link_inventory(root):
    """Hash every regular file and record every link without following links."""
    result = {}

    def visit(folder):
        for path in sorted(folder.iterdir()):
            mode = path.lstat().st_mode
            device = '/system/' + path.relative_to(root).as_posix()
            if stat.S_ISLNK(mode):
                result[device] = {'kind': 'link', 'target': os.readlink(path)}
            elif stat.S_ISDIR(mode):
                visit(path)
            elif stat.S_ISREG(mode):
                result[device] = {'kind': 'file', 'bytes': path.stat().st_size, 'sha256': sha(path)}
            else:
                raise AuditError('Unexpected special node in system snapshot: ' + device)

    visit(root)
    return dict(sorted(result.items()))


def context_dependencies(value, reader, dex_location):
    if value == '&':
        return {'kind': 'ART-special-shared-library', 'dependency_crc_check_skipped_by_format': True,
                'dependencies': []}
    if value == '':
        return {'kind': 'empty-PCL', 'dependencies': []}
    cursor, entries = 0, []

    def sequence():
        nonlocal cursor
        while True:
            match = re.match(r'(PCL|DLC)\[([^\[\]]*)\]', value[cursor:])
            check(match is not None, 'Unsupported/malformed classloader context: ' + value)
            cursor += match.end()
            if match[2]:
                for entry in match[2].split(':'):
                    parts = entry.rsplit('*', 1)
                    check(len(parts) == 2 and re.fullmatch(r'[0-9]+', parts[1]),
                          'Context entry lacks decimal checksum: ' + entry)
                    location, checksum = parts[0], int(parts[1])
                    if not location.startswith('/'):
                        location = str(PurePosixPath(dex_location.split('!')[0]).parent / location)
                    check(0 <= checksum <= 0xffffffff and reader.dex_crc(location) == checksum,
                          'Classloader context DEX checksum mismatch: ' + location)
                    entries.append({'location': location, 'checksum': checksum})
            if cursor < len(value) and value[cursor] == '{':
                cursor += 1
                if cursor < len(value) and value[cursor] != '}':
                    sequence()
                    while cursor < len(value) and value[cursor] == '#':
                        cursor += 1
                        sequence()
                check(cursor < len(value) and value[cursor] == '}', 'Unclosed context shared libraries')
                cursor += 1
            if cursor >= len(value) or value[cursor] != ';':
                return
            cursor += 1

    sequence()
    check(cursor == len(value), 'Trailing classloader context data: ' + value)
    return {'kind': 'encoded-PCL-DLC', 'dependencies': entries}


def boot_spec(config):
    check(config['DisablePreopt'] is False and config['OnlyPreoptBootImageAndSystemServer'] is False,
          'Full production dexpreopt must remain enabled')
    check(config['NeverAllowStripping'] is True and config['UseApexImage'] is False,
          'Unsupported stripping/APEX boot image configuration')
    check(set(config['CpuVariant']) == {'arm', 'arm64'}, 'Both ARM ABIs required')
    boot, runtime = config['BootJars'], config['RuntimeApexJars']
    check(len(boot) == len(set(boot)) and set(runtime).issubset(boot), 'Invalid BootJars configuration')
    remainder = [x for x in boot if x not in runtime + config['ProductUpdatableBootModules']]
    modules = runtime + remainder
    locations = ['/apex/com.android.runtime/javalib/' + x + '.jar' for x in runtime]
    locations += ['/system/framework/' + x + '.jar' for x in remainder]
    stems = ['boot'] + ['boot-' + x for x in modules[1:]]
    return modules, locations, stems


def historical_orphan_preopt(reader, before_inventory):
    """Quarantine only the two exact old, inactive ROCProvisioning artifacts."""
    paths = [reader.root / p[len('/system/'):] for p in ORPHAN_PREOPT]
    present = [p.exists() or p.is_symlink() for p in paths]
    if not any(present):
        return {}
    check(all(present), 'Partial historical ROCProvisioning preopt pair')
    check(before_inventory is not None, 'Historical orphan preopt forbidden in integrated system')
    check(not reader.path(ORPHAN_APK).exists() and ORPHAN_APK[len('/system'):] not in before_inventory,
          'Historical orphan exclusion requires the original APK to be absent')
    files = {}
    for device, path in zip(ORPHAN_PREOPT, paths):
        data = reader.read(path)
        actual = {'kind': 'file', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        expected = before_inventory[device[len('/system'):]]
        check(all(expected.get(k) == v for k, v in actual.items()),
              'Historical orphan bytes differ from the before snapshot: ' + device)
        files[device] = actual
    oat = elf_oat(reader.read(paths[0]), ORPHAN_PREOPT[0])
    vdex = vdex_header(reader.read(paths[1]), ORPHAN_PREOPT[1])
    check(oat['isa'] == 'arm64' and len(oat['dex']) == 1
          and oat['dex'][0]['location'] == ORPHAN_APK and oat['dex'][0]['dex_offset'] == 0,
          'Historical orphan OAT identity/layout differs')
    check(vdex['checksums'] == [oat['dex'][0]['checksum']], 'Historical orphan OAT/VDEX checksum mismatch')
    return files


def audit_system(system_tree, config, production_orphan_inventory=None):
    modules, locations, stems = boot_spec(config)
    reader = SystemReader(system_tree, hiddenapi_locations=locations)
    bcp, boot_paths, preopt_paths, art_results = ':'.join(locations), [], [], []
    boot_link_paths = []
    primary, oats, boot_oat_paths = {}, {}, set()
    for arch, pointer in [('arm', 4), ('arm64', 8)]:
        directory = reader.root / 'framework' / arch
        for ext in ('.art', '.oat', '.vdex'):
            actual = {p.name for p in directory.glob('boot*' + ext)}
            check(actual == {s + ext for s in stems}, 'Incomplete/stale boot component set: ' + arch + ext)
        for i, (stem, location) in enumerate(zip(stems, locations)):
            art_path, oat_path = directory / (stem + '.art'), directory / (stem + '.oat')
            vdex_path = directory / (stem + '.vdex')
            check(vdex_path.is_symlink() and os.readlink(vdex_path) == '../' + stem + '.vdex',
                  'Shared boot VDEX link topology differs: ' + str(vdex_path))
            art = art_header(reader.read(art_path), str(art_path))
            oat = elf_oat(reader.read(oat_path), str(oat_path))
            vdex = vdex_header(reader.read(vdex_path), str(vdex_path))
            check(art['pointer_size'] == pointer and oat['isa'] == arch, 'Boot ART/OAT ABI mismatch')
            check(art['oat_checksum'] == oat['checksum'], 'ART to OAT checksum mismatch: ' + stem)
            check(art['component_count'] == (len(stems) if i == 0 else 0), 'Boot component count mismatch')
            expected = reader.archive(location)
            expected_locations = [location if n == 'classes.dex' else location + '!' + n for n in expected['dex']]
            check([r['location'] for r in oat['dex']] == expected_locations, 'Boot OAT DEX order mismatch: ' + stem)
            check(vdex['checksums'] == [r['checksum'] for r in oat['dex']], 'Boot OAT/VDEX CRC mismatch')
            check(not vdex['has_embedded_dex'] and all(r['dex_offset'] == 0 for r in oat['dex']),
                  'Unsupported embedded boot DEX; audit requires the installed ZIP DEX')
            for record in oat['dex']:
                check(reader.dex_crc(record['location']) == record['checksum'], 'Boot archive CRC mismatch: ' + stem)
            if i == 0:
                check(oat['keys'].get('bootclasspath') == bcp, 'Primary boot OAT classpath differs')
                primary[arch] = art
            else:
                check(not oat['keys'], 'Unexpected secondary boot OAT key/value store')
            device_oat = '/system/' + oat_path.relative_to(reader.root).as_posix()
            oats[device_oat] = oat
            boot_oat_paths.add(device_oat)
            art_results.append({'path': '/system/' + art_path.relative_to(reader.root).as_posix(), **art})
            boot_paths.extend('/system/' + p.relative_to(reader.root).as_posix()
                              for p in (art_path, oat_path, vdex_path.resolve()))
            boot_link_paths.append('/system/' + vdex_path.relative_to(reader.root).as_posix())
    shared = {p.name for p in (reader.root / 'framework').glob('boot*.vdex')}
    check(shared == {s + '.vdex' for s in stems}, 'Incomplete/stale shared boot VDEX set')
    excluded = historical_orphan_preopt(reader, production_orphan_inventory)
    all_files = []
    for folder, dirs, names in os.walk(reader.root, followlinks=False):
        dirs[:] = [d for d in dirs if not (Path(folder) / d).is_symlink()]
        all_files += [Path(folder) / n for n in names if not (Path(folder) / n).is_symlink()]
    results, context_counts = [], collections.Counter()
    accounted_vdex = {reader.root / p[len('/system/'):] for p in excluded if p.endswith('.vdex')}
    for path in sorted(p for p in all_files if p.suffix in ('.oat', '.odex')):
        device = '/system/' + path.relative_to(reader.root).as_posix()
        if device in excluded:
            continue
        oat = oats.get(device) or elf_oat(reader.read(path), device)
        companion = path.with_suffix('.vdex')
        vdex = vdex_header(reader.read(companion), str(companion))
        accounted_vdex.add(companion.resolve())
        check(vdex['checksums'] == [r['checksum'] for r in oat['dex']], 'OAT/VDEX CRC vector mismatch: ' + device)
        check(not vdex['has_embedded_dex'] and all(r['dex_offset'] == 0 for r in oat['dex']),
              'Unsupported embedded DEX; audit requires the installed ZIP DEX: ' + device)
        for record in oat['dex']:
            check(reader.dex_crc(record['location']) == record['checksum'], 'OAT actual archive CRC mismatch: ' + device)
        if device in boot_oat_paths:
            continue
        arch = path.parent.name
        check(arch in primary and oat['isa'] == arch, 'Downstream OAT ABI mismatch: ' + device)
        expected_bcp_checksum = 'i;%d/%08x' % (len(stems), primary[arch]['image_checksum'])
        keys = oat['keys']
        check(keys.get('bootclasspath') == bcp, 'Downstream bootclasspath differs: ' + device)
        check(keys.get('bootclasspath-checksums') == expected_bcp_checksum,
              'Downstream OAT references another boot image checksum: ' + device)
        check('classpath' in keys, 'OAT classloader context absent: ' + device)
        context = context_dependencies(keys['classpath'], reader, oat['dex'][0]['location'])
        context_counts[context['kind']] += 1
        if vdex['bootclasspath_checksums']:
            check(vdex['bootclasspath_checksums'] == expected_bcp_checksum, 'VDEX boot dependency differs: ' + device)
        if vdex['classloader_context']:
            check(vdex['classloader_context'] == keys['classpath'], 'OAT/VDEX contexts differ: ' + device)
        results.append({'path': device, 'isa': arch, 'oat_checksum': oat['checksum'],
                        'compiler_filter': keys.get('compiler-filter'), 'bootclasspath': bcp,
                        'bootclasspath_checksums': expected_bcp_checksum, 'classloader_context': keys['classpath'],
                        'context_audit': context, 'dex': oat['dex'], 'vdex': vdex})
        preopt_paths.extend([device, '/system/' + companion.relative_to(reader.root).as_posix()])
        oats[device] = oat
    vdex_files = {p.resolve() for p in all_files if p.suffix == '.vdex'}
    check(accounted_vdex == vdex_files, 'Orphan/missing VDEX files: ' + str(sorted(map(str, vdex_files - accounted_vdex))))
    for path in sorted(p for p in all_files if p.suffix == '.art'):
        device = '/system/' + path.relative_to(reader.root).as_posix()
        if device in boot_paths:
            continue
        paired = path.with_suffix('.odex')
        paired_device = '/system/' + paired.relative_to(reader.root).as_posix()
        check(paired_device in oats, 'Orphan application ART image: ' + device)
        art = art_header(reader.read(path), device)
        check(art['component_count'] == 1 and art['oat_checksum'] == oats[paired_device]['checksum'],
              'Application ART/OAT dependency mismatch: ' + device)
        check(art['pointer_size'] == {'arm': 4, 'arm64': 8}[oats[paired_device]['isa']], 'App ART ABI mismatch')
        preopt_paths.append(device)
        art_results.append({'path': device, **art})
    for name in config['SystemServerJars']:
        device = '/system/framework/oat/arm64/' + name + '.odex'
        check(device in oats, 'Missing primary system server preopt: ' + name)
    if excluded:
        replacement = '/system/priv-app/ROCReleaseProvisioning/oat/arm64/ROCReleaseProvisioning.odex'
        check(replacement in oats, 'Current ROCReleaseProvisioning replacement preopt is missing')
    framework = reader.archive('/system/framework/framework.jar', inspect_classes=True)
    check(FRAMEWORK_CLASSES.issubset(framework['_classes']), 'Framework DEX lacks actual guard class definitions')
    check(FRAMEWORK_METHODS.issubset(framework['_methods']), 'Framework DEX lacks guard method IDs')
    navigation = reader.archive('/system/app/ROCNavigation/ROCNavigation.apk', inspect_classes=True)
    check(NAV_CLASSES.issubset(navigation['_classes']), 'Navigation DEX lacks actual Key/Axis/Service definitions')
    profile_paths = []
    for path in sorted(p for p in all_files if p.suffix == '.prof'):
        reader.read(path)
        profile_paths.append('/system/' + path.relative_to(reader.root).as_posix())
    check('/system/etc/boot-image.prof' in profile_paths, 'Matching boot-image.prof missing')
    installed = file_link_inventory(reader.root)
    for path, info in reader.installed.items():
        check(installed.get(path) == info, 'Input changed during audit: ' + path)
    boot_paths = sorted(set(boot_paths))
    boot_link_paths = sorted(set(boot_link_paths))
    check(len(boot_paths) == 55 and len(boot_link_paths) == 22, 'Unexpected production boot closure size')
    check(all(installed[p]['kind'] == 'file' for p in boot_paths)
          and all(installed[p]['kind'] == 'link' for p in boot_link_paths), 'Boot file/link kind mismatch')
    archives = {name: {k: v for k, v in row.items() if not k.startswith('_')}
                for name, row in reader.archives.items()}
    return {'installed_files': installed,
            'boot_modules': modules, 'boot_classpath_locations': locations,
            'boot_artifact_paths': boot_paths, 'boot_artifact_link_paths': boot_link_paths,
            'preopt_artifact_paths': sorted(set(preopt_paths)),
            'profile_paths': profile_paths, 'boot_primary_headers': primary, 'ART_images': art_results,
            'DEX_archives': archives, 'downstream_OAT_audits': results,
            'classloader_context_counts': dict(context_counts),
            'framework_guard_class_defs': sorted(FRAMEWORK_CLASSES),
            'framework_guard_method_ids': sorted(FRAMEWORK_METHODS),
            'navigation_class_defs': sorted(NAV_CLASSES),
            'excluded_orphan_preopt_paths': sorted(excluded),
            'excluded_orphan_preopt_files': excluded,
            'excluded_orphan_validation_scope': (
                'Production-only exact before-snapshot bytes; parsed arm64 OAT and VDEX checksum vector; '
                'old APK absent and current ROCReleaseProvisioning APK/preopt audited normally; '
                'excluded artifacts have no current DEX or boot-image dependency acceptance'),
            'limitations': {'physical_or_Android_runtime_verified': False,
                            'complete_DEX_bytecode_verifier_executed': False,
                            'ART_payload_or_OAT_checksum_recomputed': False,
                            'special_shared_library_context_dependencies_verified': False}}


def integrated_binding(report, production, reader_root):
    check(production.get('passed') is True and production.get('phase') == 'production',
          'Successful production ART audit required')
    check(production['source_manifest_sha256'] == MANIFEST_SHA, 'Production audit uses another source manifest')
    check(report['boot_artifact_paths'] == production['boot_artifact_paths'], 'Integrated boot component set changed')
    check(production['framework_source_sha256'] == FRAMEWORK_SHA,
          'Production audit uses another framework source')
    check(production['hiddenapi_source_sha256'] == HIDDENAPI_SOURCE_SHA
          and production['framework_dex_postprocessor'] == 'android10-hiddenapi-encode',
          'Production audit lacks the official hiddenapi producer binding')
    check(production['d8_jar_sha256'] == D8_JAR_SHA, 'Production audit uses another pinned D8 producer')
    check(not report['excluded_orphan_preopt_paths'], 'Integrated system contains excluded historical preopt')
    for path in production['excluded_orphan_preopt_paths']:
        check(path not in report['installed_files'], 'Quarantined production preopt survived integration: ' + path)
    for key in ('boot_artifact_paths', 'boot_artifact_link_paths', 'preopt_artifact_paths', 'profile_paths'):
        expected = [p for p in production[key] if '/ROCReleaseLid/' not in p]
        check(report[key] == expected, 'Integrated closure differs outside Lid exception: ' + key)
        for path in expected:
            check(report['installed_files'][path] == production['installed_files'][path],
                  'Integrated closure file differs from production: ' + path)
    for path in ('/system/framework/framework.jar', '/system/app/ROCNavigation/ROCNavigation.apk'):
        check(report['installed_files'][path] == production['installed_files'][path],
              'Integrated APK/JAR differs from production: ' + path)
    lid_path = reader_root / LID[len('/system/'):]
    check(sha(regular(lid_path)) == LID3_SHA, 'Integrated model-aware Lid3 identity mismatch')
    check(not any((lid_path.parent).rglob('*.odex')) and not any((lid_path.parent).rglob('*.vdex'))
          and not any((lid_path.parent).rglob('*.art')), 'Integrated Lid3 must have no stale preopt')
    report['Lid3_exception'] = {'APK': LID, 'sha256': LID3_SHA, 'preopt_absent': True}


def oatdump_check(system_tree, report):
    regular(OATDUMP)
    paths = ['/system/framework/arm/boot.oat', '/system/framework/arm64/boot.oat',
             '/system/framework/arm64/boot-framework.oat',
             '/system/framework/oat/arm64/services.rocsource.odex',
             '/system/app/ROCNavigation/oat/arm64/ROCNavigation.odex']
    rows = []
    for device in paths:
        path = system_tree / device[len('/system/'):]
        check(path.is_file(), 'Expected cross-check OAT absent: ' + device)
        parsed = elf_oat(path.read_bytes(), device)
        result = subprocess.run([str(OATDUMP), '--header-only', '--oat-file=' + str(path)],
                                capture_output=True, text=True, timeout=20)
        check(result.returncode == 0, 'oatdump header cross-check failed: ' + device)
        check('CHECKSUM:\n0x%08x\n' % parsed['checksum'] in result.stdout,
              'oatdump/parser checksum disagreement: ' + device)
        check('DEX FILE COUNT:\n%d\n' % len(parsed['dex']) in result.stdout,
              'oatdump/parser DEX count disagreement: ' + device)
        for key, value in parsed['keys'].items():
            check(key + ' = ' + value + '\n' in result.stdout, 'oatdump/parser key disagreement: ' + device)
        rows.append({'path': device, 'exit_status': result.returncode,
                     'stdout_sha256': hashlib.sha256(result.stdout.encode()).hexdigest(),
                     'stderr': result.stderr[-1600:]})
    return {'tool': str(OATDUMP), 'sha256': sha(OATDUMP), 'crosschecks': rows}


def main(args):
    sys.path.insert(0, str(ROOT / 'tools'))
    from package_h700_v6a import constrained
    constrained()
    started = time.monotonic()
    receipt = args.receipt.absolute()
    check(not receipt.exists() and receipt.parent.is_dir(), 'New receipt path with existing parent required')
    system = regular_root(args.system_tree)
    check(system != NATIVE and not system.is_relative_to(NATIVE), 'Audit a frozen system snapshot')
    phase = 'integrated' if args.production_audit else 'production'
    check(phase != 'production' or system == (WORK / 'after/system').resolve(),
          'Production audit requires the builder frozen after/system')
    report = {'schema': 'roc.navigation-test6.art-audit.v1', 'passed': False, 'phase': phase,
              'system_tree': str(system), 'physical_device_accessed': False,
              'audit_tool_sha256': sha(Path(__file__)), 'source_manifest_sha256': MANIFEST_SHA,
              'framework_source_sha256': FRAMEWORK_SHA,
              'hiddenapi_source_sha256': HIDDENAPI_SOURCE_SHA,
              'd8_jar_sha256': D8_JAR_SHA,
              'framework_dex_postprocessor': 'android10-hiddenapi-encode'}
    try:
        manifest = ROOT / 'build-support/public/source-manifest.json'
        check(sha(manifest) == MANIFEST_SHA, 'Current public manifest changed')
        for name, digest in PARSER_SOURCES.items():
            check(sha(NATIVE / name) == digest, 'Parser source layout identity changed: ' + name)
        report['parser_source_sha256'] = PARSER_SOURCES
        build_path = DELIVERY / 'build-result.json'
        build = json.loads(regular(build_path).read_text())
        lock_path = WORK / 'input-lock.json'
        lock = json.loads(regular(lock_path).read_text())
        check(build['passed'] is True and build['compile_exit_status'] == 0,
              'Production systemimage build did not complete')
        check(build['source_manifest_sha256'] == MANIFEST_SHA and build['framework_source_sha256'] == FRAMEWORK_SHA,
              'Production build source identity differs')
        check(build['input_lock_sha256'] == sha(lock_path) and lock['source_manifest_sha256'] == MANIFEST_SHA,
              'Production source lock differs')
        inventory_path = WORK / 'after/system-tree.json'
        check(sha(inventory_path) == build['system_inventory_sha256'], 'Frozen production inventory receipt differs')
        config_path = WORK / 'after/dexpreopt.config'
        config_digest = sha(regular(config_path))
        config = json.loads(config_path.read_text())
        before_inventory = None
        if phase == 'production':
            before_path = WORK / 'before/system-tree.json'
            check(sha(before_path) == lock['before_inventory_sha256'], 'Historical before inventory identity differs')
            before_inventory = json.loads(before_path.read_text())
            report['before_inventory_sha256'] = sha(before_path)
        report.update(audit_system(system, config, production_orphan_inventory=before_inventory))
        if phase == 'production':
            inventory = json.loads(inventory_path.read_text())
            for device, actual in report['installed_files'].items():
                expected = inventory[device[len('/system'):]]
                check(all(expected.get(k) == v for k, v in actual.items()),
                      'Frozen artifact differs from build inventory: ' + device)
        else:
            production_path = regular(args.production_audit)
            production = json.loads(production_path.read_text())
            integrated_binding(report, production, system)
            report['production_audit_sha256'] = sha(production_path)
        report['oatdump_header_crosscheck'] = oatdump_check(system, report)
        check(sha(config_path) == config_digest and sha(manifest) == MANIFEST_SHA,
              'Audit controls changed during execution')
        report.update(passed=True, build_receipt_sha256=sha(build_path), input_lock_sha256=sha(lock_path),
                      dexpreopt_config_sha256=config_digest,
                      installed_file_count=len(report['installed_files']),
                      boot_artifact_count=len(report['boot_artifact_paths']),
                      downstream_preopt_OAT_count=len(report['downstream_OAT_audits']),
                      elapsed_seconds=time.monotonic() - started)
    except BaseException as exc:
        report['error'] = type(exc).__name__ + ': ' + str(exc)
        raise
    finally:
        with receipt.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False)
            stream.write('\n')
    print(json.dumps({'passed': True, 'phase': phase, 'receipt': str(receipt),
                      'boot_artifacts': report['boot_artifact_count'],
                      'preopt_OATs': report['downstream_preopt_OAT_count']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--system-tree', type=Path, default=WORK / 'after/system')
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--production-audit', type=Path,
                        help='Required for a final integrated tree; binds the production closure')
    main(parser.parse_args())

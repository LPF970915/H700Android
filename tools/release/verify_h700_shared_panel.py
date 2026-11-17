"""Independently verify one shared H700 panel image and its exact byte delta.

This verifier never imports a panel patcher, invokes a compiler, touches a
device, or opens a block path.  verify_prefix() is usable on bounded ordinary
byte fixtures.  The command-line entry verifies a completed regular gzip.
Driver sections come from a frozen ordinary-file artifact manifest, while
their locations, maximum bounds, legacy-library identities and all preserved
bytes are checked here independently.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import re
import stat
import struct
import sys
import time


REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained
from verify_002 import verify_gpt


BASE = Path('/home/lpf/roc-os-002-20261114-v1/ROC_OS_ARM64_ver0.0.2.img')
BASE_PREFIX_SHA = 'dddb456725f6ae0b0e3977c50747a23a8c91b66c55140959b9a58ab4f7ff425a'
SIZE, PREFIX = 32434554368, 222298112
TOC_START, TOC_SIZE = 16793600, 1310720
BOOT_START, BOOT_SIZE = 155189248, 67108864
KERNEL_SIZE = 17686536
DTBS = {'uboot': (17954816, 143872, 139616),
        'kernel': (177270784, 139264, 137564)}
PANEL = '/soc@03000000/lcd0@01c0c000/'
PROFILE_KEY = PANEL + 'roc_panel_profile'
PROPERTY_NAME = b'roc_panel_profile\0'
SPACE_SHA = '847b55c93f1c0a36983ada5a500d4311b18022ef86b2db2aa3dc5614f0f400d6'
PRIMARY_REF = REPO / 'out/rg34xx-boot-analysis-20261114/primary-knulli/package/boot/uboot-h700/rg35xx-h/boot_package/rg35xx-h.dts'
PRIMARY_REF_SHA = 'efff1a3c781f5f0e9324d0b4f4b16c398a4c566b2ecac411eada26053c5f6660'
LEGACY = {'lcd_x': 720, 'lcd_y': 480, 'lcd_dclk_freq': 26, 'lcd_hbp': 46,
          'lcd_ht': 820, 'lcd_hspw': 2, 'lcd_vbp': 20, 'lcd_vt': 536,
          'lcd_vspw': 5, 'lcd_hv_clk_phase': 1, 'lcd_hv_sync_polarity': 3}
RG35H = {'lcd_x': 640, 'lcd_y': 480, 'lcd_dclk_freq': 24, 'lcd_hbp': 46,
         'lcd_ht': 770, 'lcd_hspw': 20, 'lcd_vbp': 15, 'lcd_vt': 520,
         'lcd_vspw': 4, 'lcd_hv_clk_phase': 2, 'lcd_hv_sync_polarity': 3}
ARCH = {
    'uboot': {'original_sha256': 'a11271e1276173cee48bd5705d068fd8446cfc0ffb43fca70b3b6808c2e9d0db',
              'bytes': 1048576, 'dispatch': (0x26424, 0x26afc),
              'old_bridge': (0x26b18, 0x26b1c),
              'library': (0x26b28, 3334, 'b67e8ace0c75d8a463be6276084f7324e14860c27f95a365cc427fab119cc8ba')},
    'kernel': {'original_sha256': '3328c2fab9f19f7ea6a80e34b0a76238cf594bc631f77e05fec32f8adabad042',
               'bytes': KERNEL_SIZE, 'dispatch': (0x3a2b60, 0x3a3460),
               'boe_bridge': (0x3a2b50, 0x3a2b54),
               'old_bridge': (0x3a3460, 0x3a3464),
               'library': (0x3a3480, 3412, '4c56b4decd7dedd2fca3717d203001424207eb993378d031a54711f1889aafa2')},
}
RANGES = {'prefix': (0, PREFIX), 'system': (222298112, 8589934592),
          'vendor': (8812232704, 2147483648), 'userdata': (10959716352, 21474836480),
          'backup_gpt': (32434552832, 1536)}
PARENT_RANGES = {
    'system': 'fe7877aa2f5e8821405ae49bd43382d209c0da8e0215fa245a284980f3dd66ad',
    'vendor': 'bcf0706cd474b54b7f908aa234100a352773e0d603a11f4fa00787079e0f6fa0',
    'userdata': '637a02240df99491b9616503c69cd41638b7604c927675762e640014b3cd7d86',
    'backup_gpt': 'ba9ba2c16fbb57653f2d5b221bb2f0c2ee698550f1d9dc33df30b5565d23c5dc',
}


def check(ok, message):
    if not ok:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def ordinary(path):
    path = Path(path)
    check(not path.is_symlink() and stat.S_ISREG(path.lstat().st_mode),
          'Ordinary non-symlink file required: ' + str(path))
    return path


def file_sha(path):
    with ordinary(path).open('rb') as reader:
        return hashlib.file_digest(reader, 'sha256').hexdigest()


def read_json(path):
    return json.loads(ordinary(path).read_text(encoding='utf-8'))


def read_locked(record, *, base=None):
    check(isinstance(record, dict) and 'file' in record and 'sha256' in record,
          'Missing locked artifact file/hash')
    path = Path(record['file'])
    if not path.is_absolute():
        check(base is not None, 'Relative artifact requires manifest directory')
        path = base / path
    raw = ordinary(path).read_bytes()
    check(digest(raw) == record['sha256'], 'Locked artifact SHA mismatch: ' + str(path))
    return raw


def parse_fdt(blob):
    """Strict independent parser, retaining raw values, offsets and node bodies."""
    check(len(blob) >= 40, 'Short FDT')
    h = list(struct.unpack_from('>10I', blob))
    magic, total, tree, strings, reserve, version, compat, _, names_len, tree_len = h
    check(magic == 0xd00dfeed and version == 17 and compat == 16, 'FDT identity/version')
    check(40 <= reserve <= tree < strings <= total <= len(blob), 'FDT ordered bounds')
    check(not reserve % 8 and not tree % 4 and tree + tree_len == strings,
          'FDT reserve/structure alignment')
    check(strings + names_len <= total, 'FDT strings bounds')
    pos = reserve
    while True:
        check(pos + 16 <= tree, 'FDT reserve terminator missing')
        address, length = struct.unpack_from('>QQ', blob, pos)
        pos += 16
        if address == length == 0:
            break
    check(pos == tree, 'Unexpected bytes after FDT reserve list')
    pos, stack, props, nodes = tree, [], {}, {}
    while pos + 4 <= tree + tree_len:
        token, = struct.unpack_from('>I', blob, pos)
        pos += 4
        if token == 1:
            end = blob.find(b'\0', pos, tree + tree_len)
            check(end >= pos, 'Unterminated FDT node')
            stack.append(blob[pos:end].decode('ascii'))
            pos = (end + 4) & ~3
            path = '/' + '/'.join(part for part in stack if part)
            check(path not in nodes, 'Duplicate FDT node')
            nodes[path] = pos
        elif token == 2:
            check(stack, 'FDT stack underflow')
            stack.pop()
        elif token == 3:
            check(stack and pos + 8 <= tree + tree_len, 'Truncated FDT property')
            length, name = struct.unpack_from('>II', blob, pos)
            pos += 8
            check(pos + length <= tree + tree_len and name < names_len, 'FDT property bounds')
            end = blob.find(b'\0', strings + name, strings + names_len)
            check(end >= strings + name, 'Unterminated FDT property name')
            key = '/' + '/'.join(part for part in stack if part) + '/' + blob[strings+name:end].decode('ascii')
            check(key not in props, 'Duplicate FDT property')
            props[key] = (pos, blob[pos:pos+length])
            pos = (pos + length + 3) & ~3
        elif token == 4:
            pass
        elif token == 9:
            check(not stack and pos == tree + tree_len, 'FDT end/structure mismatch')
            return h, props, nodes
        else:
            raise ValueError('Unexpected FDT token')
    raise ValueError('FDT END absent')


def verify_reference():
    raw = ordinary(PRIMARY_REF).read_bytes()
    check(digest(raw) == PRIMARY_REF_SHA, 'Pinned primary reference changed')
    node = re.search(r'\blcd0@01c0c000\s*\{(.*?)\n\s*\};', raw.decode('utf-8'), re.S)
    check(node is not None, 'Primary reference LCD node absent')
    for name, expected in RG35H.items():
        match = re.search(r'\b' + name + r'\s*=\s*<(0x[0-9a-fA-F]+)>;', node[1])
        check(match is not None and int(match[1], 16) == expected, 'Primary timing mismatch: ' + name)


def verify_fdt(before, after, architecture, profile):
    old_h, old, old_nodes = parse_fdt(before)
    new_h, new, new_nodes = parse_fdt(after)
    _, capacity, old_total = DTBS[architecture]
    check(len(before) == len(after) == capacity and old_h[1] == old_total, 'FDT fixed capacity/old total')
    check(len(old) == 4911 and PROFILE_KEY not in old, 'Unexpected original FDT property set')
    check(set(new) == set(old) | {PROFILE_KEY} and set(old_nodes) == set(new_nodes), 'FDT added unrelated node/property')
    check(new[PROFILE_KEY][1] == struct.pack('>I', profile), 'Wrong configured profile')
    check(old[PANEL+'lcd_driver_name'][1] == new[PANEL+'lcd_driver_name'][1] == b'rg34xxsp_v1\0',
          'Registered panel alias changed')
    timings = LEGACY if profile == 0 else RG35H
    for name, value in LEGACY.items():
        check(old[PANEL+name][1] == struct.pack('>I', value), 'Original timing identity changed')
    for key, row in old.items():
        wanted = struct.pack('>I', timings[key[len(PANEL):]]) if key in {PANEL+n for n in timings} else row[1]
        check(new[key][1] == wanted, 'Unexpected configured FDT value: ' + key)
    insert = old_nodes[PANEL[:-1]]
    check(new[PROFILE_KEY][0] == insert + 12, 'Carrier must precede original panel properties')
    expected_h = old_h.copy()
    expected_h[3] += 16
    expected_h[8] += len(PROPERTY_NAME)
    expected_h[9] += 16
    expected_h[1] = old_total if architecture == 'uboot' else old_total + 36
    check(new_h == expected_h, 'Unexpected FDT header delta')
    check(before[40:old_h[2]] == after[40:new_h[2]], 'FDT memory reserves changed')
    check(not any(before[old_h[3]+old_h[8]:]), 'Original FDT capacity is not zero slack')
    check(after[old_h[2]:insert] == before[old_h[2]:insert], 'FDT structure prefix changed')
    check(after[insert:insert+16] == struct.pack('>4I', 3, 4, old_h[8], profile), 'Wrong FDT carrier record')
    check(after[new_h[3]:new_h[3]+old_h[8]] == before[old_h[3]:old_h[3]+old_h[8]], 'Original FDT string table changed')
    check(after[new_h[3]+old_h[8]:new_h[3]+new_h[8]] == PROPERTY_NAME, 'Wrong appended FDT name')
    check(not any(after[new_h[3]+new_h[8]:]), 'FDT padding changed')
    shifted = bytearray(before[insert:old_h[3]])
    for name, value in timings.items():
        old_position = old[PANEL+name][0]
        check(old_position >= insert and new[PANEL+name][0] == old_position+16, 'Original FDT property moved unexpectedly')
        struct.pack_into('>I', shifted, old_position-insert, value)
    check(after[insert+16:new_h[3]] == shifted, 'Unrelated FDT structure/token/padding changed')
    return {'profile': profile, 'properties': len(new), 'total': new_h[1], 'capacity': capacity,
            'sha256': digest(after), 'timings': timings, 'original4911_properties_preserved_except_configured_timings': True,
            'memory_reserve_and_page_tail_preserved': True}


def parse_toc(blob):
    check(len(blob) == TOC_SIZE and blob[:16] == b'sunxi-package\0\0\0', 'TOC identity/size')
    magic, checksum = struct.unpack_from('<II', blob, 16)
    count, length = struct.unpack_from('<II', blob, 32)
    check(magic == 0x89119800 and count == 4 and length == TOC_SIZE, 'TOC geometry')
    check((sum(struct.unpack('<327680I', blob))-checksum+0x5f0a6c39)&0xffffffff == checksum, 'TOC additive checksum')
    items = {}
    for i in range(count):
        row = 64 + i*368
        name = blob[row:row+64].split(b'\0', 1)[0].decode('ascii')
        offset, size = struct.unpack_from('<II', blob, row+64)
        check(name not in items and name in ('u-boot', 'monitor', 'dtbo', 'dtb'), 'TOC item name')
        check(2048 <= offset < offset+size <= TOC_SIZE, 'TOC item bounds')
        items[name] = {'offset': offset, 'bytes': size, 'row': blob[row:row+368]}
    spans = sorted((r['offset'], r['offset']+r['bytes']) for r in items.values())
    check(all(a[1] <= b[0] for a, b in zip(spans, spans[1:])), 'Overlapping TOC items')
    return items


def verify_architecture(before, after, architecture, record, *, manifest_directory=None):
    spec = ARCH[architecture]
    check(len(before) == len(after) == spec['bytes'], 'Driver component size changed')
    check(digest(before) == record['original_sha256'] == spec['original_sha256'], 'Driver original identity')
    check(record['original_bytes'] == spec['bytes'], 'Artifact original size mismatch')
    check(digest(after) == record['patched_sha256'], 'Delivered driver SHA mismatch')
    if 'patched_file' in record:
        check(read_locked({'file': record['patched_file'], 'sha256': record['patched_sha256']},
                          base=manifest_directory) == after, 'Patched ordinary driver differs')
    if 'patched_binary' in record:
        check(read_locked(record['patched_binary'], base=manifest_directory) == after, 'Patched ordinary driver differs')
    sections = record['sections']
    expected_roles = {'library', 'dispatch', 'old_bridge'} | ({'boe_bridge'} if architecture == 'kernel' else set())
    check(isinstance(sections, list) and len(sections) == len(expected_roles), 'Wrong dispatcher section count')
    roles, allowed = {}, []
    for section in sections:
        offset, length = section['offset'], section['bytes']
        check(type(offset) is int and type(length) is int and length > 0, 'Invalid driver section size/offset')
        check(0 <= offset < offset+length <= len(before), 'Driver section outside component')
        data = read_locked(section, base=manifest_directory)
        check(len(data) == length and data == after[offset:offset+length], 'Delivered section bytes mismatch')
        check(digest(before[offset:offset+length]) == section['before_sha256'], 'Section original-byte lock mismatch')
        if offset == spec['library'][0]:
            role = 'library'
            check((length, digest(data)) == spec['library'][1:], 'Frozen four-table library changed')
        elif offset == spec['dispatch'][0]:
            role = 'dispatch'
            check(offset+length <= spec['dispatch'][1], 'Dispatch crossed preserved original tail')
        elif offset == spec['old_bridge'][0]:
            role = 'old_bridge'
            check(offset+length == spec['old_bridge'][1], 'Old bridge must remain one branch instruction')
        elif architecture == 'kernel' and offset == spec['boe_bridge'][0]:
            role = 'boe_bridge'
            check(offset+length == spec['boe_bridge'][1], 'BOE bridge must remain one branch instruction')
        else:
            raise ValueError('Unexpected driver section entry')
        check(role not in roles, 'Duplicate driver section role')
        roles[role] = {'name': section['name'], 'offset': offset, 'bytes': length, 'sha256': digest(data)}
        allowed.append((offset, length))
    check(set(roles) == expected_roles, 'Incomplete driver section roles')
    cursor = 0
    for offset, length in sorted(allowed):
        check(offset >= cursor and before[cursor:offset] == after[cursor:offset], 'Unexpected driver bytes outside final sections')
        cursor = offset+length
    check(before[cursor:] == after[cursor:], 'Unexpected driver suffix changed')
    receipt_raw = read_locked(record['execution_receipt'], base=manifest_directory)
    execution = json.loads(receipt_raw)
    check(execution.get('passed') is True and execution.get('arch') == architecture, 'Driver execution receipt failed/wrong architecture')
    check(set(execution.get('profiles_tested', [])) >= {0, 1, 2, 0xffffffff}, 'Driver execution missing default/explicit/unknown profile')
    check(set(execution.get('branches_tested', [])) >= {0, 1}, 'Driver execution missing old/boe branches')
    check(set(execution.get('relocation_slides', [])) >= {0, 0x01000000}, 'Driver execution missing relocation coverage')
    check(execution.get('getter_failure_tested') is True, 'Driver execution missing getter failure')
    runs = [row for row in execution.get('runs', []) if 'profile_input' in row]
    matrix = {(row['profile_input'], row['branch'], row['slide'], row['getter_ok']) for row in runs}
    expected_matrix = {(p, b, s, True) for p in (0, 1, 2, 0xffffffff) for b in (0, 1) for s in (0, 0x01000000)}
    expected_matrix |= {(1, b, 0, False) for b in (0, 1)}
    check(matrix >= expected_matrix, 'Driver receipt lacks complete execution cases')
    for row in runs:
        check(all(row.get(key) is True for key in ('exact_events', 'original_tail_reached', 'stack_callee_saved_reserved_registers')),
              'Driver recorded event/tail/ABI failure')
        use35h = row['getter_ok'] and row['profile_input'] == 1
        count = (294 if row['branch'] == 1 else 386) if use35h else (292 if row['branch'] == 1 else (635 if architecture == 'uboot' else 636))
        check(row['events'] == count, 'Driver receipt has wrong full event count')
    return {'original_sha256': digest(before), 'patched_sha256': digest(after), 'sections': roles,
            'execution_receipt_sha256': digest(receipt_raw), 'outside_sections_byte_exact': True}, allowed


def verify_prefix(before, after, artifacts, *, profile=0, manifest_directory=None):
    """Verify the complete prefix, using an independently locked manifest.

    artifacts contains passed:true and architectures.uboot/kernel; each has
    original_sha256, patched_sha256, original_bytes, three/four sections
    ({name,offset,bytes,sha256,file}), and execution_receipt({file,sha256}).
    Offsets are component-relative and never accepted as arbitrary whitelist.
    """
    check(type(profile) is int and profile in (0, 1), 'Unsupported explicit profile')
    check(len(before) == len(after) == PREFIX and digest(before) == BASE_PREFIX_SHA, 'Exact0.0.2 prefix required')
    check(artifacts.get('passed') is True and set(artifacts['architectures']) == {'uboot', 'kernel'}, 'Invalid frozen driver result')
    old_toc = before[TOC_START:TOC_START+TOC_SIZE]
    new_toc = after[TOC_START:TOC_START+TOC_SIZE]
    old_items, new_items = parse_toc(old_toc), parse_toc(new_toc)
    check(old_items == new_items, 'TOC item table changed')
    check(old_items['u-boot']['bytes'] == ARCH['uboot']['bytes'], 'U-Boot component length changed')
    check(old_items['dtb']['offset']+TOC_START == DTBS['uboot'][0] and old_items['dtb']['bytes'] == DTBS['uboot'][1], 'EarlyFDT item geometry changed')
    old_boot, new_boot = before[BOOT_START:BOOT_START+BOOT_SIZE], after[BOOT_START:BOOT_START+BOOT_SIZE]
    check(old_boot[:8] == new_boot[:8] == b'ANDROID!', 'Android boot header magic')
    check(struct.unpack_from('<I', old_boot, 8)[0] == KERNEL_SIZE and struct.unpack_from('<I', old_boot, 36)[0] == 2048, 'Original boot kernel/page geometry')
    expected_header = bytearray(old_boot[:2048])
    check(struct.unpack_from('<I', expected_header, 40)[0] == 2 and struct.unpack_from('<I', expected_header, 1648)[0] == DTBS['kernel'][2], 'Original v2 DTB header')
    struct.pack_into('<I', expected_header, 1648, DTBS['kernel'][2]+36)
    check(new_boot[:2048] == expected_header, 'Android header changed outside dtb_size')
    allowed = [(TOC_START+20, 4), (BOOT_START+1648, 4)]
    fdt_results = {}
    for name, (offset, capacity, _) in DTBS.items():
        fdt_results[name] = verify_fdt(before[offset:offset+capacity], after[offset:offset+capacity], name, profile)
        allowed.append((offset, capacity))
    components = {'uboot': (TOC_START+old_items['u-boot']['offset'], ARCH['uboot']['bytes']),
                  'kernel': (BOOT_START+2048, KERNEL_SIZE)}
    drivers = {}
    for name, (offset, length) in components.items():
        drivers[name], sections = verify_architecture(before[offset:offset+length], after[offset:offset+length], name,
                                                     artifacts['architectures'][name], manifest_directory=manifest_directory)
        allowed.extend((offset+start, size) for start, size in sections)
    cursor = 0
    for offset, length in sorted(allowed):
        check(offset >= cursor and before[cursor:offset] == after[cursor:offset], 'Unexpected prefix bytes outside exact allowed sections')
        cursor = offset+length
    check(before[cursor:] == after[cursor:], 'Unexpected prefix suffix changed')
    return {'profile': profile, 'automatic_hardware_identity': False, 'FDTs': fdt_results, 'drivers': drivers,
            'kernel_changed_only_in_reviewed_init_sections': True, 'ramdisk_unchanged': True,
            'boot0_GPT_environment_resource_monitor_dtbo_unchanged': True,
            'prefix_sha256': digest(after), 'changed_byte_count': sum(a != b for a, b in zip(before, after)),
            'allowed_sections': [{'offset': offset, 'bytes': length} for offset, length in sorted(allowed)]}


def main(args):
    constrained()
    started = time.monotonic()
    destination = args.output / 'independent-verify.json'
    check(not destination.exists(), 'Retain existing independent verification receipt')
    report = {'passed': False, 'physical_display_tested': False, 'automatic_hardware_identity': False}
    try:
        verify_reference()
        check(file_sha(REPO/'docs/SPACE_REVIEW_20261028.md') == SPACE_SHA, 'Protected SPACE_REVIEW changed')
        artifacts = read_json(args.artifacts)
        artifacts_sha = file_sha(args.artifacts)
        receipt = read_json(args.output/'image-result.json')
        check(receipt['passed'], 'Package not complete')
        check(receipt['driver_artifacts_sha256'] == artifacts_sha, 'Package driver-artifact lock mismatch')
        image = ordinary(receipt['image'])
        check(file_sha(image) == receipt['sha256'], 'Compressed SHA mismatch')
        with ordinary(BASE).open('rb') as reader:
            before = reader.read(PREFIX)
        whole = hashlib.sha256()
        ranges = {name: hashlib.sha256() for name in RANGES}
        prefix, tail, total = bytearray(), b'', 0
        print('PHASE=independent_complete_gzip_and_card_ranges', flush=True)
        with gzip.open(image, 'rb') as reader:
            while block := reader.read(4*1024**2):
                end = total+len(block)
                check(end <= SIZE, 'Gzip expands past card')
                whole.update(block)
                if total < PREFIX:
                    prefix.extend(block[:min(len(block), PREFIX-total)])
                tail = (tail+block)[-1536:]
                for name, (offset, length) in RANGES.items():
                    lo, hi = max(total, offset), min(end, offset+length)
                    if lo < hi:
                        ranges[name].update(block[lo-total:hi-total])
                total = end
        check(total == SIZE and whole.hexdigest() == receipt['raw_sha256'], 'Expanded card mismatch')
        actual_hashes = {name: value.hexdigest() for name, value in ranges.items()}
        for name in RANGES:
            check(actual_hashes[name] == receipt['ranges'][name]['sha256'], 'Package range mismatch: '+name)
            if name != 'prefix':
                check(actual_hashes[name] == PARENT_RANGES[name], 'Delivered Android/GPT range changed: '+name)
        print('PHASE=independent_two_FDTs_driver_sections_and_prefix', flush=True)
        prefix_result = verify_prefix(before, bytes(prefix), artifacts, profile=args.profile,
                                      manifest_directory=args.artifacts.resolve().parent)
        gpt = verify_gpt(bytes(prefix[:1024**2]), tail)
        check(file_sha(ordinary(receipt['raw'])) == whole.hexdigest(), 'Regular raw/gzip mismatch')
        check(file_sha(args.artifacts) == artifacts_sha, 'Artifact manifest changed during verification')
        check(file_sha(REPO/'docs/SPACE_REVIEW_20261028.md') == SPACE_SHA, 'Protected SPACE_REVIEW changed during verification')
        report.update(passed=True, gzip_sha256=receipt['sha256'], raw_sha256=whole.hexdigest(), raw_bytes=total,
                      ranges=actual_hashes, prefix=prefix_result, GPT=gpt, artifacts_sha256=artifacts_sha,
                      system_vendor_userdata_identical_to_002=True, elapsed_seconds=time.monotonic()-started)
        print(json.dumps({'passed': True, 'profile': args.profile, 'raw_sha256': whole.hexdigest()}), flush=True)
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--profile', type=int, choices=[0, 1], default=0)
    parser.add_argument('--work', type=Path, help='Accepted for consistency with ordinary-file packaging wrappers')
    main(parser.parse_args())

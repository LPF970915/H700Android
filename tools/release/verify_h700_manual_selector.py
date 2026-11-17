"""Independently inspect the delivered manual-model Test5 image.

No integrator/patcher is imported. Every changed boot region is parsed and
checked against fixed source artifacts; full-image verification reads ordinary
files and writes a fresh verification directory only.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import os
import re
import stat
import struct
import subprocess
import sys
import time
import zlib

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained
import verify_h700_shared_panel as shared_verify
from verify_002 import stream_ranges, verify_gpt, tree_inventory, metadata

BASE = Path('/home/lpf/roc-os-002-20261114-v1/ROC_OS_ARM64_ver0.0.2.img')
BASE_SYSTEM = BASE.parent / 'system.002.raw'
NAME = 'ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test5_20261114.img'
SHARED_SHA = '277e07f91aa508e2b269b7a56f90a3486d5791148bd231c7336f0a69c99f4b88'
ENV_START, ENV_BYTES = 138412032, 131072
PREFIX, BOOT_START, BOOT_BYTES = 222298112, 155189248, 67108864
TOC_START, TOC_BYTES = 16793600, 1310720
PANEL = '/soc@03000000/lcd0@01c0c000'
PANEL_MANIFEST = REPO / 'out/rg34xx-boot-analysis-20261114/panel-dispatch-v5/result.json'
PANEL_MANIFEST_SHA = '21773ba2b2eaf2b29c7a045ff7ded309f90ff1d6c6839c57916c56e9871feca4'
BASE_INIT_SHA = '454c666b454bfcafc1afa96ba9b7665ce1f9b62a2e730b7f7009fde71f39273a'
BRIDGE_SHA = 'cd0eaa149ce3117c3434b1988064e376be44dea1330846c93161f1f0e9560acd'
ELF_SHA = '49dbda95f321dd6abf25cad567cd6dec00d15beb4b6a7dfe870a67ad0b7a25ec'
BRIDGE_RECEIPT_SHA = '53f6f9e2946555f88d0b1c7d696f9a5ea4d115483c2aa29ee7131a15deae68d2'
EXECUTION_SHA = 'f874fc165d4811dcd17ff70a8c1b7779280f4ea549c40cf4b39f1e961bb9fcef'
PAYLOAD_SHA = '7a8a6b71436c330bcb281f23590aa6dcbce94e69766590d19ba6cfaa48853127'
MENU_SHA = '1f685652b248c1b3869dbb2ae9613da6a18175d15d404a11974a4c5fb35ed7ea'
HELPER_SHA = '45b726a5b0f6302252e76e77b063f7e814ce735ae3ffa8f896def7f3c9da94c9'
HOOK_SHA = 'aaa207f24a06745c7ba78538748871913810deae907d9eff1060487cead0336a'
NOTICE_SHA = '6a73f9541c2de74158c0e7cf6b0a58ef774f5a780bf191f2d7ec9cc53efe2bf2'
LID_SHA = '8b79b5f78914db5db250e3daa9410dab3d469cc6867d2189faded19cebd2b724'
LID_RECEIPT_SHA = 'b4272918e12781b60eb50a1cec4d9b5915f163d853b100f5015e3d2b689c62ce'
SYSTEM_SHA = '9ccb1d19cd78ecaabffdce16321e509146b45bc4807c38157d471c4616134e6e'
PARSER_PROOF_SHA = '88fd93615b563284f84f3a1a600b09648f086bf231cdeaa39355c330dfab1833'
PARSER_CASES_SHA = '2341a9a024d7651d420fd13eece32c9fbb7dcc9f3eac73d0114e905fb49a5e8b'
FDT_CASES_SHA = 'ebd23e17b5040a49b7ac243e0c6568008178668a8092f83973012b0b4a2e95ba'
CANDIDATE_ENV_SHA = '1d0ee64c05516f24bf905ddc696a0f3ea96c9a76082de483fb29411a888bd9d8'
LID = '/system/priv-app/ROCReleaseLid/ROCReleaseLid.apk'
REMOVED = ['/system/priv-app/ROCReleaseLid/oat/arm64/ROCReleaseLid.odex',
           '/system/priv-app/ROCReleaseLid/oat/arm64/ROCReleaseLid.vdex']
DEPENDENCIES = {
    'tools/release/verify_002.py': 'a737f350f8e8765b21105bc32ee497ef74f35ac6cea98d1c956caed88ab957a6',
    'tools/release/verify_h700_shared_panel.py': 'e4c4aac9c2655d9fbd2c17cc9f3a593b1c0772cee2d57e6f2dd4814068612faf',
    'tools/package_h700_v6a.py': '60dc0136f0c04c16d1ffda2257f063a018f48232e1374bfee0505483425def71',
}
INIT_CALL = (b'# Manual model choice runs before filesystem expansion and before Android.\n'
             b'if ! /bin/sh /grow/roc-selector-init.sh "$TF1"; then\n'
             b'    echo "[roc-selector] selector failed; preserving current panel and Android diagnostic boot"\n'
             b'fi\n')


def check(ok, why):
    if not ok:
        raise ValueError(why)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def regular(path):
    path = Path(path)
    check(not path.is_symlink() and stat.S_ISREG(path.lstat().st_mode), 'Ordinary file required: ' + str(path))
    return path


def file_sha(path):
    with regular(path).open('rb') as reader:
        return hashlib.file_digest(reader, 'sha256').hexdigest()


def locked(path, expected):
    data = regular(path).read_bytes()
    check(sha(data) == expected, 'Frozen artifact mismatch: ' + str(path))
    return data


def unchanged_outside(before, after, spans, label):
    check(len(before) == len(after), label + ' length changed')
    cursor = 0
    for offset, length in sorted(spans):
        check(type(offset) is int and type(length) is int and cursor <= offset < offset + length <= len(before),
              label + ' invalid/overlapping permitted span')
        check(before[cursor:offset] == after[cursor:offset], label + ' unexpected bytes outside permitted spans')
        cursor = offset + length
    check(before[cursor:] == after[cursor:], label + ' unexpected suffix')


def boot_parts(blob):
    check(len(blob) == BOOT_BYTES and blob[:8] == b'ANDROID!', 'Android boot partition identity')
    check(struct.unpack_from('<II', blob, 36) == (2048, 2), 'Android v2 page/header version')
    check(struct.unpack_from('<I', blob, 1632)[0] == 0 and struct.unpack_from('<Q', blob, 1636)[0] == 0,
          'Unexpected recovery_dtbo layout')
    check(struct.unpack_from('<I', blob, 1644)[0] == 1660, 'Android header_size')
    result, offset = {}, 2048
    for name, field in [('kernel', 8), ('ramdisk', 16), ('second', 24), ('dtb', 1648)]:
        size = struct.unpack_from('<I', blob, field)[0]
        end = offset + size
        padded = (end + 2047) & ~2047
        check(end <= padded <= BOOT_BYTES and not any(blob[end:padded]), 'Component bounds/zero page padding: ' + name)
        result[name] = {'offset': offset, 'bytes': size, 'data': blob[offset:end]}
        offset = padded
    check(result['kernel']['bytes'] == 17686536 and result['dtb']['bytes'] == 137600,
          'Frozen kernel/FDT sizes changed')
    check(struct.unpack_from('>II', result['dtb']['data']) == (0xd00dfeed, result['dtb']['bytes']), 'Kernel FDT v2 size mismatch')
    check(blob[offset:] == b'\xff' * (BOOT_BYTES - offset), 'Boot partition erased tail changed')
    result['end'] = offset
    return result


def cpio(blob):
    """Strict newc parser independent of the packaging emitter."""
    rows, pos = [], 0
    names = set()
    while pos + 110 <= len(blob):
        check(blob[pos:pos+6] == b'070701', 'CPIO newc header missing')
        raw_fields = blob[pos+6:pos+110]
        check(re.fullmatch(rb'[0-9a-fA-F]{104}', raw_fields) is not None, 'CPIO malformed hex')
        fields = [int(raw_fields[i:i+8], 16) for i in range(0, 104, 8)]
        size, name_size = fields[6], fields[11]
        name_end = pos + 110 + name_size
        data_start = (name_end + 3) & ~3
        data_end = data_start + size
        end = (data_end + 3) & ~3
        check(1 <= name_size <= 4096 and end <= len(blob), 'CPIO truncated/invalid entry')
        raw_name = blob[pos+110:name_end]
        check(raw_name[-1:] == b'\0' and b'\0' not in raw_name[:-1], 'CPIO invalid filename termination')
        name = raw_name[:-1].decode('utf-8', 'strict')
        check(name not in names and not name.startswith('/') and '..' not in name.split('/'), 'CPIO duplicate/unsafe path')
        check(not any(blob[name_end:data_start]) and not any(blob[data_end:end]), 'CPIO nonzero entry padding')
        names.add(name)
        rows.append({'name': name, 'fields': fields, 'data': blob[data_start:data_end]})
        pos = end
        if name == 'TRAILER!!!':
            check(size == 0 and not any(blob[pos:]), 'CPIO trailer/trailing payload')
            return rows
    raise ValueError('CPIO trailer missing')


def verify_ramdisk(before, after, artifactdir):
    check(after[:3] == b'\x1f\x8b\x08' and after[3] == 0 and after[4:8] == bytes(4), 'Ramdisk gzip flags/mtime')
    old, new = cpio(gzip.decompress(before)), cpio(gzip.decompress(after))
    original = {row['name']: row for row in old}
    delivered = {row['name']: row for row in new}
    check(sha(original['init']['data']) == BASE_INIT_SHA, 'Exact parent init required')
    anchor = b'DATA_DEV=${TF1}p7\n'
    check(original['init']['data'].count(anchor) == 1, 'Parent init selector anchor')
    expected_init = original['init']['data'].replace(anchor, anchor + INIT_CALL)
    additions = [('grow/roc-boot-selector', artifactdir/'native/build-v4/roc-boot-selector', MENU_SHA),
                 ('grow/roc-boot-state', artifactdir/'boot-state-v2/boot-state-aarch64', HELPER_SHA),
                 ('grow/roc-selector-init.sh', REPO/'tools/boot_selector/selector_init.sh', HOOK_SHA),
                 ('grow/ROC-SELECTOR-FONT-NOTICE.txt', artifactdir/'native/generated-v2/FONT-NOTICE.txt', NOTICE_SHA)]
    check([row['name'] for row in new] == [row['name'] for row in old[:-1]] + [row[0] for row in additions] + ['TRAILER!!!'],
          'CPIO entry set/order changed')
    for name, row in original.items():
        check(delivered[name]['data'] == (expected_init if name == 'init' else row['data']), 'Original CPIO payload changed: ' + name)
        fields = row['fields'].copy()
        if name == 'init':
            fields[6] = len(expected_init)
        check(delivered[name]['fields'] == fields, 'Original CPIO metadata changed: ' + name)
    for i, (name, path, expected_sha) in enumerate(additions):
        raw = locked(path, expected_sha)
        row = delivered[name]
        check(row['data'] == raw, 'Delivered CPIO artifact mismatch: ' + name)
        fields = original['init']['fields'].copy()
        fields[0:5] = [19000+i, stat.S_IFREG | (0o644 if name.endswith('.txt') else 0o755), 0, 0, 1]
        fields[6], fields[11] = len(raw), len(name.encode('utf-8')) + 1
        check(row['fields'] == fields, 'Added CPIO metadata mismatch: ' + name)
        if not name.endswith(('.sh', '.txt')):
            check(raw[:7] == b'\x7fELF\x02\x01\x01' and struct.unpack_from('<H', raw, 18)[0] == 183, 'Native artifact architecture')
            phoff = struct.unpack_from('<Q', raw, 32)[0]
            phsize, phnum = struct.unpack_from('<HH', raw, 54)
            check(phsize == 56 and phoff+phsize*phnum <= len(raw), 'Native ELF program-header bounds')
            check(all(struct.unpack_from('<I', raw, phoff+j*phsize)[0] != 3 for j in range(phnum)), 'Native artifact has dynamic interpreter')
    return {'original_entries': len(old), 'added_entries': [row[0] for row in additions],
            'original_metadata_preserved': True, 'init_sha256': sha(expected_init),
            'ramdisk_sha256': sha(after), 'static_AArch64_payloads': True}


def parse_env(block):
    check(len(block) == ENV_BYTES and struct.unpack_from('<I', block)[0] == zlib.crc32(block[4:]), 'Environment CRC/length')
    body = block[4:]
    end = body.find(b'\0\0')
    check(end > 0 and not any(body[end:]), 'Environment terminator/padding')
    rows = []
    for i, row in enumerate(body[:end].split(b'\0')):
        if i == 0 and row == b'':
            rows.append(('', ''))
        else:
            check(b'=' in row, 'Environment malformed row')
            key, value = row.decode('ascii').split('=', 1)
            check(key and re.fullmatch(r'[A-Za-z0-9_]+', key), 'Environment malformed key')
            rows.append((key, value))
    check(len(dict(rows)) == len(rows), 'Environment duplicate key')
    return rows


def verify_environment(before, after, dtb_offset, kernel_dtb):
    old, new = parse_env(before), parse_env(after)
    original, actual = dict(old), dict(new)
    check(original['boot_normal'] == 'sunxi_flash read 45000000 boot;bootm 45000000' and not any(k.startswith('roc_') for k in original), 'Unexpected parent environment')
    check(type(dtb_offset) is int and dtb_offset % 2048 == 0, 'Kernel FDT page offset')
    address = 0x45000000 + dtb_offset
    check(0x45000000 < address < 0x49000000, 'Kernel FDT address bounds')

    # This independently specified order is part of the simple-parser ABI.
    # In particular, neither a semicolon list nor Hush syntax stops safely on
    # a failed leaf in the actual U-Boot. Each nested run has one command only.
    properties = ('roc_panel_profile', 'lcd_x', 'lcd_y', 'lcd_dclk_freq',
                  'lcd_hbp', 'lcd_ht', 'lcd_hspw', 'lcd_vbp', 'lcd_vt',
                  'lcd_vspw', 'lcd_hv_clk_phase', 'lcd_hv_sync_polarity')
    values = ((0, 720, 480, 26, 46, 820, 2, 20, 536, 5, 1, 3),
              (1, 640, 480, 24, 46, 770, 20, 15, 520, 4, 2, 3))
    fdt_header, fdt_properties, fdt_nodes = shared_verify.parse_fdt(kernel_dtb)
    check(fdt_header[1] == len(kernel_dtb) == 137600 and PANEL in fdt_nodes,
          'Kernel FDT exact size/panel node')
    for name, value in zip(properties, values[0]):
        key = PANEL + '/' + name
        check(key in fdt_properties and len(fdt_properties[key][1]) == 4,
              'Kernel FDT setter requires an existing four-byte cell: ' + name)
        check(fdt_properties[key][1] == struct.pack('>I', value),
              'Kernel FDT must retain legacy720 before dispatch: ' + name)

    expected = {
        'boot_normal': 'run roc_selector_apply',
        'roc_selector_schema': '2',
        'roc_selector_apply': 'run roc_load_boot roc_dispatch roc_boot_args roc_boot_kernel',
        'roc_load_boot': 'sunxi_flash read 45000000 boot',
        'roc_dispatch': 'run roc_apply_${roc_active_model}',
        'roc_fdt_addr': 'fdt addr ' + format(address, 'x'),
    }
    for profile, model, lid in [(0, 'rg34xxsp', 1), (1, 'rg35xxh', 0)]:
        leaves = ['roc_' + str(profile) + '_' + name for name in properties]
        expected['roc_apply_' + model] = 'run ' + ' '.join(['roc_fdt_addr'] + leaves + ['roc_lid' + str(lid)])
        for name, value, leaf in zip(properties, values[profile], leaves):
            expected[leaf] = "fdt set " + PANEL + ' ' + name + " '<0x" + format(value, 'x') + ">'"
    expected.update({
        'roc_apply_rgsp': 'run roc_apply_rg34xxsp',
        'roc_lid0': 'setenv roc_clamshell 0',
        'roc_lid1': 'setenv roc_clamshell 1',
        'roc_boot_args': 'setenv bootargs ${bootargs} androidboot.roc_model=${roc_active_model} '
                         'androidboot.roc_clamshell=${roc_clamshell} androidboot.roc_route=${roc_boot_route}',
        'roc_boot_kernel': 'bootm 45000000',
    })
    check(len(expected) == 37, 'Independent environment allowlist size')
    expected_rows = [(k, expected.get(k, v)) for k, v in old]
    expected_rows += [(k, v) for k, v in expected.items() if k not in original]
    check(new == expected_rows, 'Environment values, variables or row order differ from the independent 37-item allowlist')
    check(set(actual) == set(original) | set(expected), 'Unexpected selector environment key')
    check({k: v for k, v in actual.items() if k != 'boot_normal' and not k.startswith('roc_')} ==
          {k: v for k, v in original.items() if k != 'boot_normal'}, 'Unrelated parent environment changed')

    for key, command in expected.items():
        if key == 'roc_selector_schema':
            continue
        check(len(command.encode('ascii')) < 1024 and not any(c in command for c in (';', '&', '|', '\n', '\r', '\t')),
              'Selector command exceeds the literal simple-parser boundary: ' + key)
        check(not set(command.split()) & {'if', 'then', 'else', 'fi'}, 'Hush conditional in selector command: ' + key)
        check(len(command.split()) < 100, 'Selector literal reaches the argument truncation boundary: ' + key)
    check(original['bootcmd'] == 'run setargs_nand boot_normal', 'Parent boot command order changed')
    for key in ('setargs_nand', 'setargs_mmc'):
        check(re.match(r'^setenv +bootargs ', original[key]) is not None and '${bootargs}' not in original[key],
              'Complete bootcmd retry must replace the previous bootargs: ' + key)
    check('run roc_selector_apply' in actual['boot_normal'] and actual['roc_selector_apply'],
          'Frozen boot-state helper literal hook contract')
    return {'schema': 2, 'saved_default': None, 'kernel_fdt_address': hex(address),
            'exact_twelve_setters_per_profile': True, 'existing_twelve_four_byte_cells_prechecked': True,
            'strict_changed_variable_allowlist': len(expected), 'single_command_nested_run': True,
            'maximum_literal_bytes': max(len(value.encode('ascii')) for value in expected.values()),
            'maximum_literal_arguments': max(len(value.split()) for value in expected.values()),
            'complete_bootcmd_retry_replaces_bootargs': True, 'direct_boot_normal_retry_idempotent': False,
            'expanded_runtime_bootargs_bounds_require_actual_parser_execution': True,
            'boot_state_literal_hook_compatible': True, 'unknown_rows_preserved': True, 'sha256': sha(after)}


def verify_bridge(before, after, artifactdir):
    folder = artifactdir/'early-hook-v5'
    manifest = json.loads(locked(folder/'result.json', BRIDGE_RECEIPT_SHA))
    check(manifest['passed'] is True and manifest['host_cases'] == 154 and manifest['all_original_relocations'] == 11978,
          'Early bridge execution manifest')
    check(manifest['bridge_semantics_version'] == 5 and manifest['unsaved_route'] == 'selector' and
          manifest['unsaved_model'] == 'rg35xxh' and manifest['unsaved_profile'] == '35H640' and
          manifest['hotkey_changes_route_only'] is True and manifest['automatic_profile_probe'] is False,
          'First640 menu / saved hotkey semantics receipt')
    check(manifest['first_display_after_environment'] is True and manifest['early_clock_init_preserved'] is True,
          'Early display/environment order receipt')
    locked(folder/'execution.json', EXECUTION_SHA)
    check(len(before) == len(after) == 1048576 and after == locked(folder/'uboot.early-selector.bin', BRIDGE_SHA), 'Delivered bridge full identity')
    payload = locked(folder/'early-bridge.bin', PAYLOAD_SHA)
    check(len(payload) == 944, 'Bridge payload length')
    elf = locked(folder/'early-bridge.elf', ELF_SHA)
    check(elf[:7] == b'\x7fELF\x01\x01\x01' and struct.unpack_from('<HH', elf, 16) == (2,40), 'Early bridge ELF identity')
    shoff = struct.unpack_from('<I', elf, 32)[0]
    stride, count, name_index = struct.unpack_from('<HHH', elf, 46)
    check(stride == 40 and shoff+stride*count <= len(elf) and name_index < count, 'Bridge ELF section bounds')
    headers = [struct.unpack_from('<10I', elf, shoff+i*stride) for i in range(count)]
    strings = headers[name_index]
    names = elf[strings[4]:strings[4]+strings[5]]
    allocated = []
    for row in headers:
        check(row[4]+row[5] <= len(elf) or row[1] == 8, 'Bridge ELF section file bounds')
        check(not(row[1] in (4,9) and row[5]), 'Bridge ELF unresolved relocations')
        if row[2] & 2 and row[5]:
            check(row[0] < len(names) and names[row[0]:].split(b'\0',1)[0] == b'.early_bridge' and row[1] == 1 and row[3] == 0x4a026500, 'Unexpected allocated bridge section')
            allocated.append(elf[row[4]:row[4]+row[5]])
    check(allocated == [payload], 'Bridge ELF/bin mismatch')
    fixed = [(0x2a20, bytes.fromhex('00207047')),
             (0xf1be, bytes.fromhex('00bf00bf')),
             (0x9ee64, struct.pack('<I',0x4a026501)), (0x26500,payload)]
    check([(row['offset'],row['bytes']) for row in manifest['patches']] == [(p,len(v)) for p,v in fixed], 'Bridge bounded patch manifest')
    for (offset, data), receipt in zip(fixed, manifest['patches']):
        check(after[offset:offset+len(data)] == data and sha(data) == receipt['sha256'], 'Bridge fixed patch mismatch')
        check(sha(before[offset:offset+len(data)]) == receipt['before_sha256'], 'Bridge original section identity')
    unchanged_outside(before, after, [(o,len(v)) for o,v in fixed], 'U-Boot')
    check(before[0xe6450:0xfdaa0] == after[0xe6450:0xfdaa0], 'Original relocation table changed')
    return {'sha256': sha(after), 'payload_sha256': sha(payload), 'fixed_patches': len(fixed),
            'outside_four_patches_byte_exact': True, 'original_relocation_table_preserved': True}, [(o,len(v)) for o,v in fixed]


def verify_prefix(base, shared, actual, artifactdir):
    """Verify independent bounded integration; callable by prepare before freeze."""
    base, shared, actual = bytes(base), bytes(shared), bytes(actual)
    artifactdir = Path(artifactdir)
    check(len(base) == len(shared) == len(actual) == PREFIX and sha(shared) == SHARED_SHA, 'Frozen shared prefix identity')
    manifest = json.loads(locked(PANEL_MANIFEST, PANEL_MANIFEST_SHA))
    shared_proof = shared_verify.verify_prefix(base, shared, manifest, profile=0, manifest_directory=PANEL_MANIFEST.parent)
    old_toc = shared_verify.parse_toc(shared[TOC_START:TOC_START+TOC_BYTES])
    new_toc = shared_verify.parse_toc(actual[TOC_START:TOC_START+TOC_BYTES])
    check(old_toc == new_toc, 'Manual integration changed TOC item table')
    ustart = TOC_START + old_toc['u-boot']['offset']
    usize = old_toc['u-boot']['bytes']
    bridge, patches = verify_bridge(shared[ustart:ustart+usize], actual[ustart:ustart+usize], artifactdir)
    before_boot, actual_boot = shared[BOOT_START:BOOT_START+BOOT_BYTES], actual[BOOT_START:BOOT_START+BOOT_BYTES]
    old, new = boot_parts(before_boot), boot_parts(actual_boot)
    unchanged_outside(before_boot[:2048], actual_boot[:2048], [(16,4)], 'Android v2 header')
    for name in ('kernel', 'second', 'dtb'):
        check(old[name]['data'] == new[name]['data'], 'Unrelated Android component changed: '+name)
    ramdisk = verify_ramdisk(old['ramdisk']['data'], new['ramdisk']['data'], artifactdir)
    environment = verify_environment(shared[ENV_START:ENV_START+ENV_BYTES], actual[ENV_START:ENV_START+ENV_BYTES], new['dtb']['offset'], new['dtb']['data'])
    proofdir = artifactdir/'actual-uboot-parser-v1'
    parser_proof = json.loads(locked(proofdir/'result.json', PARSER_PROOF_SHA))
    candidate = json.loads(locked(artifactdir/'test5-env-draft-v1/candidate-env.json', CANDIDATE_ENV_SHA))
    check(parser_proof['status'] == 'PASS' and type(parser_proof['case_count']) is int and parser_proof['case_count'] > 100 and
          parser_proof['uboot_sha256'] == BRIDGE_SHA, 'Actual U-Boot parser proof identity/status')
    check(parser_proof['candidate_sha256'] == CANDIDATE_ENV_SHA and
          parser_proof['candidate_environment'] == candidate == dict(parse_env(actual[ENV_START:ENV_START+ENV_BYTES])),
          'Actual parser proof candidate differs from delivered environment')
    check(parser_proof['parser_result'] == 'result-attempt3.json' and parser_proof['parser_result_sha256'] == PARSER_CASES_SHA,
          'Actual parser cases receipt binding')
    locked(proofdir/'result-attempt3.json', PARSER_CASES_SHA)
    check(parser_proof['real_fdt_passed'] is True and parser_proof['real_fdt_case_count'] == 18 and
          parser_proof['real_fdt_result'] == 'result-attemptreal-fdt-5.json' and parser_proof['real_fdt_result_sha256'] == FDT_CASES_SHA,
          'Actual FDT handler/libfdt proof binding')
    locked(proofdir/'result-attemptreal-fdt-5.json', FDT_CASES_SHA)
    check(parser_proof['physical_display_accepted'] is False and parser_proof['device_or_card_accessed'] is False,
          'Host proof must preserve the physical acceptance boundary')
    parser_result = {'passed': True, 'receipt_sha256': PARSER_PROOF_SHA,
                     'candidate_environment_sha256': CANDIDATE_ENV_SHA,
                     'actual_parser_cases': parser_proof['case_count'], 'actual_FDT_cases': parser_proof['real_fdt_case_count'],
                     'modeled_boundaries': parser_proof['modeled_boundaries'], 'physical_display_accepted': False}
    allowed = [(TOC_START+20,4), (ENV_START,ENV_BYTES), (BOOT_START,BOOT_BYTES)] + [(ustart+o,n) for o,n in patches]
    unchanged_outside(shared, actual, allowed, 'Complete prefix')
    return {'passed': True, 'prefix_sha256': sha(actual), 'shared_prefix_sha256': sha(shared),
            'shared_parent_independently_verified': True, 'shared_drivers': shared_proof['drivers'],
            'bridge': bridge, 'ramdisk': ramdisk, 'environment': environment, 'actual_parser_and_FDT_execution': parser_result,
            'kernel_second_DTB_byte_exact_shared': True, 'TOC_checksum_verified': True,
            'boot0_GPT_resource_monitor_dtbo_and_unused_env_tail_preserved': True,
            'integrated_models': ['rg34xxsp','rgsp','rg35xxh'], 'menu_models': 12,
            'physical_display_accepted': False, 'all_H700_models_accepted': False}


def main(args):
    constrained()
    started = time.monotonic()
    destination = args.output/'independent-verify.json'
    check(not destination.exists(), 'Preserve existing independent receipt')
    folder = args.work/'independent-verification'
    check(not folder.exists(), 'Fresh independent extraction directory required')
    folder.mkdir()
    report = {'passed': False, 'independent': True, 'physical_display_accepted': False,
              'all_H700_models_accepted': False, 'device_accessed': False}
    controls = {}
    def run(argv):
        result = subprocess.run(list(map(str,argv)), text=True, capture_output=True)
        with (folder/'commands.log').open('a') as writer:
            writer.write(json.dumps(list(map(str,argv)))+'\nexit='+str(result.returncode)+'\n'+result.stdout+result.stderr+'\n')
        check(result.returncode == 0, 'Independent command failed; inspect commands.log')
        return result.stdout
    try:
        controls = {str(path): file_sha(path) for path in [Path(__file__), args.output/'image-result.json',
                    args.work/'input-lock.json', REPO/'docs/SPACE_REVIEW_20261028.md']}
        for name, digest in DEPENDENCIES.items():
            check(file_sha(REPO/name) == digest, 'Independent verifier dependency changed: '+name)
            controls[str(REPO/name)] = digest
        check(controls[str(REPO/'docs/SPACE_REVIEW_20261028.md')] == shared_verify.SPACE_SHA, 'Protected SPACE_REVIEW changed')
        receipt = json.loads(regular(args.output/'image-result.json').read_text())
        check(receipt['passed'] is True and receipt['version'] == '0.0.2', 'Package incomplete')
        image, raw = regular(args.output/(NAME+'.gz')), regular(args.work/NAME)
        check(Path(receipt['image']).resolve() == image.resolve() and Path(receipt['raw']).resolve() == raw.resolve(), 'Package artifact paths differ')
        check(file_sha(image) == receipt['sha256'], 'Compressed image SHA mismatch')
        print('PHASE=independent_full_gzip_and_ranges', flush=True)
        actual_prefix, actual_system = folder/'prefix.raw', folder/'system.raw'
        with gzip.open(image,'rb') as reader:
            streamed = stream_ranges(reader, {'prefix': actual_prefix, 'system': actual_system})
        check(streamed['sha256'] == receipt['raw_sha256'] and streamed['bytes'] == receipt['raw_bytes'] == 32434554368,
              'Complete expanded gzip SHA/size mismatch')
        check(raw.stat().st_size == streamed['bytes'] and file_sha(raw) == streamed['sha256'], 'Raw/gzip whole-image mismatch')
        for name, value in streamed['ranges'].items():
            check(receipt['ranges'][name]['sha256'] == value, 'Package range SHA mismatch: '+name)
            if name not in ('prefix','system'):
                check(value == shared_verify.PARENT_RANGES[name], 'Unrelated delivered range changed: '+name)
        check(file_sha(actual_prefix) == file_sha(args.work/'prefix.manual.raw') and file_sha(actual_system) == file_sha(args.work/'system.manual.raw'),
              'Actual delivered prefix/system differs from independently verified ordinary input')
        check(file_sha(actual_system) == SYSTEM_SHA, 'Test5 system must preserve the exact independently accepted Test4 bytes')
        with regular(BASE).open('rb') as reader:
            base = reader.read(PREFIX)
        print('PHASE=independent_boot_components_and_bounded_prefix', flush=True)
        prefix = verify_prefix(base, regular(args.work/'prefix.shared.raw').read_bytes(), actual_prefix.read_bytes(),
                               REPO/'out/boot-selector-integration-20261114')
        gpt = verify_gpt(streamed['head'], streamed['tail'])
        print('PHASE=independent_actual_system_filesystem_delta', flush=True)
        check(file_sha(BASE_SYSTEM) == shared_verify.PARENT_RANGES['system'], 'Exact parent system identity')
        inventories = []
        for label, source in [('base', BASE_SYSTEM), ('actual', actual_system)]:
            target = folder/(label+'-tree')
            target.mkdir()
            run(['/usr/sbin/debugfs','-R','rdump / '+str(target),source])
            inventories.append(tree_inventory(target))
        before, after = inventories
        delta = {'added': sorted(after.keys()-before.keys()), 'removed': sorted(before.keys()-after.keys()),
                 'changed': sorted(p for p in before.keys() & after.keys() if before[p] != after[p])}
        check(delta == {'added': [], 'removed': sorted(REMOVED), 'changed': [LID]}, 'Actual filesystem delta differs from reviewed Lid change')
        check(after[LID]['sha256'] == LID_SHA, 'Actual Lid APK SHA mismatch')
        lid_receipt = json.loads(locked(REPO/'out/boot-selector-integration-20261114/lid-model/20261114-083202-709381/build-result.json', LID_RECEIPT_SHA))
        check(lid_receipt['passed'] is True and lid_receipt['artifact_sha256'] == LID_SHA and
              lid_receipt['old_and_new_Android10_signature_verified'] is True and
              lid_receipt['platform_certificate_sha256'] == 'fc30e834b3c2914a0646d0b46c4faaa045aa8d46189950012555a5f2c36745c9',
              'Frozen Lid signature/identity receipt differs')
        check(before[LID]['sha256'] == lid_receipt['original_apk_sha256'] and
              all(before[p]['sha256'] == lid_receipt['remove_stale_oat'][p] for p in REMOVED), 'Parent Lid/preopt identities differ')
        old_meta = metadata(run(['/usr/sbin/debugfs','-R','stat '+LID,BASE_SYSTEM]),LID)
        new_meta = metadata(run(['/usr/sbin/debugfs','-R','stat '+LID,actual_system]),LID)
        check(old_meta == new_meta, 'Lid filesystem permissions/owner/SELinux label changed')
        run(['/usr/sbin/e2fsck','-f','-n',actual_system])
        check(all(file_sha(Path(p)) == value for p,value in controls.items()), 'Verifier/package inputs changed during verification')
        report.update(passed=True, raw_sha256=streamed['sha256'], raw_bytes=streamed['bytes'], gzip_sha256=receipt['sha256'],
                      ranges=streamed['ranges'], prefix=prefix, GPT=gpt, filesystem_delta=delta,
                      actual_Lid_sha256=LID_SHA, actual_Lid_metadata=new_meta, system_readonly_fsck_passed=True,
                      actual_Lid_identical_to_Android10_signature_verified_frozen_artifact=True,
                      vendor_userdata_GPT_unchanged=True, original_other_system_payloads_preserved=True,
                      controls=controls)
        print('H700_MANUAL_MODEL_TEST5_INDEPENDENT_VERIFICATION_PASS', flush=True)
    except BaseException as error:
        report['failure'] = type(error).__name__+': '+str(error)
        raise
    finally:
        report['elapsed_seconds'] = time.monotonic()-started
        destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args())

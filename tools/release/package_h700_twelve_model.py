"""Prepare/package twelve explicit H700 models in ordinary Test7 file copies.

No block devices, mounts, live handheld commands, automatic flashing or uploads.
All component identities are frozen in an explicit input manifest. Run under
the project's one-CPU/global-flock resource wrapper.
"""
from pathlib import Path
import argparse
import copy
import gzip
import hashlib
import json
import os
import stat
import struct
import sys
import time
import zlib

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / 'tools'), str(REPO / 'tools/boot_selector/twelve_model')]
from package_h700_v6a import constrained
from package_002 import (regular, sha, run, write_json, sparse_copy, range_sha,
                         debugfs, tree_inventory, tree_delta, metadata, install)
from patch_ramdisk import parse, emit
from rg35xxh_display import read_toc, TOC_OFFSET, TOC_BYTES, BOOT_OFFSET, BOOT_BYTES
from h700_shared_panel import toc_checksum
from h700_manual_selector_twelve import parts, align, kernel_commands
from h700_panel_boot import decode_env, ENV_OFFSET, ENV_SIZE
from models import ALL_MODEL_IDS, MODEL_METADATA
from verify_h700_navigation_test6 import metadata_inventory

NAME = 'ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test8_TwelveModel_20261116.img'
BASE = Path('/home/lpf/roc-os-h700-manual-selector-test7-20261116-v1/ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test7_BootHandoff_20261116.img')
BASE_SHA = '8f7ffefdf4c2437ece46462b21315ccba15b57926adef2fd46c3eb3fe2c647c4'
BASE_ACCEPTANCE = REPO / 'out/roc-os-h700-manual-selector-test7-20261116/acceptance.json'
BASE_ACCEPTANCE_SHA = '2e4714d91951b6f6dd46edb736b86adc9b50b2da5d5bfc71661ea2557de4acdb'
RAW_BYTES = 32434554368
RANGES = {'prefix': (0, 222298112), 'system': (222298112, 8589934592),
          'vendor': (8812232704, 2147483648), 'userdata': (10959716352, 21474836480),
          'backup_gpt': (32434552832, 1536)}
PARENT_RANGES = {'prefix': '3cf8eb9ea03ce7ce7902aec56911507bdbfc09549f533226ffe78494e9970807',
    'system': '6ab9b9423f2cf21f365d9e028d37f7311a678f220645cadbd7f1ba491a9ca59a',
    'vendor': 'bcf0706cd474b54b7f908aa234100a352773e0d603a11f4fa00787079e0f6fa0',
    'userdata': '637a02240df99491b9616503c69cd41638b7604c927675762e640014b3cd7d86',
    'backup_gpt': 'ba9ba2c16fbb57653f2d5b221bb2f0c2ee698550f1d9dc33df30b5565d23c5dc'}
LID = '/system/priv-app/ROCReleaseLid/ROCReleaseLid.apk'
DISPLAY_RC = '/system/etc/init/roc-model-display.rc'
MODULE = '/modules/h700_stick_axes.ko'
LOADER = '/bin/rgsp-stick-axes.sh'
SPACE_SHA = '847b55c93f1c0a36983ada5a500d4311b18022ef86b2db2aa3dc5614f0f400d6'


def check(value, reason):
    if not value:
        raise ValueError(reason)


def safe(path, *, fresh=False):
    path = Path(path)
    check(path.is_absolute() and '..' not in path.parts
          and (path.is_relative_to(Path('/home/lpf')) or path.is_relative_to(REPO)),
          'Ordinary workspace path required')
    check(all(not p.is_symlink() for p in (path, *path.parents)), 'Symlink path rejected')
    if fresh:
        check(not path.exists(), 'Fresh output required; preserve all prior attempts')
    return path


def inputs(manifest):
    manifest = regular(safe(manifest))
    result = json.loads(manifest.read_text())
    check(result['schema'] == 'roc.h700.twelve-model-inputs.v1', 'Input schema')
    required = {'module', 'input_receipt', 'early_helper', 'android_loader', 'menu',
                'menu_receipt', 'selector_hook', 'early_uboot', 'early_receipt',
                'kernel', 'panel_receipt', 'lid', 'lid_receipt', 'display_rc',
                'selector_receipt', 'boot_state', 'boot_state_receipt', 'native_start_receipt'}
    check(set(result['inputs']) == required, 'Incomplete/extra component set')
    paths = {}
    for key, row in result['inputs'].items():
        path = regular(safe(row['path']))
        check(sha(path) == row['sha256'], 'Component identity changed: ' + key)
        paths[key] = path
    receipts = {}
    for key in ('input_receipt', 'menu_receipt', 'early_receipt', 'panel_receipt',
                'lid_receipt', 'selector_receipt', 'boot_state_receipt', 'native_start_receipt'):
        receipt = json.loads(paths[key].read_text())
        check(receipt.get('passed', receipt.get('pass')) is True, 'Component failed: ' + key)
        receipts[key] = receipt
    inp = receipts['input_receipt']
    for name, value in inp['source_sha256'].items():
        check(sha(regular(REPO / 'tools/input_profiles' / name)) == value,
              'Validated input source changed: ' + name)
    check(inp['module_path'] == str(paths['module']) and
          inp['module_sha256'] == sha(paths['module']), 'Input module/receipt binding')
    for key in ('early_helper', 'android_loader'):
        check(inp['source_sha256'][paths[key].name] == sha(paths[key]),
              'Input loader/receipt binding: ' + key)
    check(receipts['menu_receipt']['sha256'][str(paths['menu'])] == sha(paths['menu']),
          'Menu/receipt binding')
    for name, value in receipts['menu_receipt']['sha256'].items():
        check(sha(regular(safe(name))) == value, 'Validated menu input changed: ' + name)
    check(receipts['menu_receipt'].get('manual_panel_recovery') is True and
          receipts['menu_receipt'].get('preview_exit_code') == 4 and
          receipts['menu_receipt'].get('preview_profiles') == 3 and
          receipts['menu_receipt'].get('volume_press_release_guard') is True,
          'Native menu must include the tested manual panel recovery path')
    helper = receipts['boot_state_receipt']
    check(helper['artifact'] == str(paths['boot_state']) and
          helper['artifact_sha256'] == sha(paths['boot_state']) and
          helper.get('preview_keeps_saved_default') is True and
          helper.get('preview_next_start') == '2',
          'Preview boot-state helper/receipt binding')
    for name, value in helper['controls'].items():
        check(sha(regular(safe(name))) == value, 'Validated helper control changed: ' + name)
    starts = receipts['native_start_receipt']
    check(starts.get('all12_actual_native_start') is True and
          starts.get('actual_host_and_aarch64') is True and
          starts.get('cases') == 24 and len(starts['rows']) == 24 and
          starts['controls'].get(str(paths['menu'])) == sha(paths['menu']) and
          starts['controls'].get(str(paths['menu_receipt'])) == sha(paths['menu_receipt']),
          'All twelve actual final native confirmations must be tested')
    start_cases = set()
    for row in starts['rows']:
        check(row['passed'] is True and row['all12_available_mask'] is True and
              row['script'] == 'DDA' and
              row['selected'] == {'schema': 2, 'model_id': row['model'], 'save_default': False},
              'Native confirmation case failed or rejected a catalog model')
        start_cases.add((row['model'], row['architecture']))
    check(start_cases == {(model, arch) for model in ALL_MODEL_IDS for arch in ('host', 'aarch64')},
          'Incomplete all-model final native start coverage')
    check(receipts['selector_receipt']['source'] == str(paths['selector_hook']) and
          receipts['selector_receipt']['source_sha256'] == sha(paths['selector_hook']),
          'Selector hook/receipt binding')
    early = receipts['early_receipt']
    check(early['patched_sha256'] == sha(paths['early_uboot']), 'Early U-Boot/receipt binding')
    check(early.get('manual_panel_recovery') is True and
          early.get('preview_next_start') == '2' and
          early.get('preview_returns_to_selector') is True,
          'Early preview selection must return to the model menu')
    panel = receipts['panel_receipt']['architectures']
    check(panel['kernel']['original_sha256'] ==
          '3328c2fab9f19f7ea6a80e34b0a76238cf594bc631f77e05fec32f8adabad042' and
          panel['uboot']['original_sha256'] ==
          'a11271e1276173cee48bd5705d068fd8446cfc0ffb43fca70b3b6808c2e9d0db',
          'Panel components must preserve the proven kernel/bootloader base')
    check(panel['kernel']['patched_sha256'] == sha(paths['kernel']), 'Kernel/panel receipt binding')
    check(early['input_dispatch']['sha256'] == panel['uboot']['patched_sha256'],
          'Early hook must extend the final twelve-profile panel dispatcher')
    check(sha(regular(safe(early['input_dispatch']['path']))) ==
          panel['uboot']['patched_sha256'], 'Panel U-Boot source changed')
    lid = receipts['lid_receipt']
    check(lid['artifact'] == str(paths['lid']) and lid['artifact_sha256'] == sha(paths['lid']) and
          lid['old_and_new_Android10_signature_verified'] is True and
          lid['platform_certificate_sha256'] ==
          'fc30e834b3c2914a0646d0b46c4faaa045aa8d46189950012555a5f2c36745c9',
          'Lid artifact/production signature binding')
    check(sha(BASE_ACCEPTANCE) == BASE_ACCEPTANCE_SHA, 'Parent offline acceptance changed')
    check(sha(REPO / 'docs/SPACE_REVIEW_20261028.md') == SPACE_SHA, 'Preservation record changed')
    controls = {str(manifest): sha(manifest), str(BASE_ACCEPTANCE): BASE_ACCEPTANCE_SHA,
                str(REPO / 'docs/SPACE_REVIEW_20261028.md'): SPACE_SHA}
    controls.update({str(path): sha(path) for path in paths.values()})
    for name, value in receipts['menu_receipt']['sha256'].items():
        controls[str(regular(safe(name)))] = value
    for key in ('early_receipt', 'panel_receipt', 'menu_receipt', 'selector_receipt',
                'boot_state_receipt', 'native_start_receipt'):
        for name, value in receipts[key].get('controls', {}).items():
            path = Path(name)
            if not path.is_absolute():
                path = REPO / path
            path = regular(safe(path))
            check(sha(path) == value, 'Validated component control changed: ' + str(path))
            controls[str(path)] = value
    for name, value in inp['proof_sha256'].items():
        path = regular(safe(REPO / name))
        check(sha(path) == value, 'Validated input proof changed: ' + name)
        controls[str(path)] = value
    for directory in ('tools/boot_selector/twelve_model', 'tools/input_profiles'):
        for path in (REPO / directory).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                controls[str(path)] = sha(regular(path))
    for name in ('package_h700_twelve_model.py', 'package_h700_twelve_model.ps1',
                 'verify_h700_twelve_model.py', 'h700_manual_selector_twelve.py'):
        path = Path(__file__).with_name(name)
        controls[str(path)] = sha(regular(path))
    for key in ('early_receipt', 'panel_receipt', 'lid_receipt', 'menu_receipt',
                'input_receipt', 'selector_receipt', 'boot_state_receipt', 'native_start_receipt'):
        controls[str(paths[key])] = sha(paths[key])
    controls[early['input_dispatch']['path']] = panel['uboot']['patched_sha256']
    for name in ('tools/package_h700_v6a.py', 'tools/patch_ramdisk.py',
                 'tools/release/package_002.py', 'tools/release/rg35xxh_display.py',
                 'tools/release/h700_shared_panel.py', 'tools/release/h700_panel_boot.py',
                 'tools/release/verify_h700_navigation_test6.py',
                 'tools/audit_rgsp_single_card_boot.py',
                 'tools/release/h700_panel_profiles.py', 'tools/release/verify_002.py',
                 'tools/release/verify_h700_manual_selector.py',
                 'tools/release/verify_h700_shared_panel.py',
                 'tools/boot_selector/reference_model.py', 'tools/boot_selector/boot_state.c'):
        path = regular(REPO / name)
        controls[str(path)] = sha(path)
    return paths, controls


def controls_match(controls):
    check(all(sha(regular(safe(name))) == value for name, value in controls.items()),
          'Frozen source/component changed during operation')


def copy_range(source, target, offset, length):
    with regular(safe(source)).open('rb') as reader, safe(target, fresh=True).open('xb') as writer:
        reader.seek(offset)
        left = length
        while left:
            block = reader.read(min(4 * 1024**2, left))
            check(block, 'Truncated parent range')
            if block.count(0) == len(block):
                writer.seek(len(block), os.SEEK_CUR)
            else:
                writer.write(block)
            left -= len(block)
        writer.truncate(length)
        writer.flush()
        os.fsync(writer.fileno())


def repack_ramdisk(original, replacements):
    old = parse(gzip.decompress(original))
    lookup = {row['name']: row for row in old}
    check(len(lookup) == len(old) and set(replacements) <= set(lookup), 'Ramdisk replacement set')
    after = copy.deepcopy(old)
    for row in after:
        if row['name'] in replacements:
            check(stat.S_ISREG(row['mode']) and row['nlink'] == 1, 'Unexpected ramdisk node kind')
            row['data'] = replacements[row['name']]
    data = gzip.compress(b''.join(emit(row) for row in after), compresslevel=6, mtime=0)
    result = parse(gzip.decompress(data))
    check(result == after, 'Ramdisk roundtrip')
    check([row['name'] for row in result] == [row['name'] for row in old], 'Ramdisk entry order')
    for left, right in zip(old, result):
        if left['name'] in replacements:
            check({k: v for k, v in left.items() if k != 'data'} ==
                  {k: v for k, v in right.items() if k != 'data'}, 'Ramdisk metadata changed')
        else:
            check(left == right, 'Unrelated ramdisk member changed')
    return data, {name: {'before_sha256': hashlib.sha256(lookup[name]['data']).hexdigest(),
                        'after_sha256': hashlib.sha256(value).hexdigest()}
                  for name, value in replacements.items()}


def prepare_prefix(parent, component):
    check(len(parent) == RANGES['prefix'][1]
          and hashlib.sha256(parent).hexdigest() == PARENT_RANGES['prefix'], 'Exact Test7 prefix')
    output = bytearray(parent)
    toc = read_toc(parent[TOC_OFFSET:TOC_OFFSET + TOC_BYTES])
    item = next(row for row in toc['items'] if row['name'] == 'u-boot')
    ustart, usize = TOC_OFFSET + item['offset'], item['bytes']
    uboot = component['early_uboot'].read_bytes()
    check(len(uboot) == usize == 1048576, 'U-Boot capacity')
    output[ustart:ustart + usize] = uboot
    before_boot = parent[BOOT_OFFSET:BOOT_OFFSET + BOOT_BYTES]
    old = parts(before_boot)
    kernel = component['kernel'].read_bytes()
    check(len(kernel) == old['kernel']['bytes'] == 17686536, 'Kernel size/ABI layout')
    rd, rd_report = repack_ramdisk(old['ramdisk']['data'], {
        'grow/roc-boot-selector': component['menu'].read_bytes(),
        'grow/roc-boot-state': component['boot_state'].read_bytes(),
        'grow/roc-selector-init.sh': component['selector_hook'].read_bytes(),
        'grow/h700-optional-axes.sh': component['early_helper'].read_bytes()})
    header = bytearray(before_boot[:2048])
    struct.pack_into('<I', header, 16, len(rd))
    boot = bytearray(header)
    for value in (kernel, rd, old['second']['data'], old['dtb']['data']):
        boot.extend(b'\0' * (align(len(boot)) - len(boot)))
        boot.extend(value)
    boot.extend(b'\0' * (align(len(boot)) - len(boot)))
    check(len(boot) < BOOT_BYTES, 'Boot partition overflow')
    boot.extend(b'\xff' * (BOOT_BYTES - len(boot)))
    new = parts(boot)
    check(new['second']['data'] == old['second']['data'] and new['dtb']['data'] == old['dtb']['data'],
          'Android DTB/second changed')
    output[BOOT_OFFSET:BOOT_OFFSET + BOOT_BYTES] = boot
    rows = decode_env(parent[ENV_OFFSET:ENV_OFFSET + ENV_SIZE])
    check(dict(rows)['roc_fdt_addr'] == 'fdt addr ${fdtcontroladdr}', 'Test7 handoff fix absent')
    commands = kernel_commands(new['dtb']['offset'])
    # The old three-model variables are owned by the selector; all unrelated
    # vendor environment entries and their order remain unchanged.
    kept = [(key, value) for key, value in rows if not key.startswith('roc_')]
    changed_rows = [(key, commands.get(key, value)) for key, value in kept]
    changed_rows += [(key, value) for key, value in commands.items() if key not in dict(kept)]
    check(len(changed_rows) < 256, 'Boot-state row capacity')
    body = b'\0'.join((key + '=' + value).encode('ascii') if key else b''
                      for key, value in changed_rows) + b'\0\0'
    check(len(body) < ENV_SIZE - 4, 'Environment capacity')
    body = body.ljust(ENV_SIZE - 4, b'\0')
    env = struct.pack('<I', zlib.crc32(body)) + body
    check(decode_env(env) == changed_rows, 'Environment roundtrip')
    output[ENV_OFFSET:ENV_OFFSET + ENV_SIZE] = env
    output = toc_checksum(output)
    windows = [(ustart, ustart + usize), (TOC_OFFSET + 20, TOC_OFFSET + 24),
               (ENV_OFFSET, ENV_OFFSET + ENV_SIZE), (BOOT_OFFSET, BOOT_OFFSET + BOOT_BYTES)]
    cursor = 0
    for start, end in sorted(windows):
        check(output[cursor:start] == parent[cursor:start], 'Unrelated prefix change')
        cursor = end
    check(output[cursor:] == parent[cursor:], 'Unexpected prefix suffix change')
    return output, {'ramdisk': rd_report, 'parent_init_byte_exact': True,
        'boot_state_helper_sha256': sha(component['boot_state']), 'Android_DTB_byte_exact': True,
        'uboot_sha256': hashlib.sha256(uboot).hexdigest(),
        'kernel_sha256': hashlib.sha256(kernel).hexdigest(),
        'kernel_dtb_offset': new['dtb']['offset'], 'environment': dict(changed_rows),
        'environment_rows': len(changed_rows), 'Test7_control_FDT_handoff_retained': True,
        'allowed_prefix_windows': windows}


def dump_tree(image, target):
    target.mkdir()
    debugfs(image, 'rdump / ' + str(target))
    rows = tree_inventory(target)
    check(rows, 'Empty filesystem dump')
    return rows


def fs_prepare(name, parent, target, work, replacements, additions):
    folder = work / (name + '-evidence')
    folder.mkdir()
    before = dump_tree(parent, folder / 'before')
    before_meta = metadata_inventory(parent, before, folder, 'before', lambda args, label: run(args))
    sparse_copy(parent, target)
    for path, local in replacements.items():
        check(path in before, 'Missing replacement: ' + path)
        install(target, local, path, metadata(parent, path), work, replace=True)
    for path, (local, template) in additions.items():
        check(path not in before, 'New path already exists')
        install(target, local, path, metadata(parent, template), work)
    run(['/usr/sbin/e2fsck', '-f', '-n', target])
    after = dump_tree(target, folder / 'after')
    delta = tree_delta(before, after)
    check(delta == {'added': sorted(additions), 'removed': [], 'changed': sorted(replacements)},
          'Unexpected filesystem payload delta: ' + str(delta))
    after_meta = metadata_inventory(target, after, folder, 'after', lambda args, label: run(args))
    for path in before:
        check(before_meta[path] == after_meta[path], 'Existing owner/mode/label changed: ' + path)
    for path, (local, template) in additions.items():
        check(after_meta[path] == before_meta[template], 'New metadata differs from template')
    for path, local in replacements.items():
        check(after[path]['sha256'] == sha(local), 'Actual installed payload mismatch')
    for path, (local, template) in additions.items():
        check(after[path]['sha256'] == sha(local), 'Actual installed added payload mismatch')
    write_json(folder / 'before-tree.json', before)
    write_json(folder / 'after-tree.json', after)
    write_json(folder / 'delta.json', delta)
    return {'delta': delta, 'sha256': sha(target), 'nodes': len(after),
            'original_owners_modes_labels_preserved': True,
            'before_tree_sha256': sha(folder / 'before-tree.json'),
            'after_tree_sha256': sha(folder / 'after-tree.json')}


def prepare(args):
    started = time.monotonic()
    components, controls = inputs(args.manifest)
    work, output = safe(args.work, fresh=True), safe(args.output, fresh=True)
    check(BASE.stat().st_size == RAW_BYTES and sha(BASE) == BASE_SHA, 'Exact complete Test7 parent')
    work.mkdir(parents=True)
    output.mkdir(parents=True)
    print('PHASE=prepare_twelve_model_boot_chain', flush=True)
    with BASE.open('rb') as reader:
        parent = reader.read(RANGES['prefix'][1])
    prefix, integration = prepare_prefix(parent, components)
    (work / 'prefix.raw').write_bytes(prefix)
    write_json(work / 'integration.json', integration)
    for name in ('system', 'vendor'):
        print('PHASE=prepare_' + name + '_ordinary_copy', flush=True)
        copy_range(BASE, work / (name + '.parent.raw'), *RANGES[name])
        check(sha(work / (name + '.parent.raw')) == PARENT_RANGES[name], 'Parent range mismatch')
    system = fs_prepare('system', work / 'system.parent.raw', work / 'system.raw', work,
        {LID: components['lid']}, {DISPLAY_RC: (components['display_rc'], '/system/etc/init/bootstat.rc')})
    vendor = fs_prepare('vendor', work / 'vendor.parent.raw', work / 'vendor.raw', work,
        {MODULE: components['module'], LOADER: components['android_loader']}, {})
    controls_match(controls)
    record = {'schema': 'roc.h700.twelve-model-preparation.v1', 'passed': True,
        'work': str(work), 'output': str(output), 'controls': controls,
        'inputs': {key: {'path': str(path), 'sha256': sha(path)} for key, path in components.items()},
        'prefix_sha256': sha(work / 'prefix.raw'), 'system': system, 'vendor': vendor,
        'integration_sha256': sha(work / 'integration.json'), 'models': MODEL_METADATA,
        'physical_card_written': False, 'all_H700_models_accepted': False,
        'elapsed_seconds': time.monotonic() - started}
    write_json(output / 'preparation.json', record)
    print('TWELVE_MODEL_PREPARATION_PASS', flush=True)


def package(args):
    started = time.monotonic()
    work, output = safe(args.work), safe(args.output)
    record = json.loads(regular(output / 'preparation.json').read_text())
    check(record['passed'] is True, 'Preparation did not pass')
    controls_match(record['controls'])
    proof_path = regular(output / 'final-handoff.json')
    proof_sha = sha(proof_path)
    proof = json.loads(proof_path.read_text())
    check(sha(work / 'integration.json') == record['integration_sha256'],
          'Prepared integration receipt changed')
    integration = json.loads(regular(work / 'integration.json').read_text())
    check(proof['schema'] == 'roc.test8.twelve-model-final-handoff.v1' and
          proof['passed'] is True and proof['positive_cases'] == 24 and
          proof['negative_cases'] == 2 and proof['kernel_boundaries'] == 52 and
          proof['inputs']['prefix_sha256'] == record['prefix_sha256'] and
          proof['inputs']['uboot_sha256'] == integration['uboot_sha256'] and
          proof['inputs']['boot_components']['kernel']['sha256'] == integration['kernel_sha256'],
          'Final twelve-model handoff proof must bind this exact prepared prefix')
    controls_match(proof['controls'])
    for name, expected in [('prefix', record['prefix_sha256']),
                           ('system', record['system']['sha256']), ('vendor', record['vendor']['sha256'])]:
        check(sha(work / (name + '.raw')) == expected, 'Prepared partition changed')
    raw, packed = work / NAME, output / (NAME + '.gz')
    safe(raw, fresh=True)
    safe(packed, fresh=True)
    check(sha(BASE) == BASE_SHA, 'Parent changed since preparation')
    print('PHASE=assemble_one_shared_twelve_model_image', flush=True)
    sparse_copy(BASE, raw)
    with raw.open('r+b') as writer, BASE.open('rb') as parent_reader:
        for name in ('prefix', 'system', 'vendor'):
            writer.seek(RANGES[name][0])
            parent_reader.seek(RANGES[name][0])
            with (work / (name + '.raw')).open('rb') as reader:
                while block := reader.read(4 * 1024**2):
                    original = parent_reader.read(len(block))
                    check(len(original) == len(block), 'Short parent during assembly')
                    if block == original:
                        writer.seek(len(block), os.SEEK_CUR)
                    else:
                        writer.write(block)
        writer.flush()
        os.fsync(writer.fileno())
    ranges = {}
    for name, (offset, size) in RANGES.items():
        value = range_sha(raw, offset, size)
        expected = (record['prefix_sha256'] if name == 'prefix' else record[name]['sha256']
                    if name in ('system', 'vendor') else PARENT_RANGES[name])
        check(value == expected, 'Unexpected whole-card range delta: ' + name)
        ranges[name] = {'offset': offset, 'bytes': size, 'sha256': value}
    print('PHASE=compress_complete_test8_image', flush=True)
    digest = hashlib.sha256()
    with raw.open('rb') as reader, packed.open('xb') as writer:
        with gzip.GzipFile(filename='', fileobj=writer, mode='wb', compresslevel=6, mtime=0) as stream:
            while block := reader.read(4 * 1024**2):
                digest.update(block)
                stream.write(block)
        writer.flush()
        os.fsync(writer.fileno())
    check(raw.stat().st_size == RAW_BYTES, 'Whole-card length')
    controls_match(record['controls'])
    check(sha(proof_path) == proof_sha, 'Final handoff proof changed during packaging')
    controls_match(proof['controls'])
    report = {'schema': 'roc.h700.twelve-model-image.v1', 'passed': True,
        'image': str(packed), 'bytes': packed.stat().st_size, 'sha256': sha(packed),
        'raw': str(raw), 'raw_bytes': RAW_BYTES, 'raw_sha256': digest.hexdigest(),
        'ranges': ranges, 'preparation_sha256': sha(output / 'preparation.json'),
        'final_handoff_sha256': proof_sha,
        'parent_raw_sha256': BASE_SHA, 'integrated_models': list(ALL_MODEL_IDS),
        'electrical_profiles': 10, 'ram_identity_gate': False,
        'manual_panel_recovery': True, 'preview_next_start': '2',
        'menu_preview_models': ['rg35xxh', 'rg34xxsp', 'rgcubexx'],
        'menu_visible_on_all_models_accepted': False,
        'all_H700_models_accepted': False, 'physical_card_written': False,
        'elapsed_seconds': time.monotonic() - started}
    write_json(output / 'image-result.json', report)
    (output / (NAME + '.gz.sha256')).write_text(report['sha256'] + '  ' + NAME + '.gz\n')
    print('TWELVE_MODEL_PACKAGE_PASS; INDEPENDENT_VERIFY_PENDING', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'package'))
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    constrained()
    (prepare if args.phase == 'prepare' else package)(args)

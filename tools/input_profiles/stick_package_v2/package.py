"""Prepare/package the bounded stick-sampling delta in an exact Test8 copy."""
from pathlib import Path
import argparse
import copy
import gzip
import hashlib
import json
import os
import re
import stat
import struct
import sys
import time

REPO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO / 'tools'), str(REPO / 'tools/release')]
from package_h700_v6a import constrained
from package_002 import (regular, sha, write_json, sparse_copy, range_sha,
                         debugfs, tree_inventory, tree_delta, metadata, install)
from patch_ramdisk import parse, emit
from verify_h700_navigation_test6 import metadata_inventory, parse_metadata

NAME = 'ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test9_StickSampling_20261117.img'
BASE = Path('/home/lpf/roc-os-h700-twelve-model-test8-20261116-v1/ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test8_TwelveModel_20261116.img')
BASE_SHA = '9350c2e9e8a15e0ead4c9db00e90f6da33a2ff7bdc4179863db3797a4ae19db0'
ACCEPTANCE = REPO / 'out/roc-os-h700-twelve-model-test8-20261116/acceptance.json'
ACCEPTANCE_SHA = '7105abaf1a36469c9499973ea97434cd57891b168c451bafd5ea7fa0ce1d8b26'
RAW_BYTES = 32434554368
BOOT_START, BOOT_BYTES = 155189248, 67108864
RANGES = {'prefix': (0, 222298112), 'system': (222298112, 8589934592),
          'vendor': (8812232704, 2147483648), 'userdata': (10959716352, 21474836480),
          'backup_gpt': (32434552832, 1536)}
PARENT = {'prefix': '1dac32f9a9a5b3a341f279dd46a2ccc111bdf9b184f1f4860f991f753cc148c8',
          'system': '0c78ac63b65afcd75ff9a872cea84e97c50de68edaf69dc46edefedb1decbcd6',
          'vendor': '04f97bdfa466935ea6fe9f599ea577cb69127d326be41886b4eafbe1e6f9cb21',
          'userdata': '637a02240df99491b9616503c69cd41638b7604c927675762e640014b3cd7d86',
          'backup_gpt': 'ba9ba2c16fbb57653f2d5b221bb2f0c2ee698550f1d9dc33df30b5565d23c5dc'}
KERNEL_SHA = '62c4feb1650f1c311e79ebfe75a979bac89f3da77f1ab6e46ad46a8924fdb6e6'
CPIO_HELPER = 'grow/h700-optional-axes.sh'
MODULE, LOADER = '/modules/h700_stick_axes.ko', '/bin/rgsp-stick-axes.sh'
REQUIRED = {'module', 'early_helper', 'android_loader'}


def check(value, reason):
    if not value:
        raise ValueError(reason)


def safe(path, fresh=False):
    path = Path(path)
    check(path.is_absolute() and '..' not in path.parts and
          (path.is_relative_to(REPO) or path.is_relative_to(Path('/home/lpf'))),
          'Absolute ordinary workspace path required: ' + str(path))
    check(not any(p.is_symlink() for p in (path, *path.parents)), 'Symlink path rejected')
    check(not any(c.isspace() for c in str(path)), 'Whitespace path rejected')
    if fresh:
        check(not path.exists(), 'Fresh output required; preserve prior attempts')
    return path


def frozen(row):
    check(set(row) == {'path', 'sha256'}, 'Frozen input fields')
    path = regular(safe(row['path']))
    check(sha(path) == row['sha256'], 'Frozen input changed: ' + str(path))
    return path


def controls_match(controls):
    check(controls and all(sha(regular(safe(name))) == value for name, value in controls.items()),
          'Frozen control changed')


def inputs(manifest):
    path = regular(safe(manifest))
    data = json.loads(path.read_text())
    check(set(data) == {'schema', 'inputs', 'candidate_receipt'} and
          data['schema'] == 'roc.h700.stick-sampling-inputs.v1' and
          set(data['inputs']) == REQUIRED, 'Input manifest schema/set')
    payloads = {key: frozen(row) for key, row in data['inputs'].items()}
    receipt_path = frozen(data['candidate_receipt'])
    receipt = json.loads(receipt_path.read_text())
    check(receipt['schema'] == 'roc.h700.stick-sampling-candidate.v2' and receipt['passed'] is True,
          'Passed new candidate receipt required')
    check(receipt['artifacts'] == data['inputs'] and receipt['module_path'] == str(payloads['module']) and
          receipt['module_sha256'] == sha(payloads['module']), 'Candidate artifact binding')
    check(receipt['physical_acceptance'] is False and receipt['no_RAM_identity_gate'] is True and
          receipt['catalog_models'] == 12, 'Candidate scope/identity protection')
    controls = dict(receipt['controls'])
    controls_match(controls)
    for target in payloads.values():
        check(controls.get(str(target)) == sha(target), 'Payload absent from candidate controls')
    proofs = receipt['proofs']
    check(set(proofs) == {'host', 'build', 'abi', 'kernel_binding', 'loaders'}, 'Proof set')
    proof = {}
    for key, row in proofs.items():
        target = frozen(row)
        proof[key] = json.loads(target.read_text())
        controls[str(target)] = sha(target)
    check(proof['host']['passed'] is True and proof['host']['actual_C_host_test'] is True and
          proof['host']['kernel_APIs_mocked'] is True and proof['host']['checks'] > 0 and
          proof['host']['scenarios'] > 0, 'Actual candidate host execution required')
    for key in ('build', 'loaders'):
        check(proof[key]['passed'] is True and proof[key]['module_sha256'] == sha(payloads['module']),
              'Build/loader proof module binding: ' + key)
    abi = proof['abi']
    check(abi['module_sha256'] == sha(payloads['module']) and abi['reference_crcs_matched'] >= 410 and
          abi['module_imports_matched'] >= 40 and abi['local_crcs_matched'] >= abi['module_imports_matched'],
          'Actual module ABI proof')
    binding = proof['kernel_binding']
    check(binding['actual_kernel_sha256'] == KERNEL_SHA and binding['export_crc_tables_equal'] is True and
          binding['relocation_region_equal'] is True and binding['all_export_names_equal'] is True,
          'Actual Test8 kernel ABI binding')
    for key in ('early_helper', 'android_loader'):
        check(sha(payloads['module']) in payloads[key].read_text(), 'Loader SHA does not pin candidate module')
    controls.update({str(target): sha(target) for target in payloads.values()})
    controls.update({str(path): sha(path), str(receipt_path): sha(receipt_path), str(ACCEPTANCE): ACCEPTANCE_SHA})
    for target in Path(__file__).parent.iterdir():
        if target.is_file():
            controls[str(target)] = sha(target)
    for name in ('tools/package_h700_v6a.py', 'tools/patch_ramdisk.py', 'tools/release/package_002.py',
                 'tools/release/verify_h700_navigation_test6.py', 'tools/release/verify_h700_twelve_model.py',
                 'tools/release/verify_002.py', 'tools/release/verify_h700_manual_selector.py',
                 'tools/release/verify_h700_shared_panel.py'):
        target = REPO / name
        controls[str(target)] = sha(target)
    check(sha(ACCEPTANCE) == ACCEPTANCE_SHA, 'Test8 acceptance changed')
    return payloads, controls


def boot_parts(boot):
    check(len(boot) == BOOT_BYTES and boot[:8] == b'ANDROID!', 'Parent boot structure')
    check(struct.unpack_from('<II', boot, 36) == (2048, 2), 'Parent boot page/header')
    result, offset = {}, 2048
    for name, field in [('kernel', 8), ('ramdisk', 16), ('second', 24), ('dtb', 1648)]:
        size = struct.unpack_from('<I', boot, field)[0]
        check(offset + size <= len(boot), 'Boot component bounds')
        result[name] = {'offset': offset, 'bytes': size, 'data': boot[offset:offset + size]}
        offset = (offset + size + 2047) & ~2047
    check(hashlib.sha256(result['kernel']['data']).hexdigest() == KERNEL_SHA, 'Exact Test8 kernel')
    return result


def prepare_prefix(parent, helper):
    check(len(parent) == RANGES['prefix'][1] and hashlib.sha256(parent).hexdigest() == PARENT['prefix'],
          'Exact Test8 parent prefix')
    boot = parent[BOOT_START:BOOT_START + BOOT_BYTES]
    parts = boot_parts(boot)
    old = parts['ramdisk']['data']
    entries = parse(gzip.decompress(old))
    check(len({e['name'] for e in entries}) == len(entries), 'Duplicate CPIO entry')
    match = [e for e in entries if e['name'] == CPIO_HELPER]
    check(len(match) == 1 and stat.S_ISREG(match[0]['mode']) and match[0]['nlink'] == 1,
          'Expected owned CPIO helper')
    updated = copy.deepcopy(entries)
    for entry in updated:
        if entry['name'] == CPIO_HELPER:
            check(entry['data'] != helper.read_bytes(), 'Helper payload must actually change')
            entry['data'] = helper.read_bytes()
    compressed = gzip.compress(b''.join(emit(e) for e in updated), compresslevel=9, mtime=0)
    check(len(compressed) <= len(old), 'Level9 ramdisk does not fit original length; no offsets may move')
    padded = compressed + bytes(len(old) - len(compressed))
    check(len(padded) == len(old) and parse(gzip.decompress(padded)) == updated, 'Zero-padded gzip roundtrip')
    for before, after in zip(entries, updated):
        check({k: v for k, v in before.items() if k != 'data'} ==
              {k: v for k, v in after.items() if k != 'data'}, 'CPIO metadata changed')
        check(before['name'] == CPIO_HELPER or before == after, 'Unrelated CPIO payload changed')
    offset = BOOT_START + parts['ramdisk']['offset']
    result = bytearray(parent)
    result[offset:offset + len(old)] = padded
    check(result[:offset] == parent[:offset] and result[offset + len(old):] == parent[offset + len(old):],
          'Prefix changed outside original ramdisk')
    return result, {'ramdisk_offset': offset, 'ramdisk_bytes': len(old),
                    'compressed_stream_bytes': len(compressed), 'zero_tail_bytes': len(old) - len(compressed),
                    'changed_CPIO_payloads': [CPIO_HELPER], 'boot_header_byte_exact': True,
                    'kernel_DTB_offsets_byte_exact': True, 'environment_UBoot_byte_exact': True}


def copy_range(source, target, offset, length):
    with regular(source).open('rb') as reader, safe(target, fresh=True).open('xb') as writer:
        reader.seek(offset)
        left = length
        while left:
            block = reader.read(min(left, 4 * 1024**2))
            check(block, 'Truncated image range')
            if block.count(0) == len(block):
                writer.seek(len(block), os.SEEK_CUR)
            else:
                writer.write(block)
            left -= len(block)
        writer.truncate(length)
        writer.flush()
        os.fsync(writer.fileno())


def inode_times(text):
    result = {m[1]: (int(m[2], 16), int(m[3] or '0', 16)) for m in re.finditer(
        r'^ ?(ctime|atime|mtime|crtime):\s+(0x[0-9a-f]+)(?::([0-9a-f]+))?', text, re.M)}
    check({'ctime', 'atime', 'mtime'} <= set(result), 'Incomplete inode timestamps')
    return result


def command(image, text, folder, label, writable=False):
    result = debugfs(image, text, writable)
    (folder / (label + '.txt')).write_text(result)
    return result


def vendor_prepare(parent, target, work, payloads):
    evidence = work / 'vendor-evidence'
    evidence.mkdir()
    before_root, after_root = evidence / 'before', evidence / 'after'
    before_root.mkdir()
    debugfs(parent, 'rdump / ' + str(before_root))
    before = tree_inventory(before_root)
    check(len(before) > 200 and {MODULE, LOADER} <= set(before), 'Complete Test8 vendor tree')
    def runner(argv, label):
        import subprocess
        result = subprocess.run(list(map(str, argv)), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        (evidence / (label + '.txt')).write_text(result.stdout)
        check(result.returncode == 0, 'Filesystem operation failed: ' + label)
        return result.stdout
    bm = metadata_inventory(parent, before, evidence, 'before', runner)
    parent_root = parse_metadata(debugfs(parent, 'stat /'), '/')
    sparse_copy(parent, target)
    for path, local in {MODULE: payloads['module'], LOADER: payloads['android_loader']}.items():
        old_times = inode_times(debugfs(parent, 'stat ' + path))
        install(target, local, path, metadata(parent, path), work, replace=True)
        for key, (seconds, extra) in old_times.items():
            debugfs(target, f'set_inode_field {path} {key} @{seconds}', True)
            debugfs(target, f'set_inode_field {path} {key}_extra 0x{extra:x}', True)
        check(inode_times(debugfs(target, 'stat ' + path)) == old_times, 'Replacement timestamps changed: ' + path)
    runner(['/usr/sbin/e2fsck', '-f', '-n', target], 'readonly-fsck')
    after_root.mkdir()
    debugfs(target, 'rdump / ' + str(after_root))
    after = tree_inventory(after_root)
    check(tree_delta(before, after) == {'added': [], 'removed': [], 'changed': sorted([MODULE, LOADER])},
          'Unexpected vendor tree payload delta')
    am = metadata_inventory(target, after, evidence, 'after', runner)
    check(bm == am and parse_metadata(debugfs(target, 'stat /'), '/') == parent_root,
          'Vendor owners/modes/SELinux labels changed')
    for path, local in {MODULE: payloads['module'], LOADER: payloads['android_loader']}.items():
        check(after[path]['sha256'] == sha(local), 'Actual vendor replacement mismatch')
    write_json(evidence / 'before-tree.json', before)
    write_json(evidence / 'after-tree.json', after)
    return {'sha256': sha(target), 'nodes': len(after), 'changed': sorted([MODULE, LOADER]),
            'all_existing_owners_modes_labels_preserved': True, 'replacement_timestamps_preserved': True}


def prepare(args):
    started = time.monotonic()
    payloads, controls = inputs(args.manifest)
    work, output = safe(args.work, True), safe(args.output, True)
    check(BASE.stat().st_size == RAW_BYTES and sha(BASE) == BASE_SHA, 'Exact complete Test8 parent')
    work.mkdir(parents=True)
    output.mkdir(parents=True)
    print('PHASE=prepare_fixed_offset_ramdisk', flush=True)
    with BASE.open('rb') as reader:
        prefix, integration = prepare_prefix(reader.read(RANGES['prefix'][1]), payloads['early_helper'])
    (work / 'prefix.raw').write_bytes(prefix)
    write_json(work / 'integration.json', integration)
    print('PHASE=prepare_vendor_two_payload_delta', flush=True)
    copy_range(BASE, work / 'vendor.parent.raw', *RANGES['vendor'])
    check(sha(work / 'vendor.parent.raw') == PARENT['vendor'], 'Test8 vendor identity')
    vendor = vendor_prepare(work / 'vendor.parent.raw', work / 'vendor.raw', work, payloads)
    controls_match(controls)
    record = {'schema': 'roc.h700.stick-sampling-preparation.v1', 'passed': True,
              'work': str(work), 'output': str(output), 'controls': controls,
              'inputs': {key: {'path': str(path), 'sha256': sha(path)} for key, path in payloads.items()},
              'manifest': str(args.manifest), 'manifest_sha256': sha(args.manifest),
              'prefix_sha256': sha(work / 'prefix.raw'), 'vendor': vendor,
              'integration_sha256': sha(work / 'integration.json'), 'parent_raw_sha256': BASE_SHA,
              'physical_input_accepted': False, 'elapsed_seconds': time.monotonic() - started}
    write_json(output / 'preparation.json', record)
    print('STICK_SAMPLING_PREPARATION_PASS', flush=True)


def package(args):
    started = time.monotonic()
    work, output = safe(args.work), safe(args.output)
    prep_path = regular(output / 'preparation.json')
    prep_sha = sha(prep_path)
    prep = json.loads(prep_path.read_text())
    check(prep['schema'] == 'roc.h700.stick-sampling-preparation.v1' and prep['passed'] is True,
          'Passed preparation required')
    check(prep['work'] == str(work) and prep['output'] == str(output), 'Foreign preparation')
    controls_match(prep['controls'])
    check(sha(work / 'integration.json') == prep['integration_sha256'], 'Integration changed')
    check(sha(BASE) == BASE_SHA, 'Test8 parent changed')
    for name, expected in [('prefix', prep['prefix_sha256']), ('vendor', prep['vendor']['sha256'])]:
        check(sha(work / (name + '.raw')) == expected, 'Prepared range changed: ' + name)
    raw, packed = safe(work / NAME, True), safe(output / (NAME + '.gz'), True)
    print('PHASE=assemble_shared_Test9', flush=True)
    sparse_copy(BASE, raw)
    with raw.open('r+b') as writer, BASE.open('rb') as parent:
        for name in ('prefix', 'vendor'):
            writer.seek(RANGES[name][0])
            parent.seek(RANGES[name][0])
            with (work / (name + '.raw')).open('rb') as reader:
                while block := reader.read(4 * 1024**2):
                    original = parent.read(len(block))
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
        expected = prep['prefix_sha256'] if name == 'prefix' else prep['vendor']['sha256'] if name == 'vendor' else PARENT[name]
        check(value == expected, 'Unexpected assembled range: ' + name)
        ranges[name] = {'offset': offset, 'bytes': size, 'sha256': value}
    print('PHASE=compress_complete_Test9', flush=True)
    digest = hashlib.sha256()
    with raw.open('rb') as reader, packed.open('xb') as writer:
        with gzip.GzipFile(filename='', fileobj=writer, mode='wb', compresslevel=6, mtime=0) as stream:
            while block := reader.read(4 * 1024**2):
                digest.update(block)
                stream.write(block)
        writer.flush()
        os.fsync(writer.fileno())
    controls_match(prep['controls'])
    check(sha(prep_path) == prep_sha, 'Preparation mutated during packaging')
    result = {'schema': 'roc.h700.stick-sampling-image.v1', 'passed': True,
              'image': str(packed), 'bytes': packed.stat().st_size, 'sha256': sha(packed),
              'raw': str(raw), 'raw_bytes': RAW_BYTES, 'raw_sha256': digest.hexdigest(),
              'ranges': ranges, 'preparation_sha256': prep_sha,
              'parent_raw_sha256': BASE_SHA, 'one_shared_twelve_model_image': True,
              'system_userdata_GPT_byte_exact': True, 'boot_component_offsets_byte_exact': True,
              'physical_input_accepted': False, 'all_H700_models_accepted': False,
              'physical_card_written': False, 'elapsed_seconds': time.monotonic() - started}
    write_json(output / 'image-result.json', result)
    (output / (NAME + '.gz.sha256')).write_text(result['sha256'] + '  ' + NAME + '.gz\n')
    print('STICK_SAMPLING_PACKAGE_PASS; INDEPENDENT_VERIFY_PENDING', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'package'))
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    check(args.phase != 'prepare' or args.manifest is not None, 'Prepare requires manifest')
    constrained()
    (prepare if args.phase == 'prepare' else package)(args)

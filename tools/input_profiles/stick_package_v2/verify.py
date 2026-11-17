"""Independently inspect the complete Test9 gzip and its fixed Test8 delta.

The Test9 producer is never imported. All inherited parsers are read-only
independent-verifier routines; their identities are locked with this verifier.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO / 'tools'), str(REPO / 'tools/release')]
from package_h700_v6a import constrained
from verify_h700_twelve_model import (stream, verify_gpt, boot_parts, cpio,
                                     verify_filesystem, ordinary)

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


def check(value, reason):
    if not value:
        raise ValueError(reason)


def sha(path):
    with ordinary(path).open('rb') as reader:
        return hashlib.file_digest(reader, 'sha256').hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def frozen(row):
    check(set(row) == {'path', 'sha256'}, 'Frozen input fields')
    path = ordinary(row['path'])
    check(sha(path) == row['sha256'], 'Frozen input changed: ' + str(path))
    return path


def controls_check(controls):
    check(controls and all(sha(name) == value for name, value in controls.items()), 'Frozen control changed')


def directory(path):
    path = Path(path)
    check(path.is_absolute() and '..' not in path.parts and
          (path.is_relative_to(REPO) or path.is_relative_to(Path('/home/lpf'))) and
          all(not p.is_symlink() for p in (path, *path.parents)) and path.is_dir(),
          'Ordinary workspace directory required: ' + str(path))
    return path


def receipt_check(manifest_path):
    manifest = json.loads(ordinary(manifest_path).read_text())
    check(set(manifest) == {'schema', 'inputs', 'candidate_receipt'} and
          manifest['schema'] == 'roc.h700.stick-sampling-inputs.v1' and
          set(manifest['inputs']) == {'module', 'early_helper', 'android_loader'}, 'Manifest schema/payload set')
    paths = {key: frozen(row) for key, row in manifest['inputs'].items()}
    candidate = json.loads(frozen(manifest['candidate_receipt']).read_text())
    check(candidate['schema'] == 'roc.h700.stick-sampling-candidate.v2' and candidate['passed'] is True and
          candidate['artifacts'] == manifest['inputs'] and candidate['module_path'] == str(paths['module']) and
          candidate['module_sha256'] == sha(paths['module']), 'Candidate/artifact receipt binding')
    check(candidate['physical_acceptance'] is False and candidate['no_RAM_identity_gate'] is True and
          candidate['catalog_models'] == 12, 'Candidate scope and identity policy')
    controls_check(candidate['controls'])
    for path in paths.values():
        check(candidate['controls'].get(str(path)) == sha(path), 'Payload missing from candidate controls')
    check(set(candidate['proofs']) == {'host', 'build', 'abi', 'kernel_binding', 'loaders'}, 'Candidate proof set')
    proofs = {key: json.loads(frozen(row).read_text()) for key, row in candidate['proofs'].items()}
    host = proofs['host']
    check(host['passed'] is True and host['actual_C_host_test'] is True and
          host['kernel_APIs_mocked'] is True and host['checks'] > 0 and host['scenarios'] > 0,
          'Actual host C execution missing')
    for name in ('build', 'loaders'):
        check(proofs[name]['passed'] is True and proofs[name]['module_sha256'] == sha(paths['module']),
              'Actual module/build/loader binding: ' + name)
    abi = proofs['abi']
    check(abi['module_sha256'] == sha(paths['module']) and abi['reference_crcs_matched'] >= 410 and
          abi['module_imports_matched'] >= 40 and abi['local_crcs_matched'] >= abi['module_imports_matched'],
          'Actual module CRC/ABI proof incomplete')
    binding = proofs['kernel_binding']
    check(binding['actual_kernel_sha256'] == KERNEL_SHA and binding['export_crc_tables_equal'] is True and
          binding['relocation_region_equal'] is True and binding['all_export_names_equal'] is True,
          'Exact Test8 kernel/export binding')
    for name in ('early_helper', 'android_loader'):
        check(sha(paths['module']) in paths[name].read_text(), 'Loader does not pin actual module SHA')
    return paths


def verify_prefix(before, after, helper):
    check(len(before) == len(after) == RANGES['prefix'][1] and
          hashlib.sha256(before).hexdigest() == PARENT['prefix'], 'Exact Test8 prefix')
    oldboot, newboot = before[BOOT_START:BOOT_START + BOOT_BYTES], after[BOOT_START:BOOT_START + BOOT_BYTES]
    old, new = boot_parts(oldboot), boot_parts(newboot)
    check(oldboot[:2048] == newboot[:2048], 'Android boot header must be completely identical')
    for key in old:
        check(old[key]['offset'] == new[key]['offset'] and old[key]['bytes'] == new[key]['bytes'],
              'Original component offset/size changed: ' + key)
        if key != 'ramdisk':
            check(old[key]['data'] == new[key]['data'], 'Boot component changed: ' + key)
    check(hashlib.sha256(new['kernel']['data']).hexdigest() == KERNEL_SHA, 'Exact inherited kernel')
    offset = BOOT_START + old['ramdisk']['offset']
    end = offset + old['ramdisk']['bytes']
    check(before[:offset] == after[:offset] and before[end:] == after[end:], 'Unexpected prefix change outside ramdisk')
    compressed = new['ramdisk']['data']
    check(compressed[:4] == b'\x1f\x8b\x08\0' and compressed[4:8] == bytes(4), 'Deterministic gzip flags/mtime')
    oldcpio, newcpio = cpio(gzip.decompress(old['ramdisk']['data'])), cpio(gzip.decompress(compressed))
    check([r['name'] for r in oldcpio] == [r['name'] for r in newcpio], 'CPIO topology/order changed')
    changed = []
    for a, b in zip(oldcpio, newcpio):
        fields = list(a['fields'])
        if a['name'] == CPIO_HELPER:
            check(b['data'] == helper.read_bytes() and a['data'] != b['data'], 'Actual CPIO helper replacement')
            fields[6] = len(b['data'])
            changed.append(a['name'])
        else:
            check(a['data'] == b['data'], 'Unrelated CPIO payload changed: ' + a['name'])
        check(fields == b['fields'], 'CPIO metadata changed: ' + a['name'])
    check(changed == [CPIO_HELPER], 'Expected exactly one CPIO payload replacement')
    return {'allowed_prefix_window': [offset, end], 'changed_CPIO_payloads': changed,
            'header_all_components_offsets_sizes_equal': True, 'kernel_AndroidDTB_second_byte_exact': True,
            'boot0_UBoot_TOC_environment_byte_exact': True, 'init_selector_busybox_byte_exact': True}


def time_inventory(text):
    rows = {}
    markers = list(re.finditer(r'^debugfs:\s+stat\s+(.+?)\s*$', text, re.M))
    for index, marker in enumerate(markers):
        name = json.loads(marker[1])
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        block = text[marker.end():end]
        values = {m[1]: (int(m[2], 16), int(m[3] or '0', 16)) for m in re.finditer(
            r'^ ?(ctime|atime|mtime|crtime):\s+(0x[0-9a-f]+)(?::([0-9a-f]+))?', block, re.M)}
        check({'ctime', 'atime', 'mtime'} <= set(values) and name not in rows, 'Timestamp inventory incomplete')
        rows[name] = values
    check(rows, 'Empty timestamp inventory')
    return rows


def main(args):
    constrained()
    started = time.monotonic()
    directory(args.work)
    directory(args.output)
    folder = args.work / 'independent-verification'
    target = args.output / 'independent-verify.json'
    check(not folder.exists() and not target.exists(), 'Fresh independent outputs required')
    folder.mkdir()
    report = {'schema': 'roc.h700.stick-sampling-independent.v1', 'passed': False, 'independent': True,
              'physical_input_accepted': False, 'all_H700_models_accepted': False,
              'device_accessed': False, 'images_modified': False}
    def run(argv, label):
        result = subprocess.run(list(map(str, argv)), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        logfile = folder / (label + '.txt')
        check(not logfile.exists(), 'Duplicate verification log')
        logfile.write_text(result.stdout)
        check(result.returncode == 0, 'Read-only command failed: ' + label + ': ' + result.stdout[-700:])
        return result.stdout
    try:
        check(sha(ACCEPTANCE) == ACCEPTANCE_SHA, 'Original Test8 acceptance changed')
        parent_acceptance = json.loads(ACCEPTANCE.read_text())
        check(parent_acceptance['offline_passed'] is True and parent_acceptance['image']['raw_sha256'] == BASE_SHA,
              'Parent acceptance semantic binding')
        prep_path, result_path = args.output / 'preparation.json', args.output / 'image-result.json'
        prep_sha, result_sha = sha(prep_path), sha(result_path)
        prep, result = json.loads(ordinary(prep_path).read_text()), json.loads(ordinary(result_path).read_text())
        check(prep['schema'] == 'roc.h700.stick-sampling-preparation.v1' and prep['passed'] is True and
              result['schema'] == 'roc.h700.stick-sampling-image.v1' and result['passed'] is True,
              'Passed preparation/image receipts required')
        check(prep['work'] == str(args.work) and prep['output'] == str(args.output) and
              result['preparation_sha256'] == prep_sha, 'Preparation binding')
        check(result['parent_raw_sha256'] == prep['parent_raw_sha256'] == BASE_SHA and
              result['physical_input_accepted'] is False and result['physical_card_written'] is False,
              'Parent/physical scope mismatch')
        controls_check(prep['controls'])
        manifest = ordinary(prep['manifest'])
        check(sha(manifest) == prep['manifest_sha256'] and prep['controls'].get(str(manifest)) == sha(manifest),
              'Frozen manifest missing')
        paths = receipt_check(manifest)
        check(prep['inputs'] == {k: {'path': str(v), 'sha256': sha(v)} for k, v in paths.items()},
              'Prepared manifest payload mismatch')
        check(sha(args.work / 'integration.json') == prep['integration_sha256'], 'Integration receipt changed')
        raw, packed = ordinary(result['raw']), ordinary(result['image'])
        check(raw == args.work / NAME and packed == args.output / (NAME + '.gz') and
              raw.stat().st_size == result['raw_bytes'] == RAW_BYTES and packed.stat().st_size == result['bytes'] and
              sha(packed) == result['sha256'], 'Delivered image identity/path')
        print('PHASE=independent_full_gzip_expansion_and_raw_comparison', flush=True)
        with gzip.open(packed, 'rb') as reader, raw.open('rb') as compare:
            actual = stream(reader, folder, 'actual', compare=compare, complete=True)
        check(actual['sha256'] == result['raw_sha256'], 'Actual complete raw SHA mismatch')
        print('PHASE=independent_complete_parent_read', flush=True)
        with ordinary(BASE).open('rb') as reader:
            parent = stream(reader, folder, 'parent')
        check(parent['sha256'] == BASE_SHA and parent['ranges'] == PARENT, 'Exact entire Test8 parent')
        check(set(result['ranges']) == set(RANGES) and all(result['ranges'][name] ==
              {'offset': offset, 'bytes': size, 'sha256': actual['ranges'][name]}
              for name, (offset, size) in RANGES.items()), 'All range report identities')
        for name in ('system', 'userdata', 'backup_gpt'):
            check(actual['ranges'][name] == PARENT[name], 'Protected range changed: ' + name)
        check(actual['ranges']['prefix'] == prep['prefix_sha256'] and
              actual['ranges']['vendor'] == prep['vendor']['sha256'], 'Prepared/actual partition mismatch')
        check(actual['head'][:8192] == parent['head'][:8192] and actual['tail'] == parent['tail'],
              'GPT/MBR bytes changed')
        report['GPT'] = verify_gpt(actual['head'], actual['tail'])
        before = (folder / 'parent.prefix.raw').read_bytes()
        after = (folder / 'actual.prefix.raw').read_bytes()
        report['prefix'] = verify_prefix(before, after, paths['early_helper'])
        print('PHASE=independent_complete_vendor_tree_and_metadata', flush=True)
        report['vendor'] = verify_filesystem('vendor', folder, paths, run)
        oldtimes = time_inventory((folder / 'vendor-before-all-metadata.txt').read_text())
        newtimes = time_inventory((folder / 'vendor-after-all-metadata.txt').read_text())
        check(oldtimes == newtimes, 'Vendor inode timestamps changed')
        root_before = time_inventory('debugfs: stat "/"\n' +
                                     (folder / 'vendor-before-root-stat.txt').read_text())
        root_after = time_inventory('debugfs: stat "/"\n' +
                                    (folder / 'vendor-after-root-stat.txt').read_text())
        check(root_before == root_after, 'Vendor root inode timestamps changed')
        report['vendor']['all_original_inode_timestamps_preserved'] = True
        controls_check(prep['controls'])
        check(sha(prep_path) == prep_sha and sha(result_path) == result_sha,
              'Producer receipts mutated during verification')
        report.update(passed=True, gzip_sha256=sha(packed), raw_sha256=actual['sha256'],
                      parent_raw_sha256=BASE_SHA, raw_bytes=RAW_BYTES,
                      producer_not_imported=True, complete_gzip_raw_byte_comparison=True,
                      all_original_CPIO_metadata_preserved=True,
                      Navigation18_framework_ART_Lid4_time_USB_security_byte_exact=True,
                      ranges=actual['ranges'], controls=prep['controls'],
                      elapsed_seconds=time.monotonic() - started)
    except BaseException as error:
        report.update(error=repr(error), elapsed_seconds=time.monotonic() - started)
        write_json(target, report)
        raise
    write_json(target, report)
    print('STICK_SAMPLING_INDEPENDENT_PASS; PHYSICAL_INPUT_ACCEPTANCE_PENDING', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args())

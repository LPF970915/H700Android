"""Independently verify the exact Test11 -> ROC OS 0.0.3 two-byte delta.

Run only under the existing low-pressure/global-lock wrapper. The producer is
never imported. All images are ordinary files; no device, mount, key or userdata
filesystem is opened. Only fresh verification files and a receipt are written.
"""
from pathlib import Path, PurePosixPath
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

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained
from verify_002 import verify_gpt

BASE_IMAGE = REPO / 'out/roc-os-h700-stick-adc-control-test11-20261117/ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test11_ADCControl_20261117.img.gz'
BASE_RAW = Path('/home/lpf/roc-os-h700-stick-adc-control-test11-20261117-v1/ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test11_ADCControl_20261117.img')
BASE_ACCEPTANCE = REPO / 'out/roc-os-h700-stick-adc-control-test11-20261117/acceptance.json'
BASE_GZIP_SHA = 'f78a8910ab46688fff862a69985db51a289550a13bdb839df38320c50e259dfe'
BASE_GZIP_BYTES = 591772828
BASE_RAW_SHA = '4998df90707eaab2d319bd77d6bf1ae4b262a598895338afafefe4d25704b43c'
BASE_ACCEPTANCE_SHA = '5946a9d78db74a79e7c0a104b1389af09010c5e0564af43b2dd0911eb2eab382'
RAW_BYTES = 32434554368
SYSTEM_OFFSET, SYSTEM_BYTES = 222298112, 8589934592
RANGES = {'prefix': (0, SYSTEM_OFFSET), 'system': (SYSTEM_OFFSET, SYSTEM_BYTES),
          'vendor': (8812232704, 2147483648), 'userdata': (10959716352, 21474836480),
          'backup_gpt': (32434552832, 1536)}
BASE_RANGES = {
    'prefix': 'bb7a8d1d2fb12ab284501b7aeb9ff3a57b7b9f12aff4a9db04529e9bcde484ac',
    'system': '0c78ac63b65afcd75ff9a872cea84e97c50de68edaf69dc46edefedb1decbcd6',
    'vendor': '68183115705bdf104ec78c6232d38dcdb81143bed9bc5d2ed9ad1762b027e430',
    'userdata': '637a02240df99491b9616503c69cd41638b7604c927675762e640014b3cd7d86',
    'backup_gpt': 'ba9ba2c16fbb57653f2d5b221bb2f0c2ee698550f1d9dc33df30b5565d23c5dc',
}
DEPENDENCIES = {
    'tools/package_h700_v6a.py': '60dc0136f0c04c16d1ffda2257f063a018f48232e1374bfee0505483425def71',
    'tools/release/verify_002.py': 'a737f350f8e8765b21105bc32ee497ef74f35ac6cea98d1c956caed88ab957a6',
}
PROPS = '/system/build.prop'
NAME = 'ROC_OS_ARM64_ver0.0.3.img.gz'


def check(value, reason):
    if not value:
        raise ValueError(reason)


def ordinary(path):
    path = Path(path)
    check(path.is_absolute() and '..' not in path.parts, 'Absolute canonical path required')
    check(not any(p.is_symlink() for p in (path, *path.parents)), 'Symlink path rejected')
    check(stat.S_ISREG(path.lstat().st_mode), 'Ordinary non-device file required: ' + str(path))
    return path


def directory(path):
    path = Path(path)
    check(path.is_absolute() and '..' not in path.parts, 'Absolute canonical directory required')
    check(not any(p.is_symlink() for p in (path, *path.parents)), 'Symlink directory rejected')
    check(path.is_dir(), 'Existing ordinary directory required: ' + str(path))
    return path


def sha(path):
    with ordinary(path).open('rb') as reader:
        return hashlib.file_digest(reader, 'sha256').hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sparse_write(writer, data):
    if data.count(0) == len(data):
        writer.seek(len(data), os.SEEK_CUR)
    else:
        writer.write(data)


def stream_compare(packed, parent_path, raw_path, folder):
    """Read every byte of gzip, exact parent and producer raw in one pass."""
    current_hash, parent_hash = hashlib.sha256(), hashlib.sha256()
    current_ranges = {name: hashlib.sha256() for name in RANGES}
    parent_ranges = {name: hashlib.sha256() for name in RANGES}
    total, differences, head, tail = 0, [], b'', b''
    with gzip.open(packed, 'rb') as current, parent_path.open('rb') as parent, \
            raw_path.open('rb') as raw, (folder / 'actual-system.raw').open('xb') as system, \
            (folder / 'parent-system.raw').open('xb') as parent_system:
        while block := current.read(4 * 1024**2):
            end = total + len(block)
            check(end <= RAW_BYTES, 'Expanded image exceeds exact card size')
            before, produced = parent.read(len(block)), raw.read(len(block))
            check(len(before) == len(block), 'Truncated parent raw')
            check(produced == block, 'Published gzip differs from actual producer raw')
            current_hash.update(block)
            parent_hash.update(before)
            if before != block:
                for index, (old, new) in enumerate(zip(before, block)):
                    if old != new:
                        check(len(differences) < 2, 'More than two raw bytes changed')
                        check(old == ord('2') and new == ord('3'), 'Non-version byte changed')
                        differences.append({'offset': total + index, 'before': old, 'after': new})
            if total < 1024**2:
                head += block[:min(len(block), 1024**2 - total)]
            tail = (tail + block)[-1536:]
            for name, (offset, size) in RANGES.items():
                lo, hi = max(total, offset), min(end, offset + size)
                if lo < hi:
                    section = block[lo - total:hi - total]
                    previous = before[lo - total:hi - total]
                    current_ranges[name].update(section)
                    parent_ranges[name].update(previous)
                    if name == 'system':
                        sparse_write(system, section)
                        sparse_write(parent_system, previous)
            total = end
        check(total == RAW_BYTES and not parent.read(1) and not raw.read(1), 'Exact raw size differs')
        check(len(differences) == 2, 'Expected exactly two version-byte changes')
        system.truncate(SYSTEM_BYTES)
        parent_system.truncate(SYSTEM_BYTES)
    return {'bytes': total, 'sha256': current_hash.hexdigest(), 'parent_sha256': parent_hash.hexdigest(),
            'ranges': {name: value.hexdigest() for name, value in current_ranges.items()},
            'parent_ranges': {name: value.hexdigest() for name, value in parent_ranges.items()},
            'differences': differences, 'head': head, 'tail': tail}


def property_check(folder, actual, parent, differences, run):
    before = run(['/usr/sbin/debugfs', '-R', 'cat ' + PROPS, parent], 'parent-build-prop', log=False)
    after = run(['/usr/sbin/debugfs', '-R', 'cat ' + PROPS, actual], 'actual-build-prop', log=False)
    check(before and len(before) == len(after), 'build.prop missing or length changed')
    fields = [('ro.build.display.id', b'ROC_OS_ARM64_ver0.0.2'), ('ro.roc.os.version', b'0.0.2')]
    expected, offsets = bytearray(before), []
    for key, old in fields:
        pattern = rb'^' + re.escape(key.encode()) + rb'=(.*)$'
        matches = list(re.finditer(pattern, before, re.M))
        check(len(matches) == 1 and matches[0][1] == old, 'Parent property differs/duplicates: ' + key)
        position = matches[0].end(1) - 1
        check(before[position] == ord('2'), 'Unexpected source version character')
        expected[position] = ord('3')
        offsets.append(position)
        current = re.findall(pattern, after, re.M)
        check(current == [old[:-1] + b'3'], 'Actual release property differs: ' + key)
    check(after == bytes(expected), 'build.prop changed beyond two reviewed version values')
    parent_stat = run(['/usr/sbin/debugfs', '-R', 'stat ' + PROPS, parent], 'parent-build-prop-stat')
    actual_stat = run(['/usr/sbin/debugfs', '-R', 'stat ' + PROPS, actual], 'actual-build-prop-stat')
    check(b'Inode:' in parent_stat and parent_stat == actual_stat,
          'build.prop inode, ownership, mode, xattr, extent or timestamps changed')
    stats = run(['/usr/sbin/debugfs', '-R', 'stats', actual], 'actual-system-stats')
    sizes = re.findall(rb'^Block size:\s+(\d+)\s*$', stats, re.M)
    check(len(sizes) == 1, 'Filesystem block size ambiguous')
    block_size = int(sizes[0])
    check(1024 <= block_size <= 65536 and block_size & (block_size - 1) == 0, 'Invalid ext4 block size')
    mappings = {}
    for logical in sorted({offset // block_size for offset in offsets}):
        command = f'bmap {PROPS} {logical}'
        first = run(['/usr/sbin/debugfs', '-R', command, parent], f'parent-bmap-{logical}')
        second = run(['/usr/sbin/debugfs', '-R', command, actual], f'actual-bmap-{logical}')
        check(re.fullmatch(rb'\s*[0-9]+\s*', first) and first == second, 'bmap differs or contains holes')
        physical = int(first)
        check(physical > 0 and (physical + 1) * block_size <= SYSTEM_BYTES, 'Invalid data-block mapping')
        mappings[logical] = physical
    declared = sorted(({'offset': SYSTEM_OFFSET + mappings[offset // block_size] * block_size + offset % block_size,
                        'before': ord('2'), 'after': ord('3')} for offset in offsets),
                      key=lambda row: row['offset'])
    check(differences == declared, 'Actual full-card changes do not map to the two version characters')
    run(['/usr/sbin/e2fsck', '-f', '-n', actual], 'actual-system-readonly-fsck')
    return {'path': PROPS, 'parent_sha256': hashlib.sha256(before).hexdigest(),
            'sha256': hashlib.sha256(after).hexdigest(), 'bytes': len(after),
            'properties': {'ro.build.display.id': 'ROC_OS_ARM64_ver0.0.3', 'ro.roc.os.version': '0.0.3'},
            'file_byte_offsets': offsets, 'ext4_block_size': block_size,
            'independent_bmap_offsets': declared, 'all_other_properties_byte_exact': True,
            'inode_metadata_and_extent_stat_byte_exact': True, 'readonly_fsck_passed': True}


def main(args):
    constrained()
    started = time.monotonic()
    directory(args.work)
    directory(args.output)
    folder, target = args.work / 'independent-verification', args.output / 'independent-verify.json'
    check(not folder.exists() and not target.exists(), 'Fresh independent outputs required; preserve earlier runs')
    folder.mkdir()
    report = {'schema': 'roc.h700.release-0.0.3.independent.v1', 'passed': False, 'version': '0.0.3',
              'independent': True, 'producer_imported': False, 'device_accessed': False,
              'images_modified': False, 'new_release_image_physically_tested': False,
              'all_H700_models_accepted': False}

    def run(argv, label, log=True):
        check(not any(any(c.isspace() for c in str(path)) for path in (argv[-1],)), 'Filesystem image path has whitespace')
        result = subprocess.run(list(map(str, argv)), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        check(result.returncode == 0, 'Read-only filesystem command failed: ' + label + ': ' +
              result.stderr.decode(errors='replace')[-600:])
        if log:
            logfile = folder / (label + '.txt')
            check(not logfile.exists(), 'Duplicate verification log')
            logfile.write_bytes(result.stdout)
        return result.stdout

    try:
        result_path = ordinary(args.output / 'image-result.json')
        input_lock = ordinary(args.output / 'input-lock.json')
        locks = {str(result_path): sha(result_path), str(Path(__file__)): sha(Path(__file__)),
                 str(BASE_ACCEPTANCE): sha(BASE_ACCEPTANCE), str(input_lock): sha(input_lock)}
        declared_controls = json.loads(input_lock.read_text())
        required_controls = {
            'tools/release/package_003.py', 'tools/release/verify_003.py',
            'tools/release/package_003.ps1', 'tools/release/check_003_source.py',
            'tools/release/package_002.py', 'tools/release/verify_002.py',
            'tools/package_h700_v6a.py', 'build-support/public/source-manifest.json',
            'build-support/public/overlay/device/roc/roc_os_release_candidate/release_properties.mk',
            'out/roc-os-h700-stick-adc-control-test11-20261117/acceptance.json',
        }
        check(isinstance(declared_controls, dict) and required_controls <= declared_controls.keys(),
              'Producer input lock omits a required source/producer/verifier control')
        for name, digest in declared_controls.items():
            path = PurePosixPath(name)
            check(name == path.as_posix() and not path.is_absolute() and '..' not in path.parts and
                  not any(c in name for c in '\\\n\r\0') and re.fullmatch('[0-9a-f]{64}', digest),
                  'Unsafe frozen input-lock entry')
            check(sha(REPO / name) == digest, 'Producer control changed: ' + name)
            locks[str(REPO / name)] = digest
        check(locks[str(BASE_ACCEPTANCE)] == BASE_ACCEPTANCE_SHA, 'Frozen Test11 acceptance differs')
        accepted = json.loads(BASE_ACCEPTANCE.read_text())
        check(accepted['offline_passed'] is True and accepted['image']['sha256'] == BASE_GZIP_SHA and
              accepted['image']['raw_sha256'] == BASE_RAW_SHA, 'Test11 acceptance identity differs')
        for name, digest in DEPENDENCIES.items():
            check(sha(REPO / name) == digest, 'Frozen verifier dependency differs: ' + name)
            locks[str(REPO / name)] = digest
        result = json.loads(result_path.read_text())
        check(result['schema'] == 'roc.h700.release003.package.v1' and result['passed'] is True and
              result['version'] == '0.0.3', 'Passed 0.0.3 producer result required')
        check(result['base_gzip_sha256'] == BASE_GZIP_SHA and result['base_raw_sha256'] == BASE_RAW_SHA and
              result['base_acceptance_sha256'] == BASE_ACCEPTANCE_SHA and
              result['source_manifest_sha256'] == declared_controls['build-support/public/source-manifest.json'],
              'Producer parent/source identity mismatch')
        check(result['fresh_0_0_3_card_boot_accepted'] is False and
              result['all_H700_models_accepted'] is False and result['physical_card_written'] is False,
              'Prior physical feedback must not imply fresh 0.0.3/all-model physical acceptance')
        image, raw = ordinary(result['image']), ordinary(result['raw'])
        base_image, base_raw = ordinary(args.base_image), ordinary(args.base_raw)
        check(image == args.output / NAME and image.stat().st_size == result['bytes'] and
              sha(image) == result['sha256'], 'Published 0.0.3 gzip identity differs')
        check(base_image.stat().st_size == BASE_GZIP_BYTES and sha(base_image) == BASE_GZIP_SHA,
              'Exact frozen Test11 gzip required')
        check(base_raw.stat().st_size == raw.stat().st_size == result['raw_bytes'] == RAW_BYTES,
              'Exact full raw lengths required')
        check(image != base_image and raw != base_raw, 'Release and parent images must be separate ordinary files')
        print('PHASE=independent_full_gzip_parent_and_producer_raw_comparison', flush=True)
        actual = stream_compare(image, base_raw, raw, folder)
        check(actual['parent_sha256'] == BASE_RAW_SHA and actual['parent_ranges'] == BASE_RANGES,
              'Exact complete Test11 parent required')
        check(actual['sha256'] == result['raw_sha256'], 'Actual full gzip raw SHA differs')
        check(set(result['ranges']) == set(RANGES) and all(result['ranges'][name] ==
              {'offset': offset, 'bytes': length, 'base_sha256': actual['parent_ranges'][name],
               'sha256': actual['ranges'][name]} for name, (offset, length) in RANGES.items()),
              'Producer partition ranges disagree with independent complete streams')
        check(result['changed_bytes'] == 2 and len(result['edits']) == 2 and
              all(set(row) == {'property', 'property_file_offset', 'image_offset', 'before', 'after'}
                  for row in result['edits']), 'Producer two-edit declaration differs')
        declared_edits = sorted(({'offset': row['image_offset'], 'before': row['before'], 'after': row['after']}
                                 for row in result['edits']), key=lambda row: row['offset'])
        check(declared_edits == actual['differences'], 'Producer edits disagree with actual two changed bytes')
        for name in RANGES:
            if name != 'system':
                check(actual['ranges'][name] == BASE_RANGES[name], 'Unrelated full-card range changed: ' + name)
        check(actual['ranges']['system'] != BASE_RANGES['system'], 'System version bytes unchanged')
        report['GPT'] = verify_gpt(actual['head'], actual['tail'])
        print('PHASE=independent_actual_ext4_properties_inode_and_readonly_fsck', flush=True)
        report['system'] = property_check(folder, folder / 'actual-system.raw', folder / 'parent-system.raw',
                                          actual['differences'], run)
        check({row['property']: row['property_file_offset'] for row in result['edits']} ==
              dict(zip(('ro.build.display.id', 'ro.roc.os.version'), report['system']['file_byte_offsets'])) and
              result['build_prop_before_sha256'] == report['system']['parent_sha256'] and
              result['build_prop_after_sha256'] == report['system']['sha256'],
              'Producer property offsets/content identity disagree with independently extracted files')
        check(all(sha(Path(name)) == digest for name, digest in locks.items()), 'Frozen verification input changed')
        check(sha(image) == result['sha256'] and sha(base_image) == BASE_GZIP_SHA,
              'Published or parent gzip changed during verification')
        report.update(passed=True, gzip_sha256=result['sha256'], gzip_bytes=result['bytes'],
                      raw_sha256=actual['sha256'], raw_bytes=RAW_BYTES, parent_raw_sha256=BASE_RAW_SHA,
                      parent_gzip_sha256=BASE_GZIP_SHA, parent_acceptance_sha256=BASE_ACCEPTANCE_SHA,
                      complete_gzip_parent_and_raw_byte_comparison=True, exactly_two_version_bytes_changed=True,
                      differences=actual['differences'], ranges=actual['ranges'],
                      all_boot_vendor_userdata_GPT_and_other_system_bytes_byte_exact=True,
                      controls=locks, elapsed_seconds=time.monotonic() - started)
    except BaseException as error:
        report.update(error=repr(error), elapsed_seconds=time.monotonic() - started)
        write_json(target, report)
        raise
    write_json(target, report)
    print('ROC_OS_003_INDEPENDENT_VERIFICATION_PASS', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--base-raw', type=Path, default=BASE_RAW)
    parser.add_argument('--base-image', type=Path, default=BASE_IMAGE)
    main(parser.parse_args())

#!/usr/bin/env python3
"""Build and read back the two-library H700 trigger-axis image."""

import argparse
import fcntl
import gzip
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained
from release.package_002 import extract_tree, install, metadata, sha, sparse_copy, tree_delta, write_json
from release.verify_002 import RANGES, RAW_BYTES, require, stream_ranges, verify_gpt

TEST12 = REPO / 'out/roc-os-h700-chinese-ime-20261118'
PARENT_SYSTEM = Path('/home/lpf/roc-h700-chinese-ime-20261118-v4/system.a-pinyin.raw')
PARENT_RAW = Path('/home/lpf/roc-h700-standard-a-test12-20261118-v1/parent.img')
PARENT_REPORT_SHA = 'bff3f360eabfe3ad7e70a6f8218d1aac421d4ef05047e1f30dddd416e0f67311'
SOURCE = REPO / 'build-support/public/overlay/frameworks/native/services/inputflinger/InputReader.cpp'
MANIFEST = REPO / 'build-support/public/source-manifest.json'
IMAGE_NAME = 'ROC_OS_ARM64_ver0.0.3_H700_Test13_GamepadTriggers_20261120.img.gz'
LIBRARIES = {'lib/libinputreader.so': 'ARM', 'lib64/libinputreader.so': 'AArch64'}
SYSTEM_OFFSET, SYSTEM_SIZE = RANGES['system']


def parent_receipt():
    path = TEST12 / 'verify-result.json'
    require(sha(path) == PARENT_REPORT_SHA, 'Test12 verification record changed')
    receipt = json.loads(path.read_text())
    require(receipt['passed'] and receipt['raw']['bytes'] == RAW_BYTES, 'Test12 parent was not verified')
    require(sha(PARENT_SYSTEM) == receipt['raw']['ranges']['system'], 'Test12 system out of sync')
    return receipt


def readelf(path, options):
    return subprocess.check_output(['/usr/bin/readelf', '--wide', options, path], text=True)


def abi(path, arch):
    elf_header = readelf(path, '--file-header')
    machine = re.search(r'^\s*Machine:\s*(.+)$', elf_header, re.M)
    require(machine and machine[1].strip() == arch, f'Wrong ELF machine for {path}')
    dynamic = readelf(path, '--dynamic')
    dependencies = sorted(re.findall(r'\((?:NEEDED|SONAME)\).*?\[([^\]]+)\]', dynamic))
    symbols = set()
    for line in readelf(path, '--dyn-syms').splitlines():
        fields = line.split()
        if len(fields) >= 8 and fields[0][:-1].isdigit() and fields[0].endswith(':'):
            _, _, size, kind, binding, visibility, section, name, *_ = fields
            symbols.add((name, kind, binding, visibility, section == 'UND', size if kind == 'OBJECT' else ''))
    require('libinputreader.so' in dependencies and len(symbols) > 100, f'Incomplete ELF audit: {path}')
    return dependencies, symbols


def audit_system(image, original, target, installed, output):
    result = subprocess.run(['/usr/sbin/e2fsck', '-f', '-n', image], check=True, capture_output=True)
    (output / (target.name + '-fsck.log')).write_bytes(result.stdout + result.stderr)
    delta = tree_delta(original, extract_tree(image, target))
    require(delta == {'added': [], 'removed': [], 'changed': sorted(installed)}, 'Unexpected system tree delta')
    for path, record in installed.items():
        require(sha(target / path.lstrip('/')) == record['sha256'], f'Payload mismatch: {path}')
        require(metadata(image, path) == record['metadata'], f'Metadata mismatch: {path}')


def package(args, parent):
    image = args.output / IMAGE_NAME
    baseline = args.work / 'test12-system'
    changed_system = args.work / 'test13-system.raw'
    expected_source = sha(SOURCE)
    require(sha(args.build / 'InputReader.cpp') == expected_source, 'Build source differs from the overlay')
    entry = next(record for record in json.loads(MANIFEST.read_text())['files']
                 if record['path'] == 'frameworks/native/services/inputflinger/InputReader.cpp')
    require(entry['sha256'] == expected_source, 'Source manifest pin mismatch')
    args.output.mkdir(parents=True, exist_ok=False)
    args.work.mkdir(parents=True, exist_ok=False)
    print('Checking ARM and AArch64 libraries and staging Test12 system', flush=True)
    original = extract_tree(PARENT_SYSTEM, baseline)
    sparse_copy(PARENT_SYSTEM, changed_system)
    installed = {}
    for relative, arch in LIBRARIES.items():
        path = '/system/' + relative
        before = baseline / path.lstrip('/')
        after = args.build / 'built' / relative
        require(abi(before, arch) == abi(after, arch), f'Dynamic ABI changed: {path}')
        old_hash, new_hash = sha(before), sha(after)
        require(old_hash != new_hash, f'Unchanged library: {path}')
        meta = metadata(changed_system, path)
        install(changed_system, after, path, meta, args.work, replace=True)
        installed[path] = {'sha256': new_hash, 'parent_sha256': old_hash, 'metadata': meta, 'arch': arch}
    audit_system(changed_system, original, args.work / 'test13-system', installed, args.output)
    print('Compressing test image', flush=True)
    partial = image.with_suffix('.gz.partial')
    chunk_size = 4 * 1024**2
    require(PARENT_RAW.stat().st_size == RAW_BYTES, 'Incorrect size of parent raw image')
    with PARENT_RAW.open('rb') as base, changed_system.open('rb') as system, partial.open('xb') as output:
        with gzip.GzipFile(filename='', fileobj=output, mode='wb', compresslevel=1, mtime=0) as writer:
            left = SYSTEM_OFFSET
            while left:
                data = base.read(min(chunk_size, left))
                require(data, 'Truncated raw prefix')
                writer.write(data)
                left -= len(data)
            shutil.copyfileobj(system, writer, chunk_size)
            base.seek(SYSTEM_OFFSET + SYSTEM_SIZE)
            shutil.copyfileobj(base, writer, chunk_size)
    partial.rename(image)
    write_json(args.output / 'image-result.json', {
        'passed': True, 'parent_gzip_sha256': parent['gzip_sha256'], 'source_sha256': expected_source,
        'source_manifest_sha256': sha(MANIFEST), 'system_sha256': sha(changed_system),
        'image_sha256': sha(image), 'image_bytes': image.stat().st_size, 'installed': installed,
    })


def verify(args, parent):
    image = args.output / IMAGE_NAME
    result = json.loads((args.output / 'image-result.json').read_text())
    require(result['passed'] and result['image_sha256'] == sha(image), 'Candidate gzip identity changed')
    require(result['parent_gzip_sha256'] == parent['gzip_sha256'], 'Wrong Test12 parent')
    require(result['source_sha256'] == sha(SOURCE) and result['source_manifest_sha256'] == sha(MANIFEST),
            'Source changed after packaging')
    system = args.work / 'test13-from-gzip.raw'
    print('Reading back every byte and verifying GPT, ext4 and installed payloads', flush=True)
    with gzip.open(image, 'rb') as reader:
        raw = stream_ranges(reader, {'system': system})
    gpt = verify_gpt(raw.pop('head'), raw.pop('tail'))
    expected = parent['raw']['ranges'] | {'system': result['system_sha256']}
    require(raw['ranges'] == expected, 'Candidate altered a range outside Test12 system')
    require(set(result['installed']) == {'/system/' + lib for lib in LIBRARIES}, 'Unexpected payload list')
    original = extract_tree(PARENT_SYSTEM, args.work / 'test12-readback-system')
    audit_system(system, original, args.work / 'test13-readback-system', result['installed'], args.output)
    write_json(args.output / 'verify-result.json', {
        'passed': True, 'candidate_only': True, 'runtime_verified': False,
        'image': image.name, 'image_sha256': result['image_sha256'], 'image_bytes': result['image_bytes'],
        'parent_gzip_sha256': parent['gzip_sha256'], 'raw': raw, 'gpt': gpt, 'installed': result['installed'],
    })
    print(f"Candidate SHA-256 {result['image_sha256']}", flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('package', 'verify', 'all'))
    parser.add_argument('--build', required=True, type=Path)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    constrained()
    lock_path = Path('/tmp/h700-android10-low-pressure.lock')
    if not lock_path.exists():
        subprocess.run(['/usr/sbin/runuser', '-u', 'lpf', '--', '/usr/bin/touch', lock_path], check=True)
    with lock_path.open('rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        parent = parent_receipt()
        if args.phase in ('package', 'all'):
            package(args, parent)
        if args.phase in ('verify', 'all'):
            verify(args, parent)

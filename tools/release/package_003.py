"""Promote exact, user-tested Test11 to 0.0.3 by changing two version bytes.

Only ordinary image files are used. No mounts, block devices or live devices.
Use package_003.ps1 for the required resource limits and global lock.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import time

from package_002 import regular, sparse_copy
from package_h700_v6a import constrained

REPO = Path(__file__).resolve().parents[2]
BASE_DIR = REPO / 'out/roc-os-h700-stick-adc-control-test11-20261117'
BASE_NAME = 'ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test11_ADCControl_20261117.img'
BASE_IMAGE = BASE_DIR / (BASE_NAME + '.gz')
BASE_RAW = Path('/home/lpf/roc-os-h700-stick-adc-control-test11-20261117-v1') / BASE_NAME
BASE_GZIP_SHA = 'f78a8910ab46688fff862a69985db51a289550a13bdb839df38320c50e259dfe'
BASE_RAW_SHA = '4998df90707eaab2d319bd77d6bf1ae4b262a598895338afafefe4d25704b43c'
BASE_ACCEPTANCE_SHA = '5946a9d78db74a79e7c0a104b1389af09010c5e0564af43b2dd0911eb2eab382'
RAW_BYTES = 32434554368
SYSTEM_OFFSET = 222298112
SYSTEM_BYTES = 8589934592
SYSTEM_SHA = '0c78ac63b65afcd75ff9a872cea84e97c50de68edaf69dc46edefedb1decbcd6'
PROPS = '/system/build.prop'
NAME = 'ROC_OS_ARM64_ver0.0.3.img'
CHUNK = 4 * 1024**2
RANGES = {'prefix': (0, SYSTEM_OFFSET), 'system': (SYSTEM_OFFSET, SYSTEM_BYTES),
          'vendor': (8812232704, 2147483648), 'userdata': (10959716352, 21474836480),
          'backup_gpt': (32434552832, 1536)}


def sha(path):
    with regular(path).open('rb') as reader:
        return hashlib.file_digest(reader, 'sha256').hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def command(argv):
    ran = subprocess.run(list(map(str, argv)), capture_output=True)
    require(ran.returncode == 0, str(argv[0]) + ' failed: ' + ran.stderr.decode(errors='replace')[-2000:])
    return ran.stdout


def fs(image, request):
    return command(['/usr/sbin/debugfs', '-R', request, regular(image)])


def system_copy(raw, output):
    with regular(raw).open('rb') as reader, output.open('xb') as writer:
        reader.seek(SYSTEM_OFFSET)
        remaining = SYSTEM_BYTES
        while remaining:
            body = reader.read(min(CHUNK, remaining))
            require(bool(body), 'Short system range')
            if body.count(0) == len(body):
                writer.seek(len(body), os.SEEK_CUR)
            else:
                writer.write(body)
            remaining -= len(body)
        writer.truncate(SYSTEM_BYTES)


def stream_identity(raw):
    digest = hashlib.sha256()
    ranges = {name: hashlib.sha256() for name in RANGES}
    total = 0
    with regular(raw).open('rb') as reader:
        while block := reader.read(CHUNK):
            digest.update(block)
            for name, (offset, length) in RANGES.items():
                lo, hi = max(total, offset), min(total + len(block), offset + length)
                if lo < hi:
                    ranges[name].update(block[lo-total:hi-total])
            total += len(block)
    require(total == RAW_BYTES, 'Whole card size differs')
    return digest.hexdigest(), {name: value.hexdigest() for name, value in ranges.items()}


def main(args):
    constrained()
    started = time.monotonic()
    require(not args.work.exists() and not args.output.exists(), 'Fresh work/output required; preserve earlier results')
    args.work.mkdir(parents=True)
    args.output.mkdir(parents=True)
    report = {'schema': 'roc.h700.release003.package.v1', 'version': '0.0.3', 'passed': False,
              'physical_card_written': False, 'device_accessed': False,
              'Android_full_rebuild_performed': False, 'all_H700_models_accepted': False,
              'fresh_0_0_3_card_boot_accepted': False}
    try:
        print('PHASE=verify_exact_Test11_parent_and_frozen_controls', flush=True)
        require(sha(args.base_image) == BASE_GZIP_SHA, 'Wrong Test11 gzip')
        require(sha(BASE_DIR / 'acceptance.json') == BASE_ACCEPTANCE_SHA, 'Wrong Test11 acceptance')
        parent_digest, parent_ranges = stream_identity(args.base_raw)
        require(parent_digest == BASE_RAW_SHA and parent_ranges['system'] == SYSTEM_SHA, 'Wrong Test11 raw')
        accepted = json.loads((BASE_DIR / 'acceptance.json').read_bytes())
        require(accepted['offline_passed'], 'Parent not accepted offline')
        controls = {}
        names = ['tools/release/package_003.py', 'tools/release/verify_003.py',
                 'tools/release/package_003.ps1', 'tools/release/check_003_source.py',
                 'tools/release/package_002.py', 'tools/release/verify_002.py',
                 'tools/package_h700_v6a.py', 'build-support/public/source-manifest.json',
                 'build-support/public/overlay/device/roc/roc_os_release_candidate/release_properties.mk',
                 'out/roc-os-h700-stick-adc-control-test11-20261117/acceptance.json']
        for name in names:
            controls[name] = sha(REPO / name)
        for name, digest in accepted['preserved_records'].items():
            require(sha(REPO / name) == digest, 'Protected record changed: ' + name)
            controls[name] = digest
        save(args.output / 'input-lock.json', controls)
        parent_system = args.work / 'system.parent.raw'
        system_copy(args.base_raw, parent_system)
        require(sha(parent_system) == SYSTEM_SHA, 'Extracted parent system differs')
        before = fs(parent_system, 'cat ' + PROPS)
        before_stat = fs(parent_system, 'stat ' + PROPS)
        (args.work / 'build.prop.before').write_bytes(before)
        block_size_text = command(['/usr/sbin/dumpe2fs', '-h', parent_system]).decode()
        block_size = int(re.search(r'^Block size:\s+(\d+)$', block_size_text, re.M)[1])
        require(block_size == 4096, 'Unexpected ext4 block size')
        replacement = before
        edits = []
        for old, new in [(b'ro.build.display.id=ROC_OS_ARM64_ver0.0.2', b'ro.build.display.id=ROC_OS_ARM64_ver0.0.3'),
                         (b'ro.roc.os.version=0.0.2', b'ro.roc.os.version=0.0.3')]:
            matches = list(re.finditer(rb'^' + re.escape(old) + rb'$', before, re.M))
            require(len(matches) == 1, 'Expected one exact parent property: ' + old.decode())
            pos = matches[0].end() - 1
            logical, within = divmod(pos, block_size)
            physical = int(fs(parent_system, f'bmap {PROPS} {logical}').strip())
            require(0 < physical * block_size < SYSTEM_BYTES, 'Invalid data block')
            with parent_system.open('rb') as reader:
                reader.seek(physical * block_size)
                mapped = reader.read(block_size)
            require(mapped[:min(block_size, len(before)-logical*block_size)] == before[logical*block_size:(logical+1)*block_size],
                    'File data block mapping differs')
            absolute = SYSTEM_OFFSET + physical * block_size + within
            edits.append({'property': old.split(b'=')[0].decode(), 'property_file_offset': pos,
                          'image_offset': absolute, 'before': 50, 'after': 51})
            replacement = replacement.replace(old, new)
        require(len(before) == len(replacement) and sum(a != b for a, b in zip(before, replacement)) == 2,
                'Expected exactly two property bytes')
        raw = args.work / NAME
        print('PHASE=copy_parent_and_apply_two_version_bytes', flush=True)
        sparse_copy(args.base_raw, raw)
        with raw.open('r+b') as writer:
            for edit in edits:
                writer.seek(edit['image_offset'])
                require(writer.read(1) == b'2', 'Parent raw property byte differs')
                writer.seek(edit['image_offset'])
                writer.write(b'3')
            writer.flush()
            os.fsync(writer.fileno())
        actual_system = args.work / 'system.003.raw'
        system_copy(raw, actual_system)
        require(fs(actual_system, 'cat ' + PROPS) == replacement, 'Actual image version readback differs')
        require(fs(actual_system, 'stat ' + PROPS) == before_stat, 'Property metadata changed')
        (args.work / 'build.prop.after').write_bytes(replacement)
        checked = subprocess.run(['/usr/sbin/e2fsck', '-f', '-n', actual_system], capture_output=True)
        (args.work / 'system-fsck.txt').write_bytes(checked.stdout + checked.stderr)
        require(checked.returncode == 0, 'Read-only system fsck failed')
        actual_digest, actual_ranges = stream_identity(raw)
        for name in RANGES:
            if name != 'system':
                require(parent_ranges[name] == actual_ranges[name], 'Non-system range changed: ' + name)
        print('PHASE=compress_release_0_0_3', flush=True)
        packed = args.output / (NAME + '.gz')
        with raw.open('rb') as reader, packed.open('xb') as writer:
            with gzip.GzipFile(filename='', fileobj=writer, mode='wb', mtime=0, compresslevel=6) as compressor:
                shutil.copyfileobj(reader, compressor, CHUNK)
            writer.flush()
            os.fsync(writer.fileno())
        require(sha(args.base_image) == BASE_GZIP_SHA, 'Parent gzip changed during package')
        for name, digest in controls.items():
            require(sha(REPO / name) == digest, 'Frozen input changed: ' + name)
        report.update(passed=True, image=str(packed), bytes=packed.stat().st_size, sha256=sha(packed),
                      raw=str(raw), raw_bytes=RAW_BYTES, raw_sha256=actual_digest,
                      base_gzip_sha256=BASE_GZIP_SHA, base_raw_sha256=BASE_RAW_SHA,
                      base_acceptance_sha256=BASE_ACCEPTANCE_SHA,
                      source_manifest_sha256=controls['build-support/public/source-manifest.json'],
                      edits=edits, changed_bytes=2, build_prop_before_sha256=hashlib.sha256(before).hexdigest(),
                      build_prop_after_sha256=hashlib.sha256(replacement).hexdigest(),
                      property_metadata_byte_exact=True, system_fsck_passed=True,
                      ranges={name: {'offset': offset, 'bytes': length, 'base_sha256': parent_ranges[name],
                                     'sha256': actual_ranges[name]} for name, (offset, length) in RANGES.items()},
                      elapsed_seconds=time.monotonic()-started)
        print(json.dumps({'passed': True, 'image': str(packed), 'sha256': report['sha256']}), flush=True)
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        save(args.output / 'image-result.json', report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-image', type=Path, default=BASE_IMAGE)
    parser.add_argument('--base-raw', type=Path, default=BASE_RAW)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args())

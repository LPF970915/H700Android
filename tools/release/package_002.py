"""Package the reviewed 0.0.2 delta into ordinary copies of exact 0.0.1 files."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained

BASE_GZIP_SHA = 'e72580e8c4e4afc8b08b50570ad6beebf46a435ee6e8b32b7a943f21786a6346'
BASE_RAW_SHA = '09935c4935ca579d6956388b2a3af509b4d6c4763e36a047091373a4218208e3'
BASE_SYSTEM_SHA = '5da9a675fea3c7804c3682394eaef712dab8e26fcb33d97464c08304e4a2ea80'
NAV_SHA = '780e5bc74af0ee375626628fd4e4970e77a8d10e78b4cfc21c339b8b25d6f4e5'
OLD_NAV_SHA = 'a5460ba1ad4956ca759797df561b19250110bc7626a351478c30d56492f0f5a6'
RAW_BYTES = 32434554368
SYSTEM_OFFSET = 222298112
SYSTEM_BYTES = 8589934592
RANGES = {
    'prefix': (0, SYSTEM_OFFSET),
    'system': (SYSTEM_OFFSET, SYSTEM_BYTES),
    'vendor': (8812232704, 2147483648),
    'userdata': (10959716352, 21474836480),
    'backup_gpt': (32434552832, 1536),
}
NAV = '/system/app/ROCNavigation/ROCNavigation.apk'
PROPS = '/system/build.prop'
OVERLAY = '/system/product/overlay/ROCTimeDefaults.apk'
REMOVED = [
    '/system/app/ROCNavigation/oat/arm64/ROCNavigation.odex',
    '/system/app/ROCNavigation/oat/arm64/ROCNavigation.vdex',
]
ADDED = [OVERLAY]
PLATFORM_CERT = 'fc30e834b3c2914a0646d0b46c4faaa045aa8d46189950012555a5f2c36745c9'


def regular(path):
    path = Path(path)
    if path.is_symlink() or not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError('Ordinary non-symlink file required: ' + str(path))
    return path


def sha(path):
    with regular(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def run(argv):
    result = subprocess.run(list(map(str, argv)), capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f'{argv[0]} failed ({result.returncode}): {result.stdout[-2500:]} {result.stderr[-2500:]}')
    return result.stdout


def debugfs(image, command, writable=False):
    return run(['/usr/sbin/debugfs', *(['-w'] if writable else []), '-R', command, regular(image)])


def sparse_copy(source, target):
    # SEEK_DATA is optional; the fallback still preserves zero extents sparsely.
    import errno
    with regular(source).open('rb') as reader, Path(target).open('xb') as writer:
        size = source.stat().st_size
        try:
            offset = 0
            while offset < size:
                try:
                    data = os.lseek(reader.fileno(), offset, os.SEEK_DATA)
                except OSError as error:
                    if error.errno == errno.ENXIO:
                        break
                    raise
                hole = min(os.lseek(reader.fileno(), data, os.SEEK_HOLE), size)
                reader.seek(data)
                writer.seek(data)
                remaining = hole - data
                while remaining:
                    block = reader.read(min(4 * 1024**2, remaining))
                    if not block:
                        raise ValueError('Short source')
                    writer.write(block)
                    remaining -= len(block)
                offset = hole
        except OSError as error:
            if error.errno not in (errno.EINVAL, errno.ENOTSUP):
                raise
            reader.seek(0)
            writer.seek(0)
            while block := reader.read(4 * 1024**2):
                if block.count(0) == len(block):
                    writer.seek(len(block), os.SEEK_CUR)
                else:
                    writer.write(block)
        writer.truncate(size)
        writer.flush()
        os.fsync(writer.fileno())


def range_sha(path, offset, length):
    digest = hashlib.sha256()
    with regular(path).open('rb') as stream:
        stream.seek(offset)
        while length:
            block = stream.read(min(4 * 1024**2, length))
            if not block:
                raise ValueError('Short image range')
            digest.update(block)
            length -= len(block)
    return digest.hexdigest()


def tree_inventory(directory):
    rows = {}
    # Never follow rootfs links into the host filesystem.
    def visit(root):
        for path in sorted(root.iterdir()):
            info = path.lstat()
            name = '/' + path.relative_to(directory).as_posix()
            row = {'mode': oct(stat.S_IMODE(info.st_mode))}
            if stat.S_ISLNK(info.st_mode):
                row.update(kind='link', target=os.readlink(path))
            elif stat.S_ISDIR(info.st_mode):
                row['kind'] = 'directory'
                visit(path)
            elif stat.S_ISREG(info.st_mode):
                row.update(kind='file', bytes=info.st_size, sha256=sha(path))
            else:
                raise ValueError('Unexpected rootfs special node: ' + name)
            rows[name] = row
    visit(directory)
    return rows


def extract_tree(image, target):
    target.mkdir()
    debugfs(image, f'rdump / {target}')
    result = tree_inventory(target)
    if len(result) < 3000 or NAV not in result:
        raise ValueError('Incomplete filesystem extraction')
    return result


def tree_delta(before, after):
    return {
        'added': sorted(after.keys() - before.keys()),
        'removed': sorted(before.keys() - after.keys()),
        'changed': sorted(name for name in before.keys() & after.keys() if before[name] != after[name]),
    }


def metadata(image, name):
    output = debugfs(image, f'stat {name}')
    mode = re.search(r'Type: (\w+)\s+Mode:\s+([0-7]+)', output)
    owner = re.search(r'User:\s+(\d+)\s+Group:\s+(\d+)', output)
    label = re.search(r'security.selinux.*?= "([^"\\]+)', output)
    if not (mode and owner and label):
        raise ValueError('Incomplete ext4 metadata: ' + name)
    return {'kind': mode[1], 'mode': mode[2], 'uid': int(owner[1]), 'gid': int(owner[2]), 'selinux': label[1]}


def install(image, local, name, meta, work, replace=False):
    if replace:
        debugfs(image, 'rm ' + name, True)
    debugfs(image, f'write {regular(local)} {name}', True)
    mode = ('010' if meta['kind'] == 'regular' else '004') + meta['mode']
    for field, value in [('mode', mode), ('uid', str(meta['uid'])), ('gid', str(meta['gid']))]:
        debugfs(image, f'set_inode_field {name} {field} {value}', True)
    label = work / 'selinux-label.bin'
    label.write_bytes(meta['selinux'].encode() + b'\0')
    debugfs(image, f'ea_set -f {label} {name} security.selinux', True)
    if metadata(image, name) != meta:
        raise ValueError('Installed metadata mismatch: ' + name)


def main(args):
    constrained()
    started = time.monotonic()
    for path in (args.base_image, args.base_raw, args.base_system, args.navigation, args.time_receipt):
        regular(path)
        if any(char.isspace() for char in str(path)):
            raise ValueError('Paths with whitespace are unsupported')
    if args.work.exists() or args.output.exists():
        raise ValueError('Fresh work and publication directories required; preserve failed outputs')
    args.work.mkdir(parents=True)
    args.output.mkdir(parents=True)
    report = {'schema': 1, 'version': '0.0.2', 'passed': False, 'physical_card_written': False,
              'runtime_fresh_boot_tested': False, 'all_H700_models_accepted': False}
    try:
        print('PHASE=verify_exact_0.0.1_inputs', flush=True)
        assert sha(args.base_image) == BASE_GZIP_SHA
        assert args.base_raw.stat().st_size == RAW_BYTES and sha(args.base_raw) == BASE_RAW_SHA
        assert sha(args.base_system) == BASE_SYSTEM_SHA
        assert range_sha(args.base_raw, SYSTEM_OFFSET, SYSTEM_BYTES) == BASE_SYSTEM_SHA
        assert sha(args.navigation) == NAV_SHA
        time_result = json.loads(args.time_receipt.read_text())
        assert time_result['passed'] is True
        assert time_result['image_install_path'] == OVERLAY
        assert time_result['platform_certificate_sha256'] == PLATFORM_CERT
        assert time_result['idmap_overlayable_checks_enforced'] is True
        assert time_result['idmap_lookup'] == "cookie=1 config='' value=ntp.aliyun.com"
        overlay = regular(Path(time_result['artifact']))
        assert sha(overlay) == time_result['artifact_sha256']
        manifest = REPO / 'build-support/public/source-manifest.json'
        controls = {str(path): sha(path) for path in
                    [args.navigation, overlay, args.time_receipt, manifest, Path(__file__)]}
        write_json(args.work / 'input-lock.json', controls)
        before = extract_tree(args.base_system, args.work / 'before-tree')
        assert before[NAV]['sha256'] == OLD_NAV_SHA
        assert not set(ADDED) & before.keys()
        assert all(path in before for path in REMOVED)
        write_json(args.work / 'before-filesystem.json', before)
        system = args.work / 'system.002.raw'
        sparse_copy(args.base_system, system)
        print('PHASE=apply_reviewed_system_delta', flush=True)
        nav_meta, prop_meta = metadata(args.base_system, NAV), metadata(args.base_system, PROPS)
        install(system, args.navigation, NAV, nav_meta, args.work, True)
        for path in REMOVED:
            debugfs(system, 'rm ' + path, True)
        old_props = (args.work / 'before-tree/system/build.prop').read_text()
        assert re.findall(r'^ro.build.display.id=(.*)$', old_props, re.M) == ['QP1A.191105.004 dev-keys']
        assert not re.search(r'^ro.roc.os.version=', old_props, re.M)
        new_props = re.sub(r'^ro.build.display.id=.*$', 'ro.build.display.id=ROC_OS_ARM64_ver0.0.2', old_props, flags=re.M)
        new_props += '\n# ROC OS image release version\nro.roc.os.version=0.0.2\n'
        prop_file = args.work / 'build.prop'
        prop_file.write_text(new_props, encoding='utf-8', newline='\n')
        install(system, prop_file, PROPS, prop_meta, args.work, True)
        for path in ADDED[:-1]:
            debugfs(system, 'mkdir ' + path, True)
            for field, value in [('mode', '040755'), ('uid', '0'), ('gid', '0')]:
                debugfs(system, f'set_inode_field {path} {field} {value}', True)
            label = args.work / 'selinux-label.bin'
            label.write_bytes(b'u:object_r:vendor_overlay_file:s0\0')
            debugfs(system, f'ea_set -f {label} {path} security.selinux', True)
            assert metadata(system, path) == {'kind': 'directory', 'mode': '0755', 'uid': 0, 'gid': 0, 'selinux': 'u:object_r:vendor_overlay_file:s0'}
        overlay_meta = {'kind': 'regular', 'mode': '0644', 'uid': 0, 'gid': 0, 'selinux': 'u:object_r:vendor_overlay_file:s0'}
        install(system, overlay, OVERLAY, overlay_meta, args.work)
        run(['/usr/sbin/e2fsck', '-f', '-n', system])
        after = extract_tree(system, args.work / 'after-tree')
        delta = tree_delta(before, after)
        expected = {'added': sorted(ADDED), 'removed': sorted(REMOVED), 'changed': sorted([NAV, PROPS])}
        assert delta == expected, delta
        assert after[NAV]['sha256'] == NAV_SHA and after[OVERLAY]['sha256'] == sha(overlay)
        write_json(args.work / 'after-filesystem.json', after)
        write_json(args.work / 'filesystem-delta.json', delta)
        print('PHASE=assemble_and_verify_card_ranges', flush=True)
        raw = args.work / 'ROC_OS_ARM64_ver0.0.2.img'
        sparse_copy(args.base_raw, raw)
        with raw.open('r+b') as writer, system.open('rb') as reader:
            writer.seek(SYSTEM_OFFSET)
            shutil.copyfileobj(reader, writer, 4 * 1024**2)
            writer.flush()
            os.fsync(writer.fileno())
        ranges = {}
        for name, (offset, length) in RANGES.items():
            parent, current = range_sha(args.base_raw, offset, length), range_sha(raw, offset, length)
            if name != 'system':
                assert parent == current, name
            else:
                assert current == sha(system)
            ranges[name] = {'offset': offset, 'bytes': length, 'base_sha256': parent, 'sha256': current}
        assert raw.stat().st_size == RAW_BYTES
        print('PHASE=compress_and_read_back_full_image', flush=True)
        packed = args.output / (raw.name + '.gz')
        with raw.open('rb') as reader, packed.open('xb') as writer:
            with gzip.GzipFile(filename='', fileobj=writer, mode='wb', mtime=0, compresslevel=6) as stream:
                shutil.copyfileobj(reader, stream, 4 * 1024**2)
            writer.flush()
            os.fsync(writer.fileno())
        raw_hash = sha(raw)
        with gzip.open(packed, 'rb') as reader:
            digest = hashlib.file_digest(reader, 'sha256').hexdigest()
        assert digest == raw_hash
        assert all(sha(Path(path)) == value for path, value in controls.items())
        report.update(passed=True, image=str(packed), bytes=packed.stat().st_size, sha256=sha(packed),
                      raw=str(raw), raw_bytes=RAW_BYTES, raw_sha256=raw_hash, system=str(system),
                      work=str(args.work), base_gzip_sha256=BASE_GZIP_SHA, base_raw_sha256=BASE_RAW_SHA,
                      navigation_sha256=NAV_SHA, time_defaults_sha256=sha(overlay),
                      time_defaults_receipt=str(args.time_receipt), source_manifest_sha256=sha(manifest),
                      ranges=ranges, filesystem_delta=delta, old_preopt_files_removed=True,
                      boot_vendor_userdata_security_unchanged=True, Android_full_rebuild_performed=False,
                      existing_signing_identity=PLATFORM_CERT, elapsed_seconds=time.monotonic() - started)
        print(json.dumps({'passed': True, 'image': str(packed), 'sha256': report['sha256']}), flush=True)
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        write_json(args.output / 'image-result.json', report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('base-image', 'base-raw', 'base-system', 'navigation', 'time-receipt', 'work', 'output'):
        parser.add_argument('--' + key, type=Path, required=True)
    main(parser.parse_args())

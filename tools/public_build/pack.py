#!/usr/bin/env python3
"""Assemble a regular image file from rebuilt partitions and pinned boot assets."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import os
import stat
import struct
import sys
from common import REPO, copy_sparse, load, regular, require_hash, require_manifest_binding, run, sha, write_json
sys.path.insert(0, str(REPO / 'tools'))
from android_bootimg import read_header, component_offsets, pack as pack_boot
from android_sparse_to_raw import convert
from patch_ramdisk import parse, emit


def expand(source, target, expected_size):
    source = regular(source)
    if target.exists():
        raise ValueError('Refuse overwriting an expanded partition')
    with source.open('rb') as stream:
        magic = stream.read(4)
    if magic == struct.pack('<I', 0xED26FF3A):
        convert(str(source), str(target))
    else:
        with target.open('xb') as dest:
            copy_sparse(source, dest)
            dest.truncate(source.stat().st_size)
    if target.stat().st_size != expected_size:
        raise ValueError(f'Wrong expanded partition size: {source}')
    run(['e2fsck', '-f', '-n', target])
    return target


def check_properties(system, work):
    values = {}
    for index, name in enumerate(['/system/etc/prop.default', '/prop.default', '/default.prop', '/system/build.prop']):
        dest = work / f'properties-{index}.txt'
        run(['debugfs', '-R', f'dump {name} {dest}', system])
        if dest.is_file():
            for line in dest.read_text(errors='replace').splitlines():
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    values.setdefault(key, value)
    for key, value in {'ro.build.type': 'user', 'ro.secure': '1', 'ro.adb.secure': '1', 'ro.debuggable': '0'}.items():
        if values.get(key) != value:
            raise ValueError(f'Built system does not satisfy {key}={value}')


def boot_prefix(inputs, system, work):
    spec = load('external-inputs.json')['reference_image']
    base = require_hash(inputs / 'prefix.raw', spec['ranges']['prefix']['sha256'])
    data = bytearray(base.read_bytes())
    start, length = spec['boot']['offset'], spec['boot']['bytes']
    template = work / 'boot-template.raw'
    template.write_bytes(data[start:start+length])
    _, header = read_header(template)
    offsets = component_offsets(header)
    original = template.read_bytes()
    entries = parse(gzip.decompress(original[offsets['ramdisk']:offsets['ramdisk']+header['ramdisk_size']]))
    old = {e['name']: e for e in entries}
    replacements = {}
    for name in ['roc-grow-userdata-gpt', 'e2fsck_static', 'roc-resize2fs-static']:
        dest = work / name
        run(['debugfs', '-R', f'dump /system/bin/{name} {dest}', system])
        dest.chmod(0o755)
        body = regular(dest).read_bytes()
        if body[:6] != b'\x7fELF\x02\x01' or int.from_bytes(body[18:20], 'little') != 183:
            raise ValueError(f'Boot helper must be ELF64 AArch64: {name}')
        replacements['grow/' + name] = body
    for entry in entries:
        if entry['name'] in replacements:
            if entry['nlink'] != 1:
                raise ValueError('Unexpected hard-linked boot helper')
            entry['data'] = replacements.pop(entry['name'])
            entry.update(uid=0, gid=0, mode=stat.S_IFREG | 0o755)
    if replacements:
        raise ValueError('Reference boot archive lacks required helper entries')
    ramdisk = work / 'ramdisk.gz'
    ramdisk.write_bytes(gzip.compress(b''.join(emit(e) for e in entries), mtime=0))
    boot = work / 'boot.raw'
    pack_boot(argparse.Namespace(template=str(template), out=str(boot), ramdisk=str(ramdisk), kernel=None, second=None, dtb=None))
    _, new_header = read_header(boot)
    new_offsets = component_offsets(new_header)
    rebuilt = boot.read_bytes()
    for name in ['kernel', 'second', 'dtb']:
        size = header.get('dt_size_detected', header['dt_size']) if name == 'dtb' else header[name + '_size']
        if original[offsets[name]:offsets[name]+size] != rebuilt[new_offsets[name]:new_offsets[name]+size]:
            raise ValueError('Hardware boot component changed: ' + name)
    if 'enforcing' not in new_header['cmdline'] or 'permissive' in new_header['cmdline']:
        raise ValueError('Unexpected boot SELinux command line')
    data[start:start+length] = rebuilt
    target = work / 'prefix.raw'
    target.write_bytes(data)
    return target


def clean_userdata(path, layout, android_tools=None):
    with path.open('xb') as stream:
        stream.truncate(layout['userdata_bytes'])
    run(['mke2fs', '-q', '-F', '-t', 'ext4', '-b', '4096', '-I', '256', '-L', 'userdata',
         '-U', layout['userdata_uuid'], '-O', '^orphan_file,^metadata_csum_seed,^metadata_csum,^64bit',
         '-E', 'root_owner=1000:1000,lazy_itable_init=0,lazy_journal_init=0', path])
    run(['debugfs', '-w', '-R', 'set_inode_field / mode 040771', path])
    context = path.parent / 'userdata-context'
    context.write_bytes(b'u:object_r:system_data_file:s0\0')
    run(['debugfs', '-w', '-R', f'ea_set -f {context} / security.selinux', path])
    run(['e2fsck', '-f', '-n', path])
    listing = run(['debugfs', '-R', 'ls -l /', path]).stdout
    if 'misc' in listing or 'adb' in listing:
        raise ValueError('Unexpected data in freshly created userdata')
    if android_tools is not None:
        run(['qemu-aarch64', android_tools / 'e2fsck_static', '-f', '-n', path])
        run(['qemu-aarch64', android_tools / 'roc-grow-userdata-gpt', '--check-volume', path, '--image-test'])
    return path


def assemble(path, size, ranges):
    with path.open('xb') as out:
        end = 0
        for offset, source in sorted(ranges):
            source = regular(source)
            if offset < end or offset + source.stat().st_size > size:
                raise ValueError('Overlapping or overflowing image ranges')
            copy_sparse(source, out, offset)
            end = offset + source.stat().st_size
        out.truncate(size)
    # Independent range readback; a mismatched source or offset aborts packaging.
    with path.open('rb') as stream:
        for offset, source in ranges:
            stream.seek(offset)
            remaining = source.stat().st_size
            digest = hashlib.sha256()
            while remaining:
                block = stream.read(min(1024**2, remaining))
                if not block:
                    raise ValueError('Incomplete assembled image')
                remaining -= len(block)
                digest.update(block)
            if digest.hexdigest() != sha(source):
                raise ValueError('Image range readback mismatch')


def main(args):
    inputs = args.inputs.resolve()
    product = args.product.resolve()
    output = args.output.absolute()
    if any(c.isspace() for c in str(output)):
        raise ValueError('Use output paths without spaces for debugfs')
    if output.exists():
        raise ValueError('Choose a new output directory')
    built = json.loads(regular(product / 'public-build.json').read_text())
    if not built['passed'] or built['product'] != 'roc_os_release_candidate-user':
        raise ValueError('A successful public user build receipt is required')
    manifest_sha = require_manifest_binding(built)
    build_receipt_sha = sha(product / 'public-build.json')
    for name in ['system.img', 'vendor.img', 'ramdisk.img']:
        require_hash(product / name, built['images'][name])
    spec = load('external-inputs.json')['reference_image']
    for name in ['prefix', 'backup_gpt']:
        require_hash(inputs / (name + '.raw'), spec['ranges'][name]['sha256'])
    output.mkdir(parents=True)
    system = expand(product / 'system.img', output / 'system.raw', spec['ranges']['system']['bytes'])
    vendor = expand(product / 'vendor.img', output / 'vendor.raw', spec['ranges']['vendor']['bytes'])
    check_properties(system, output)
    prefix = boot_prefix(inputs, system, output)
    userdata = clean_userdata(output / 'userdata.raw', spec['layout'], output)
    raw = output / 'ROC_OS_ARM64_community.img'
    ranges = [(0, prefix), (spec['ranges']['system']['offset'], system),
              (spec['ranges']['vendor']['offset'], vendor),
              (spec['layout']['userdata_offset'], userdata),
              (spec['ranges']['backup_gpt']['offset'], inputs / 'backup_gpt.raw')]
    assemble(raw, spec['raw_bytes'], ranges)
    packed = raw.with_suffix('.img.gz')
    with raw.open('rb') as src, packed.open('xb') as dst:
        with gzip.GzipFile(filename='', fileobj=dst, mode='wb', compresslevel=6, mtime=0) as stream:
            while block := src.read(1024**2):
                stream.write(block)
    raw_hash = sha(raw)
    with gzip.open(packed, 'rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != raw_hash:
        raise ValueError('Complete gzip readback mismatch')
    write_json(output / 'result.json', {'passed': True, 'bytes': packed.stat().st_size,
               'source_manifest_sha256': manifest_sha, 'public_build_receipt_sha256': build_receipt_sha,
               'sha256': sha(packed), 'raw_bytes': raw.stat().st_size, 'raw_sha256': raw_hash,
               'system_input_sha256': sha(product / 'system.img'), 'vendor_input_sha256': sha(product / 'vendor.img'),
               'hardware_kernel_dtb_retained': True, 'userdata_created_empty': True,
               'preauthorized_adb_keys': False, 'physical_device_tested': False,
               'official_signature_or_identical_official_SHA': False})
    print(f'PACKAGED {packed}; new empty userdata, no preauthorized ADB key', flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--inputs', type=Path, required=True)
    ap.add_argument('--product', type=Path, required=True, help='Rebuilt OUT_DIR/target/product/roc_os_source64')
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    try:
        main(args)
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(2)

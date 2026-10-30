#!/usr/bin/env python3
"""Add the explicitly approved MT APK to a pinned v6a, without rewriting v6a.

Use H700ReleaseImageMT in the low-pressure wrapper. Only regular local image
files are opened. Compress the contiguous ranges directly: no 32GB raw on D:.
"""
import copy
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

import package_h700_v6a as base

ROOT = base.ROOT
WORK = Path('/home/lpf/h700-release-v6b-20261030')
OUT = ROOT / 'out/h700-v6b-preinstall-20261030'
PARENT_RAW_SHA = '2c4b6178a0202353d9dd31787f7a1b720141c62c2fbdff7120ae5684d45cabea'
PARENT_COMPONENTS_SHA = '8467a9145e9b3749fb2ea957735e4c32d4222a4e9228cc151285f18b1ed200a4'
PARENT_PAYLOAD_SHA = '34e0ef4b9b4ad13f88354207431752fdd4c10837182273eb50d316a6a81289f7'
MT_SHA = '8f83cef8ac63f76a81e1fee3ededb213f6ba43cc19761e38bc4e567c87edd47d'
RELEASE = 'H700_RG34XXSP_2GB_v6b_20261030_NoROM_MT'


def check_apps(parent, selected):
    """Permit exactly the seven unchanged entries plus the approved MT APK."""
    if len(parent) != 7 or len(selected) != 8 or selected[:7] != parent:
        raise ValueError('Only MT may be added to the exact seven selected inputs')
    mt = selected[7]
    if (mt['id'], mt['package'], mt['sha256'], mt['bytes']) != ('MTManager', 'bin.mt.plus', MT_SHA, 37521106):
        raise ValueError('Unrecognized MT input')
    if mt['file'] != 'out/mt-manager-20261030/MT2.26.10.apk':
        raise ValueError('Use the preserved official MT APK')


def validate_ranges(ranges):
    offset = 0
    for r in ranges:
        if r['offset'] != offset or r['bytes'] <= 0:
            raise ValueError('Image ranges overlap or contain a gap')
        offset += r['bytes']
    return offset


def transfer_exact(src, count, *consumers):
    digest = hashlib.sha256()
    while count:
        block = src.read(min(count, 8 * 1024**2))
        if not block:
            raise ValueError('Short image range')
        for consume in consumers:
            consume(block)
        digest.update(block)
        count -= len(block)
    return digest.hexdigest()


def preflight():
    parent = json.loads((ROOT / 'docs/baselines/rg34xxsp-v6a-20261030/image-lock.json').read_text())
    if parent['sha256'] != PARENT_RAW_SHA or not parent['gzip']['full_decompressed_sha256_verified']:
        raise ValueError('Unexpected v6a parent')
    components_file = base.regular(base.OUT / 'partition-components.json')
    payload_file = base.regular(base.OUT / 'payload-manifest.json')
    if base.sha(components_file) != PARENT_COMPONENTS_SHA or base.sha(payload_file) != PARENT_PAYLOAD_SHA:
        raise ValueError('Parent component/payload receipts changed')
    parts = json.loads(components_file.read_text())
    payload = json.loads(payload_file.read_text())
    selected = json.loads((ROOT / 'config/pegasus/preinstall-apks-v6b.json').read_text())
    check_apps(payload['apps'], selected)
    mt = base.regular(ROOT / selected[7]['file'])
    if mt.stat().st_size != selected[7]['bytes'] or base.sha(mt) != MT_SHA:
        raise ValueError('Official MT APK hash mismatch')
    for r in parent['ranges']:
        name = r['name']
        file = base.WORK / (name + ('.candidate.raw' if name in ('system', 'vendor') else '.raw'))
        base.regular(file)
        print('VERIFY_PARENT_RANGE ' + name, flush=True)
        if file.stat().st_size != r['bytes'] or base.sha(file) != r['sha256']:
            raise ValueError('Parent range changed: ' + name)
    return parent, parts, payload, selected


def patch_system(parts, payload, selected):
    marker = WORK / 'partitions-verified.json'
    if marker.exists():
        raise ValueError('A completed v6b stage already exists; do not overwrite it')
    image = WORK / 'system.candidate.raw'
    if image.exists():
        raise ValueError('An incomplete v6b partition is retained for inspection')
    subprocess.run(['cp', '--sparse=always', str(base.WORK / 'system.candidate.raw'), str(image)], check=True)
    delta = WORK / 'delta'
    delta.mkdir()
    mt = ROOT / selected[7]['file']
    apps = base.write(delta / 'apps.list', ''.join(a['package'] + ' ' + a['id'] + '.apk ' + a['sha256'] + '\n' for a in selected))
    files = copy.deepcopy(payload['files'])
    files.pop('SHA256SUMS')
    files['apks/MTManager.apk'] = MT_SHA
    files['apps.list'] = base.sha(apps)
    sums = base.write(delta / 'SHA256SUMS', ''.join(d + '  ' + n + '\n' for n, d in sorted(files.items())))
    files['SHA256SUMS'] = base.sha(sums)
    prop = base.dump(image, '/system/build.prop', delta / 'build.prop')
    text = prop.read_text()
    if len(re.findall(r'^ro.h700.release=v6a-rg34xxsp-20261030$', text, re.M)) != 1:
        raise ValueError('Unexpected parent release property')
    base.write(prop, text.replace('ro.h700.release=v6a-rg34xxsp-20261030', 'ro.h700.release=v6b-rg34xxsp-20261030'))
    script = ROOT / 'android/h700-android10/device/roc/rgsp/h700-preinstall-v6b.sh'
    subprocess.run(['bash', '-n', str(script)], check=True)
    changes = {
        '/system/etc/h700-preinstall/apks/MTManager.apk': mt,
        '/system/etc/h700-preinstall/apps.list': apps,
        '/system/etc/h700-preinstall/SHA256SUMS': sums,
        '/system/build.prop': prop,
        '/system/bin/h700-preinstall.sh': script,
    }
    context = WORK / 'system-file.context'
    context.write_bytes(base.context_for('system', '/system/bin/h700-preinstall.sh'))
    commands = []
    for inside, source in changes.items():
        mode = '0100755' if inside.endswith('/h700-preinstall.sh') else '0100644'
        commands += ['rm ' + base.q(inside), 'write ' + base.q(source) + ' ' + base.q(inside),
                     'set_inode_field ' + base.q(inside) + ' mode ' + mode,
                     'set_inode_field ' + base.q(inside) + ' uid 0',
                     'set_inode_field ' + base.q(inside) + ' gid 0',
                     'ea_set -f ' + base.q(context) + ' ' + base.q(inside) + ' security.selinux']
    cmdfile = base.write(WORK / 'system.debugfs.commands', '\n'.join(commands) + '\n')
    with (WORK / 'system.debugfs.log').open('w') as log:
        subprocess.run(['debugfs', '-w', '-f', str(cmdfile), str(image)], stdout=log, stderr=subprocess.STDOUT, check=True)
    updated = copy.deepcopy(parts)
    for inside, source in changes.items():
        updated['system']['files'][inside] = base.sha(source)
    for name in ('system', 'vendor'):
        current = image if name == 'system' else base.WORK / 'vendor.candidate.raw'
        with (WORK / (name + '.fsck.log')).open('w') as log:
            subprocess.run(['e2fsck', '-f', '-n', str(current)], stdout=log, stderr=subprocess.STDOUT, check=True)
        for i, (inside, digest) in enumerate(updated[name]['files'].items()):
            sample = base.dump(current, inside, WORK / 'readback.tmp')
            if base.sha(sample) != digest:
                raise ValueError('Component readback mismatch: ' + inside)
            attr = WORK / 'context-readback.tmp'
            if attr.exists():
                attr.unlink()
            base.debug(current, 'ea_get -f ' + base.q(attr) + ' ' + base.q(inside) + ' security.selinux')
            if not attr.exists() or attr.read_bytes() != base.context_for(name, inside):
                raise ValueError('SELinux label mismatch: ' + inside)
            if i and i % 500 == 0:
                print('READBACK ' + name + ' ' + str(i), flush=True)
        updated[name]['sha256'] = base.sha(current)
        updated[name]['e2fsck_exit'] = 0
    # All legacy payload entries are preserved; only the app list and checksums change.
    old_payload = base.WORK / 'payload'
    new_payload = copy.deepcopy(payload)
    new_payload.update({'apps': selected, 'files': files})
    new_payload['bytes'] += mt.stat().st_size + apps.stat().st_size - (old_payload / 'apps.list').stat().st_size + sums.stat().st_size - (old_payload / 'SHA256SUMS').stat().st_size
    base.jsonwrite(marker, updated)
    base.jsonwrite(WORK / 'payload-verified.json', new_payload)
    base.jsonwrite(WORK / 'delta-lock.json', {k: base.sha(v) for k, v in changes.items()})
    return updated, new_payload


def compress(parent, parts, payload):
    ranges = copy.deepcopy(parent['ranges'])
    if validate_ranges(ranges) != base.SIZE:
        raise ValueError('Unexpected image length')
    for r in ranges:
        if r['name'] in parts:
            r['sha256'] = parts[r['name']]['sha256']
    output = OUT / (RELEASE + '.img.gz')
    partial = OUT / (RELEASE + '.img.gz.partial')
    receipt = OUT / 'image-manifest.json'
    if any(p.exists() for p in (output, partial, receipt)):
        raise ValueError('Use new output names; existing artifacts are protected')
    print('COMPRESS_RANGES_DIRECTLY_NO_RAW_COPY', flush=True)
    full = hashlib.sha256()
    with partial.open('xb') as stream:
        with gzip.GzipFile(filename='', fileobj=stream, mode='wb', compresslevel=6, mtime=0) as dst:
            for r in ranges:
                name = r['name']
                source = (WORK / 'system.candidate.raw' if name == 'system' else
                          base.WORK / ('vendor.candidate.raw' if name == 'vendor' else name + '.raw'))
                print('COMPRESS_RANGE ' + name, flush=True)
                with source.open('rb') as src:
                    digest = transfer_exact(src, r['bytes'], dst.write, full.update)
                    if src.read(1) or digest != r['sha256']:
                        raise ValueError('Range changed during compression: ' + name)
    print('VERIFY_GZIP_FULL_DECOMPRESSION_AND_RANGES', flush=True)
    checked = hashlib.sha256()
    with gzip.open(partial, 'rb') as src:
        for r in ranges:
            if transfer_exact(src, r['bytes'], checked.update) != r['sha256']:
                raise ValueError('Decompressed range mismatch: ' + r['name'])
        if src.read(1) or checked.hexdigest() != full.hexdigest():
            raise ValueError('Full decompression SHA mismatch')
    compressed_sha = base.sha(partial)
    result = {
        'release': RELEASE, 'status': 'FILESYSTEM_COMPONENTS_RANGES_AND_GZIP_VERIFIED_PENDING_COLD_FLASH_ACCEPTANCE',
        'parent_image_sha256': PARENT_RAW_SHA, 'base_sha256': base.BASE,
        'bytes': base.SIZE, 'sha256': full.hexdigest(), 'ranges': ranges,
        'gzip': {'file': output.name, 'bytes': partial.stat().st_size, 'sha256': compressed_sha, 'full_decompressed_sha256_verified': True},
        'raw_materialized': False, 'preinstall_apps': payload['apps'], 'game_rom_files': 0,
        'collection_entries': payload['game_entries'], 'media_files': payload['media_files'],
        'factory_userdata_and_roms_preserved': True, 'full_aosp_rebuild': False,
        'physical_flash_performed': False, 'fresh_first_boot_verified': False,
        'cpu_quota': 'one aggregate CPU, affinity 0-1, nice 19', 'memory_max_gib': 6, 'swap_max_mib': 512,
        'hardware_voltage_telemetry_available': False,
        'partition_component_manifest_sha256': base.sha(WORK / 'partitions-verified.json'),
        'payload_manifest_sha256': base.sha(WORK / 'payload-verified.json'),
    }
    partial.rename(output)
    base.jsonwrite(receipt, result)
    base.jsonwrite(OUT / 'partition-components.json', parts)
    base.jsonwrite(OUT / 'payload-manifest.json', payload)
    base.write(OUT / (output.name + '.sha256'), compressed_sha + '  ' + output.name + '\n')
    print('IMAGE_READY ' + str(output), flush=True)


def main():
    base.constrained()
    if shutil.disk_usage(ROOT).free < 40 * 1024**3 or shutil.disk_usage('/home/lpf').free < 12 * 1024**3:
        raise ValueError('Need 40GiB output / 12GiB stage free')
    OUT.mkdir(exist_ok=True)
    WORK.mkdir(exist_ok=True)
    parent, parts, payload, selected = preflight()
    print('PATCH_FIVE_EXPLICIT_FILES', flush=True)
    parts, payload = patch_system(parts, payload, selected)
    compress(parent, parts, payload)


if __name__ == '__main__':
    main()

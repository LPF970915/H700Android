#!/usr/bin/env python3
"""Package H700 Test14 with USB0 peripheral mode and the system gamepad checker."""

import argparse
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import zipfile

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / 'tools'), str(REPO / 'tools/boot_selector/twelve_model')]
from package_h700_v6a import constrained
from release.package_002 import debugfs, extract_tree, install, metadata, regular, sha, sparse_copy, tree_delta, write_json
from release.verify_002 import RANGES, RAW_BYTES, require, stream_ranges, verify_gpt
from rg35xxh_display import TOC_OFFSET, TOC_BYTES, fdt_properties, read_toc

TEST13 = REPO / 'out/roc-os-h700-gamepad-triggers-test13-20261120'
PARENT_VERIFY = '34a4a9d7d6e04faa2a730499d509669d6759f67e22fdd8a7af44bb9849056037'
PARENT_SYSTEM = Path('/home/lpf/roc-h700-digital-triggers-image-20261120-v1/test13-from-gzip.raw')
TAIL_SOURCE = Path('/home/lpf/roc-h700-standard-a-test12-20261118-v1/parent.img')
ANDROID = Path('/home/lpf/h700-android10/android')
KEYS = Path('/home/lpf/.roc-os/keys/production-v1')
HOST = Path('/home/lpf/roc-os-user-20261104/out/host/linux-x86')
SDK = ANDROID / 'prebuilts/sdk/tools/linux'
JDK = ANDROID / 'prebuilts/jdk/jdk9/linux-x86/bin'
APP = REPO / 'tools/input_probe/gamepad'
MANIFEST = REPO / 'build-support/public/source-manifest.json'
APP_DIR = '/system/app/ROCGamepadCheck'
APP_APK = APP_DIR + '/ROCGamepadCheck.apk'
USB = '/soc@03000000/usbc0@0/'
PORT = USB + 'usb_port_type'
IMAGE = 'ROC_OS_ARM64_ver0.0.3_H700_Test14_USBDevice_GamepadCheck_20261120.img.gz'
SYSTEM_OFFSET, SYSTEM_SIZE = RANGES['system']


def digest(data):
    return hashlib.sha256(data).hexdigest()


def control_tree(prefix):
    toc = prefix[TOC_OFFSET:TOC_OFFSET + TOC_BYTES]
    records = read_toc(toc)
    require(records['bytes'] == TOC_BYTES, 'Unexpected TOC checksum length')
    item = next(row for row in records['items'] if row['name'] == 'dtb')
    offset = TOC_OFFSET + item['offset']
    _, properties = fdt_properties(prefix[offset:offset + item['bytes']])
    return offset, properties, records['items']


def patch_usb(prefix):
    require(len(prefix) == SYSTEM_OFFSET, 'Wrong boot prefix size')
    offset, props, items = control_tree(prefix)
    require(props[USB + 'status']['data'] == b'okay\0', 'USB0 manager disabled')
    require(props[USB + 'usb_detect_type']['data'] == b'\0\0\0\x02' and
            props[USB + 'usb_det_vbus_gpio']['data'] == b'axp_ctrl\0', 'Unexpected baseline USB wiring')
    require(props[PORT]['data'] == b'\0\0\0\x02', 'Baseline USB0 is not OTG')
    property_offset = offset + props[PORT]['offset']
    updated = bytearray(prefix)
    struct.pack_into('>I', updated, property_offset, 0)
    struct.pack_into('<I', updated, TOC_OFFSET + 20, 0x5f0a6c39)
    checksum = sum(struct.unpack_from(f'<{TOC_BYTES // 4}I', updated, TOC_OFFSET)) & 0xffffffff
    struct.pack_into('<I', updated, TOC_OFFSET + 20, checksum)
    _, after, new_items = control_tree(updated)
    require(before_after_property_delta(props, after) == {PORT}, 'USB patch altered another property')
    require(after[PORT]['data'] == b'\0' * 4, 'USB port mode readback failed')
    require([item for item in items if item['name'] != 'dtb'] ==
            [item for item in new_items if item['name'] != 'dtb'], 'Another TOC component changed')
    return bytes(updated), property_offset


def before_after_property_delta(before, after):
    require(before.keys() == after.keys(), 'Device tree property set changed')
    return {path for path in before if before[path] != after[path]}


def boot_proof(prefix_file, prefix_hash, output):
    import verify_final_handoff as machine

    original_tree = machine.tree

    def usb_tree(execution, address):
        result = original_tree(execution, address)
        _, properties = fdt_properties(bytes(execution.uc.mem_read(address, 0x30000)))
        mode = struct.unpack('>I', properties[PORT]['data'])[0]
        require(mode == 0, 'Final kernel handoff did not retain USB0 peripheral mode')
        return dict(result, usb0_port_type=mode)

    machine.tree = usb_tree
    try:
        namespace = argparse.Namespace(prefix=prefix_file, prefix_sha256=prefix_hash, output=output)
        require(machine.main(namespace) == 0, 'Actual U-Boot handoff proof failed')
    finally:
        machine.tree = original_tree
    report = json.loads((output / 'result.json').read_text())
    require(report['positive_cases'] == 24 and all(case['final_DTB']['usb0_port_type'] == 0
            for case in report['cases']), 'Incomplete proof of USB0 role for all models')
    return report['positive_cases']


def run(*argv, env=None):
    return subprocess.check_output([str(value) for value in argv], env=env, text=True)


def apk_certificate():
    der = subprocess.check_output(['/usr/bin/openssl', 'x509', '-in', KEYS / 'releasekey.x509.pem', '-outform', 'DER'])
    return digest(der)


def verify_apk(apk):
    sdk_env = os.environ | {'LD_LIBRARY_PATH': f'{HOST}/lib64:{SDK}/lib64'}
    signature = run(JDK / 'java', '-Xmx256m', '-jar', SDK / 'lib/apksigner.jar', 'verify',
                    '--min-sdk-version', '29', '--max-sdk-version', '29', '--print-certs', apk)
    require(re.findall(r'certificate SHA-256 digest: ([0-9a-f]+)', signature) == [apk_certificate()],
            'Checker does not have the ROC release certificate')
    run(SDK / 'bin/zipalign', '-c', '4', apk, env=sdk_env)
    badging = run(SDK / 'bin/aapt', 'dump', 'badging', apk, env=sdk_env)
    require("package: name='com.roc.rgsp.gamepadcheck' versionCode='2' versionName='1.1'" in badging and
            "sdkVersion:'29'" in badging and "targetSdkVersion:'29'" in badging and
            'com.roc.rgsp.gamepadcheck.GamepadCheck' in badging and 'uses-permission' not in badging,
            'Checker manifest identity, launch entry or permissions differ')
    manifest = run(SDK / 'bin/aapt', 'dump', 'xmltree', apk, 'AndroidManifest.xml', env=sdk_env)
    require('android.intent.category.LAUNCHER' in manifest and
            'android.intent.category.LEANBACK_LAUNCHER' in manifest, 'Missing launcher categories')
    with zipfile.ZipFile(apk) as archive:
        require(archive.testzip() is None and archive.read('classes.dex')[:4] == b'dex\n', 'Invalid APK code')
    return {'sha256': sha(apk), 'signer_sha256': apk_certificate(), 'version': '1.1'}


def build_apk(work):
    content = json.loads(MANIFEST.read_text())
    entries = {record['input']['path']: record['sha256'] for record in content['files']
               if record['input']['kind'] == 'repository'}
    for name in ('Android.bp', 'AndroidManifest.xml', 'GamepadCheck.java'):
        file = APP / name
        require(sha(file) == entries[file.relative_to(REPO).as_posix()], 'Checker source manifest mismatch')
    sdk_env = os.environ | {'LD_LIBRARY_PATH': f'{HOST}/lib64:{SDK}/lib64'}
    android_jar = ANDROID / 'prebuilts/sdk/29/public/android.jar'
    classes = work / 'classes'
    classes.mkdir()
    run(JDK / 'javac', '--release', '8', '-encoding', 'UTF-8', '-classpath', android_jar,
        '-d', classes, APP / 'GamepadCheck.java')
    app_jar = work / 'checker.jar'
    run(JDK / 'jar', 'cf', app_jar, '-C', classes, '.')
    run(JDK / 'java', '-Xmx256m', '-cp', ANDROID / 'prebuilts/r8/buildtools/d8-master.jar',
        'com.android.tools.r8.D8', '--min-api', '29', '--lib', android_jar, '--output', work, app_jar)
    unsigned, aligned = work / 'unsigned.apk', work / 'aligned.apk'
    run(SDK / 'bin/aapt', 'package', '-f', '-M', APP / 'AndroidManifest.xml', '-I', android_jar,
        '-F', unsigned, env=sdk_env)
    with zipfile.ZipFile(unsigned, 'a', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(work / 'classes.dex', 'classes.dex')
    run(SDK / 'bin/zipalign', '-f', '4', unsigned, aligned, env=sdk_env)
    apk = work / 'ROCGamepadCheck.apk'
    run(JDK / 'java', '-Xmx256m', '-jar', SDK / 'lib/apksigner.jar', 'sign', '--min-sdk-version', '29',
        '--key', KEYS / 'releasekey.pk8', '--cert', KEYS / 'releasekey.x509.pem', '--out', apk, aligned)
    return apk, verify_apk(apk)


def verify_system(image, before, extract, report, output):
    fsck = run('/usr/sbin/e2fsck', '-f', '-n', image)
    (output / (extract.name + '-fsck.log')).write_text(fsck)
    expected = {'added': [APP_DIR, APP_APK], 'removed': [], 'changed': []}
    require(tree_delta(before, extract_tree(image, extract)) == expected, 'Unexpected system file changes')
    for path, wanted in report['metadata'].items():
        require(metadata(image, path) == wanted, 'System metadata mismatch: ' + path)
    require(verify_apk(extract / APP_APK.lstrip('/')) == report['apk'], 'Preinstalled APK readback mismatch')
    usb_init = extract / 'system/etc/init/h700-usb-configfs.rc'
    text = usb_init.read_text()
    require(text.count('setprop sys.usb.config mtp,adb') == 2 and
            text.count('setprop persist.sys.usb.config mtp,adb') == 2 and
            'setprop sys.usb.controller 5100000.udc-controller' in text, 'MTP default is not configured')


def main(work, output):
    require(not work.exists() and not output.exists(), 'Use a new work and output directory')
    receipt = TEST13 / 'verify-result.json'
    require(sha(receipt) == PARENT_VERIFY, 'Test13 proof changed')
    parent = json.loads(receipt.read_text())
    ranges = parent['raw']['ranges']
    parent_image = TEST13 / parent['image']
    require(parent['passed'] and sha(parent_image) == parent['image_sha256'], 'Unexpected Test13 gzip')
    work.mkdir(parents=True)
    output.mkdir(parents=True)
    with gzip.open(regular(parent_image), 'rb') as reader:
        prefix = reader.read(SYSTEM_OFFSET)
    require(digest(prefix) == ranges['prefix'], 'Test13 prefix mismatch')
    patched, cell_offset = patch_usb(prefix)
    prefix_file = work / 'prefix.raw'
    prefix_file.write_bytes(patched)
    prefix_hash = digest(patched)
    print('Running the actual U-Boot handoff for all model choices', flush=True)
    handoffs = boot_proof(prefix_file, prefix_hash, output / 'handoff')
    print('Building the production-signed Android 10 checker and staging the system partition', flush=True)
    apk, app_receipt = build_apk(work)
    require(sha(PARENT_SYSTEM) == ranges['system'], 'Verified Test13 system partition changed')
    before = extract_tree(PARENT_SYSTEM, work / 'test13-system')
    system = work / 'test14-system.raw'
    sparse_copy(PARENT_SYSTEM, system)
    directory_meta = metadata(system, '/system/app/LeanbackIME')
    file_meta = metadata(system, '/system/app/LeanbackIME/LeanbackIME.apk')
    debugfs(system, 'mkdir ' + APP_DIR, writable=True)
    label = work / 'directory-label.bin'
    label.write_bytes(directory_meta['selinux'].encode('ascii') + b'\0')
    debugfs(system, f'ea_set -f {label} {APP_DIR} security.selinux', writable=True)
    install(system, apk, APP_APK, file_meta, work)
    report = {'apk': app_receipt, 'metadata': {APP_DIR: directory_meta, APP_APK: file_meta}}
    verify_system(system, before, work / 'test14-system', report, output)
    print('Compressing Test14', flush=True)
    image = output / IMAGE
    partial = output / (IMAGE + '.partial')
    require(TAIL_SOURCE.stat().st_size == RAW_BYTES, 'Wrong retained tail source size')
    with partial.open('xb') as packed, gzip.GzipFile(filename='', fileobj=packed, mode='wb',
                                                   compresslevel=1, mtime=0) as writer:
        writer.write(patched)
        with system.open('rb') as source:
            shutil.copyfileobj(source, writer, 4 * 1024**2)
        with TAIL_SOURCE.open('rb') as source:
            source.seek(SYSTEM_OFFSET + SYSTEM_SIZE)
            shutil.copyfileobj(source, writer, 4 * 1024**2)
    partial.rename(image)
    print('Reading back the entire Test14 image and comparing it with Test13', flush=True)
    actual_prefix = work / 'prefix-readback.raw'
    actual_system = work / 'system-readback.raw'
    with gzip.open(image, 'rb') as reader:
        raw = stream_ranges(reader, {'prefix': actual_prefix, 'system': actual_system})
    gpt = verify_gpt(raw.pop('head'), raw.pop('tail'))
    require(gpt == parent['gpt'], 'GPT differs from Test13')
    require(raw['ranges'] == ranges | {'prefix': prefix_hash, 'system': sha(system)}, 'Unexpected range hash')
    actual = actual_prefix.read_bytes()
    _, props, _ = control_tree(actual)
    require(props[PORT]['data'] == bytes(4), 'Gzip readback has wrong USB mode')
    windows = [(TOC_OFFSET + 20, TOC_OFFSET + 24), (cell_offset, cell_offset + 4)]
    cursor = 0
    for begin, end in windows:
        require(prefix[cursor:begin] == actual[cursor:begin], 'Unrelated boot prefix bytes differ')
        cursor = end
    require(prefix[cursor:] == actual[cursor:], 'Unrelated boot prefix suffix differs')
    verify_system(actual_system, before, work / 'test14-readback-system', report, output)
    write_json(output / 'verify-result.json', {
        'passed': True, 'candidate_only': True, 'physical_usb_verified': False,
        'parent_image_sha256': parent['image_sha256'], 'image': image.name,
        'image_sha256': sha(image), 'image_bytes': image.stat().st_size, 'raw': raw, 'gpt': gpt,
        'usb': {'property': PORT, 'from': 2, 'to': 0, 'all_model_handoff_cases': handoffs,
                'changed_boot_windows': windows, 'android_default_functions': 'mtp,adb'},
        'checker': report, 'source_manifest_sha256': sha(MANIFEST),
        'handoff_proof_sha256': sha(output / 'handoff/result.json'),
    })


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    constrained()
    lock_path = Path('/tmp/h700-android10-low-pressure.lock')
    if not lock_path.exists():
        subprocess.run(['/usr/sbin/runuser', '-u', 'lpf', '--', '/usr/bin/touch', lock_path], check=True)
    with lock_path.open('rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        main(args.work, args.output)

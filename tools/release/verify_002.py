"""Independently verify actual 0.0.2 gzip bytes and its exact 0.0.1 delta.

Use the existing low-pressure/global-lock wrapper. This writes only a fresh
verification workspace and receipt, never an input image, Native tree or device.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import os
import re
import stat
import struct
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
import zlib

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained

NATIVE = Path('/home/lpf/h700-android10/android')
HOST = Path('/home/lpf/roc-os-user-20261104/out/host/linux-x86')
BASE_GZIP_SHA = 'e72580e8c4e4afc8b08b50570ad6beebf46a435ee6e8b32b7a943f21786a6346'
BASE_RAW_SHA = '09935c4935ca579d6956388b2a3af509b4d6c4763e36a047091373a4218208e3'
BASE_SYSTEM_SHA = '5da9a675fea3c7804c3682394eaef712dab8e26fcb33d97464c08304e4a2ea80'
NAV_SHA = '780e5bc74af0ee375626628fd4e4970e77a8d10e78b4cfc21c339b8b25d6f4e5'
OLD_NAV_SHA = 'a5460ba1ad4956ca759797df561b19250110bc7626a351478c30d56492f0f5a6'
RRO_SHA = '5f4bba3f134cab9d60024badf468a62a7d6709b30836277d3630e65d0d66e842'
FRAMEWORK_SHA = '37ff73e1b9332c23c685c433e9b2bf9e810be8b36744b40dc172c192d37d1975'
CERT_SHA = 'fc30e834b3c2914a0646d0b46c4faaa045aa8d46189950012555a5f2c36745c9'
RAW_BYTES = 32434554368
RANGES = {
    'prefix': (0, 222298112),
    'system': (222298112, 8589934592),
    'vendor': (8812232704, 2147483648),
    'userdata': (10959716352, 21474836480),
    'backup_gpt': (32434552832, 1536),
}
NAV = '/system/app/ROCNavigation/ROCNavigation.apk'
PROPS = '/system/build.prop'
RRO = '/system/product/overlay/ROCTimeDefaults.apk'
FRAMEWORK = '/system/framework/framework-res.apk'
REMOVED = ['/system/app/ROCNavigation/oat/arm64/ROCNavigation.odex',
           '/system/app/ROCNavigation/oat/arm64/ROCNavigation.vdex']
SDK_PINS = {
    'prebuilts/jdk/jdk9/linux-x86/bin/java': '0fc49ba9e906db74a7d3cb0b4a44b9e0916e1e487b45431c0cb7ed281cd7ef65',
    'prebuilts/sdk/tools/linux/bin/aapt': 'ad71b6a5dc04977ceb84697f45ef2e2c7e8e29f33c8a62f39205f0525fd52835',
    'prebuilts/sdk/tools/linux/bin/zipalign': '7c4efc4f8b3c7454f42473f653b758200a68dac4ed79df37c1d4b8661c83887f',
    'prebuilts/sdk/tools/linux/lib/apksigner.jar': 'b9b61b17a11523da8e10e454f35ef1093397014e22b67323576816456e64537c',
}
HOST_PINS = {
    'bin/aapt2': '648030a1c3eb82853de3db71d668bee042ccb042e25c17cab247ec354fc3ba6e',
    'bin/idmap2': '3e091dd90832d7999b679bae7d5a152d7b6a5252793b78c5e59be18739772416',
    'lib64/libz-host.so': '264dc3747d8f351e5742a053507bbfdca448ded25a427b794d77c7b0a7be02af',
    'lib64/libc++.so': '2386a312915f4b6d86bd20e677d8f3948b823d7a1441670cfe0cf05fd4d66e64',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def regular(path):
    path = Path(path)
    require(not path.is_symlink() and stat.S_ISREG(path.lstat().st_mode),
            'Ordinary input required: ' + str(path))
    return path


def sha(path):
    with regular(path).open('rb') as reader:
        return hashlib.file_digest(reader, 'sha256').hexdigest()


def json_write(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def stream_ranges(reader, outputs=None):
    """Hash every actual byte once, splitting exact ranges independently."""
    outputs = outputs or {}
    total, digest = 0, hashlib.sha256()
    hashes = {name: hashlib.sha256() for name in RANGES}
    handles = {name: path.open('xb') for name, path in outputs.items()}
    head, tail = b'', b''
    try:
        while block := reader.read(4 * 1024**2):
            end = total + len(block)
            require(end <= RAW_BYTES, 'Expanded image exceeds exact card size')
            digest.update(block)
            if total < 1024**2:
                head += block[:min(len(block), 1024**2 - total)]
            tail = (tail + block)[-1536:]
            for name, (offset, length) in RANGES.items():
                lo, hi = max(total, offset), min(end, offset + length)
                if lo >= hi:
                    continue
                section = block[lo-total:hi-total]
                hashes[name].update(section)
                if name in handles:
                    target = handles[name]
                    if section.count(0) == len(section):
                        target.seek(len(section), os.SEEK_CUR)
                    else:
                        target.write(section)
            total = end
        require(total == RAW_BYTES, 'Expanded image size mismatch')
        for name, handle in handles.items():
            handle.truncate(RANGES[name][1])
    finally:
        for handle in handles.values():
            handle.close()
    return {'bytes': total, 'sha256': digest.hexdigest(),
            'ranges': {name: value.hexdigest() for name, value in hashes.items()},
            'head': head, 'tail': tail}


def verify_gpt(head, tail):
    require(head[510:512] == b'\x55\xaa', 'Missing protective MBR signature')
    headers = []
    tables = []
    for block, absolute in [(head[512:1024], 512), (tail[-512:], RAW_BYTES-512)]:
        require(block[:8] == b'EFI PART', 'Missing GPT header')
        size, stored_crc = struct.unpack_from('<II', block, 12)
        require(92 <= size <= 512, 'Invalid GPT header size')
        checked = bytearray(block[:size])
        checked[16:20] = b'\0' * 4
        require(zlib.crc32(checked) & 0xffffffff == stored_crc, 'GPT header CRC mismatch')
        current, backup, first, last = struct.unpack_from('<QQQQ', block, 24)
        table_lba, count, entry_size, table_crc = struct.unpack_from('<QIII', block, 72)
        require(current * 512 == absolute, 'GPT current LBA mismatch')
        require(entry_size >= 128 and entry_size % 8 == 0 and 0 < count <= 128,
                'Invalid GPT entries geometry')
        table_offset, length = table_lba * 512, count * entry_size
        if table_offset < len(head):
            table = head[table_offset:table_offset+length]
        else:
            start = table_offset - (RAW_BYTES - len(tail))
            table = tail[start:start+length]
        require(len(table) == length, 'GPT entries unavailable')
        require(zlib.crc32(table) & 0xffffffff == table_crc, 'GPT table CRC mismatch')
        headers.append((current, backup, first, last, block[56:72]))
        tables.append(table)
    require(headers[0][0] == 1 and headers[0][1] == RAW_BYTES//512-1,
            'Primary GPT backup LBA mismatch')
    require(headers[1][0] == headers[0][1] and headers[1][1] == 1, 'Backup GPT LBA mismatch')
    require(headers[0][2:] == headers[1][2:] and tables[0] == tables[1], 'GPT pair differs')
    entries = []
    entry_size = struct.unpack_from('<I', head, 512+84)[0]
    for i in range(0, len(tables[0]), entry_size):
        row = tables[0][i:i+entry_size]
        if row[:16] == b'\0' * 16:
            continue
        first, last = struct.unpack_from('<QQ', row, 32)
        entries.append({'name': row[56:128].decode('utf-16le').rstrip('\0'),
                        'offset': first*512, 'bytes': (last-first+1)*512})
    for name in ('system', 'vendor', 'userdata'):
        expected = RANGES[name]
        require(sum((e['offset'], e['bytes']) == expected for e in entries) == 1,
                'GPT partition does not match ' + name)
    return entries


def tree_inventory(root):
    entries = {}
    def walk(directory):
        for child in sorted(directory.iterdir()):
            info = child.lstat()
            key = '/' + child.relative_to(root).as_posix()
            row = {'mode': stat.S_IMODE(info.st_mode)}
            if stat.S_ISLNK(info.st_mode):
                row.update(kind='link', target=os.readlink(child))
            elif stat.S_ISDIR(info.st_mode):
                row['kind'] = 'directory'
                walk(child)
            elif stat.S_ISREG(info.st_mode):
                row.update(kind='file', bytes=info.st_size, sha256=sha(child))
            else:
                raise ValueError('Unexpected extracted node: ' + key)
            entries[key] = row
    walk(root)
    require(len(entries) >= 3000 and NAV in entries, 'Incomplete extracted system tree')
    return entries


def metadata(output, name):
    kind = re.search(r'Type: (\w+)\s+Mode:\s+([0-7]+)', output)
    owners = re.search(r'User:\s+(\d+)\s+Group:\s+(\d+)', output)
    label = re.search(r'security.selinux.*?= "([^"\\]+)', output)
    require(bool(kind and owners and label), 'Missing filesystem metadata: ' + name)
    return {'kind': kind[1], 'mode': kind[2], 'uid': int(owners[1]), 'gid': int(owners[2]),
            'selinux': label[1]}


def main(args):
    constrained()
    started = time.monotonic()
    require(not args.work.exists(), 'Fresh independent workspace required')
    require(not args.result.exists(), 'Independent receipt exists; preserve earlier results')
    args.work.mkdir(parents=True)
    args.result.parent.mkdir(parents=True, exist_ok=True)
    receipt = {'schema': 1, 'passed': False, 'independent': True, 'version': '0.0.2',
               'device_accessed': False, 'images_modified': False, 'runtime_accepted': False}
    env = os.environ.copy()
    sdk = NATIVE / 'prebuilts/sdk/tools/linux'
    env['LD_LIBRARY_PATH'] = str(HOST/'lib64') + ':' + str(sdk/'lib64')

    def run(argv, name, codes=(0,), log_stdout=True):
        result = subprocess.run(list(map(str, argv)), text=True, capture_output=True, env=env)
        # Settings XML output is deliberately never written to this log.
        with (args.work/'commands.log').open('a') as log:
            log.write(json.dumps(list(map(str, argv)))+'\nexit='+str(result.returncode)+'\n')
            if log_stdout:
                log.write(result.stdout+result.stderr+'\n')
        require(result.returncode in codes, name+' failed; inspect independent commands.log')
        return result.stdout, result.stderr

    def fs(image, command, name):
        return run(['/usr/sbin/debugfs', '-R', command, image], name)

    try:
        result = json.loads(regular(args.package_result).read_text())
        require(result['passed'] is True and result['version'] == '0.0.2', 'Package did not finish')
        image = regular(Path(result['image']))
        for path in [args.base_image, args.base_raw, args.base_system, image]:
            require(not any(c.isspace() for c in str(path)), 'Whitespace in debugfs path unsupported')
        locks = {str(p): sha(p) for p in [args.package_result, Path(__file__)]}
        for relative, digest in SDK_PINS.items():
            require(sha(NATIVE/relative) == digest, 'SDK tool differs: '+relative)
        for relative, digest in HOST_PINS.items():
            require(sha(HOST/relative) == digest, 'Host tool differs: '+relative)
        print('PHASE=independent_base_and_gzip_stream_hashes', flush=True)
        require(sha(args.base_image) == BASE_GZIP_SHA, 'Wrong 0.0.1 gzip')
        require(sha(args.base_system) == BASE_SYSTEM_SHA, 'Wrong 0.0.1 system')
        with regular(args.base_raw).open('rb') as reader:
            baseline = stream_ranges(reader)
        require(baseline['sha256'] == BASE_RAW_SHA, 'Wrong actual 0.0.1 raw')
        require(baseline['ranges']['system'] == BASE_SYSTEM_SHA, 'Base system range mismatch')
        require(image.stat().st_size == result['bytes'] and sha(image) == result['sha256'],
                'Published gzip hash/size mismatch')
        actual_system, actual_data = args.work/'actual-system.raw', args.work/'actual-userdata.raw'
        with gzip.open(image, 'rb') as reader:
            actual = stream_ranges(reader, {'system': actual_system, 'userdata': actual_data})
        require(actual['sha256'] == result['raw_sha256'], 'Full expanded gzip SHA mismatch')
        require(actual['bytes'] == result['raw_bytes'] == RAW_BYTES, 'Expanded size differs')
        for name, digest in actual['ranges'].items():
            require(digest == result['ranges'][name]['sha256'], 'Package range disagrees: '+name)
            require(baseline['ranges'][name] == result['ranges'][name]['base_sha256'],
                    'Package base range disagrees: '+name)
            if name != 'system':
                require(digest == baseline['ranges'][name], 'Non-system bytes changed: '+name)
        require(actual['ranges']['system'] != BASE_SYSTEM_SHA, 'System unexpectedly unchanged')
        entries = verify_gpt(actual['head'], actual['tail'])
        require(actual['head'][:2048] == baseline['head'][:2048] and actual['tail'] == baseline['tail'],
                'GPT/header bytes changed')
        receipt.update(gzip_sha256=result['sha256'], gzip_bytes=image.stat().st_size,
                       raw_sha256=actual['sha256'], raw_bytes=actual['bytes'],
                       actual_gzip_full_stream_verified=True, partitions=entries,
                       ranges=actual['ranges'], non_system_ranges_exactly_unchanged=True)
        print('PHASE=independent_actual_system_tree_and_metadata', flush=True)
        trees = []
        for name, source in [('base', args.base_system), ('actual', actual_system)]:
            root = args.work/(name+'-tree')
            root.mkdir()
            fs(source, 'rdump / '+str(root), name+'-system-rdump')
            inventory = tree_inventory(root)
            json_write(args.work/(name+'-filesystem.json'), inventory)
            trees.append(inventory)
        before, after = trees
        delta = {'added': sorted(after.keys()-before.keys()), 'removed': sorted(before.keys()-after.keys()),
                 'changed': sorted(p for p in before.keys() & after.keys() if before[p] != after[p])}
        expected = {'added': [RRO], 'removed': sorted(REMOVED), 'changed': sorted([NAV, PROPS])}
        require(delta == expected, 'Actual filesystem delta not the exact reviewed five files')
        require(before[NAV]['sha256'] == OLD_NAV_SHA and after[NAV]['sha256'] == NAV_SHA,
                'Navigation payload mismatch')
        require(after[RRO]['sha256'] == RRO_SHA, 'TimeDefaults payload mismatch')
        for removed in REMOVED:
            require(removed not in after, 'Old Navigation preopt remains')
        metadata_result = {}
        for name in [NAV, PROPS]:
            old = metadata(fs(args.base_system, 'stat '+name, 'base-stat')[0], name)
            new = metadata(fs(actual_system, 'stat '+name, 'actual-stat')[0], name)
            require(old == new, 'Replaced file metadata changed: '+name)
            metadata_result[name] = new
        overlay_meta = metadata(fs(actual_system, 'stat '+RRO, 'overlay-stat')[0], RRO)
        require(overlay_meta == {'kind': 'regular', 'mode': '0644', 'uid': 0, 'gid': 0,
                                 'selinux': 'u:object_r:vendor_overlay_file:s0'}, 'RRO metadata incorrect')
        metadata_result[RRO] = overlay_meta
        base_props = (args.work/'base-tree'/PROPS.lstrip('/')).read_bytes()
        actual_props = (args.work/'actual-tree'/PROPS.lstrip('/')).read_bytes()
        require(re.findall(rb'^ro.build.display.id=(.*)$', base_props, re.M) ==
                [b'QP1A.191105.004 dev-keys'], 'Unexpected base display version')
        expected_props = re.sub(rb'^ro.build.display.id=.*$', b'ro.build.display.id=ROC_OS_ARM64_ver0.0.2',
                                base_props, flags=re.M) + b'\n# ROC OS image release version\nro.roc.os.version=0.0.2\n'
        require(actual_props == expected_props, 'build.prop changed beyond two reviewed version properties')
        run(['/usr/sbin/e2fsck', '-f', '-n', actual_system], 'actual-system-readonly-fsck')
        receipt.update(filesystem_delta=delta, exactly_five_file_delta=True,
                       actual_file_metadata=metadata_result, old_navigation_preopt_absent=True,
                       build_properties_exactly_reviewed=True, system_readonly_fsck_passed=True)
        print('PHASE=actual_apk_signatures_resources_and_product_idmap', flush=True)
        paths = {name: args.work/'actual-tree'/name.lstrip('/') for name in [NAV, RRO, FRAMEWORK]}
        require(sha(paths[FRAMEWORK]) == FRAMEWORK_SHA, 'Actual target framework differs')
        java = NATIVE/'prebuilts/jdk/jdk9/linux-x86/bin/java'
        apk_reports = {}
        for name, apk in [(NAV, paths[NAV]), (RRO, paths[RRO])]:
            sig = run([java, '-Xmx256m', '-jar', sdk/'lib/apksigner.jar', 'verify',
                       '--min-sdk-version', '29', '--max-sdk-version', '29',
                       '--verbose', '--print-certs', apk], 'actual-signature')[0]
            require(re.findall(r'certificate SHA-256 digest: (\w+)', sig) == [CERT_SHA],
                    'Actual APK production certificate mismatch')
            run([sdk/'bin/zipalign', '-c', '4', apk], 'actual-alignment')
            badging = run([sdk/'bin/aapt', 'dump', 'badging', apk], 'actual-badging')[0]
            require("sdkVersion:'29'" in badging and "targetSdkVersion:'29'" in badging,
                    'Actual APK SDK differs')
            with zipfile.ZipFile(apk) as archive:
                names = archive.namelist()
                require(len(names) == len(set(names)), 'APK duplicate members')
                if name == NAV:
                    require(re.search(r"package: name='com\.roc\.rgsp\.navtrial' versionCode='17' versionName='2\.3-axis-guard'", badging),
                            'Actual Navigation version differs')
                    require(re.findall(r"uses-permission: name='([^']+)'", badging) ==
                            ['android.permission.EXPAND_STATUS_BAR'], 'Actual Navigation permission set differs')
                    require([n for n in names if n.endswith('.dex')] == ['classes.dex'], 'Navigation DEX set differs')
                    dex = archive.read('classes.dex')
                    require(dex[:8] == b'dex\n038\0' and struct.unpack_from('<I', dex, 32)[0] == len(dex),
                            'Navigation DEX size/version')
                    require(dex[12:32] == hashlib.sha1(dex[32:]).digest(), 'Navigation standard DEX SHA1')
                    require(struct.unpack_from('<I', dex, 8)[0] == zlib.adler32(dex[12:]) & 0xffffffff,
                            'Navigation DEX checksum')
                    for descriptor in [b'Lcom/roc/rgsp/navtrial/NavigationService;', b'Lcom/roc/rgsp/navtrial/AxisNavigation;']:
                        require(descriptor in dex, 'Navigation required class missing')
                else:
                    require(re.search(r"package: name='com\.roc\.os\.time\.defaults' versionCode='1' versionName='0\.0\.2'", badging),
                            'Actual RRO version differs')
                    require('uses-permission:' not in badging, 'RRO requests permissions')
                    require(set(n for n in names if not n.startswith('META-INF/')) ==
                            {'AndroidManifest.xml', 'resources.arsc'}, 'RRO has extra payload/code')
            apk_reports[name] = {'sha256': sha(apk), 'platform_certificate_sha256': CERT_SHA,
                                 'Android10_signature_verified': True, 'zipalign_verified': True}
        xml = run([sdk/'bin/aapt', 'dump', 'xmltree', paths[RRO], 'AndroidManifest.xml'],
                  'actual-overlay-manifest')[0]
        require(not re.search(r'\bE: (uses-permission|activity|activity-alias|service|provider|receiver)\b', xml),
                'RRO contains components or permissions')
        for pattern in [r'\bE: overlay\b', r'android:targetPackage[^\n]*="android"',
                        r'android:isStatic[^\n]*=\(type 0x12\)0xffffffff',
                        r'android:hasCode[^\n]*=\(type 0x12\)0x0',
                        r'android:priority[^\n]*=\(type 0x10\)0x3e8']:
            require(re.search(pattern, xml), 'RRO compiled manifest mismatch: '+pattern)
        resources = run([HOST/'bin/aapt2', 'dump', 'resources', paths[RRO]], 'actual-overlay-resources')[0]
        require(re.findall(r'^\s*resource 0x[0-9a-fA-F]+ (\S+)', resources, re.M) ==
                ['string/config_ntpServer'], 'RRO resource set differs')
        require('() "ntp.aliyun.com"' in resources, 'RRO server value differs')
        idmap = args.work/'actual-time-defaults.idmap'
        idmap_tool = HOST/'bin/idmap2'
        run([idmap_tool, 'create', '--target-apk-path', paths[FRAMEWORK], '--overlay-apk-path', paths[RRO],
             '--idmap-path', idmap, '--policy', 'public', '--policy', 'product'], 'actual-idmap-create')
        run([idmap_tool, 'verify', '--idmap-path', idmap], 'actual-idmap-verify')
        mapping = run([idmap_tool, 'dump', '--idmap-path', idmap], 'actual-idmap-dump')[0]
        rows = [line.strip() for line in mapping.splitlines() if re.match(r'^0x[0-9a-fA-F]+ -> ', line)]
        require(len(rows) == 1 and re.fullmatch(r'0x01040192 -> 0x[0-9a-fA-F]+ string/config_ntpServer', rows[0]),
                'RRO idmap contains unexpected mappings')
        lookup = run([idmap_tool, 'lookup', '--idmap-path', idmap, '--config', '',
                      '--resid', 'android:string/config_ntpServer'], 'actual-idmap-lookup')[0].strip()
        require(lookup == "cookie=1 config='' value=ntp.aliyun.com", 'Actual RRO lookup differs')
        receipt.update(actual_apks=apk_reports, actual_overlay_resources_exact=True,
                       idmap_overlayable_checks_enforced=True, idmap_policy=['public', 'product'],
                       actual_idmap_mappings=rows, actual_idmap_lookup=lookup)
        print('PHASE=selected_original_userdata_time_settings_only', flush=True)
        # The expanded published userdata is byte-identical to actual 0.0.1.
        # Never extract its tree, log XML, or read credentials/key files.
        setting_path = '/system/users/0/settings_global.xml'
        info, error = fs(actual_data, 'stat '+setting_path, 'selected-settings-stat')
        settings = {}
        if 'File not found' in error and not info.strip():
            state = 'settings_global.xml_absent'
        else:
            require('Inode:' in info, 'Cannot establish userdata settings state')
            text, cat_error = run(['/usr/sbin/debugfs', '-R', 'cat '+setting_path, actual_data],
                                  'selected-settings-only', log_stdout=False)
            require('File not found' not in cat_error and text.strip(), 'Settings XML read failed')
            root = ET.fromstring(text)
            for setting in root.iter('setting'):
                if setting.get('name') in ('ntp_server', 'auto_time'):
                    require(setting.get('name') not in settings, 'Duplicate selected setting')
                    settings[setting.get('name')] = setting.get('value')
            state = 'selected_fields_read'
        ntp = settings.get('ntp_server')
        require(ntp in (None, '', 'null', 'ntp.aliyun.com'), 'Explicit userdata ntp_server blocks reviewed overlay default')
        receipt['original_userdata_time_settings'] = {
            'actual_0_0_1_partition_and_published_gzip_partition_identical': True,
            'settings_file_state': state, 'selected_global_settings': settings,
            'explicit_ntp_server_override_present': ntp not in (None, '', 'null'),
            'overlay_default_not_masked_by_other_server': True,
            'other_settings_or_credentials_logged': False,
            'next_boot_network_sync_runtime_verified': False}
        require(all(sha(Path(p)) == value for p, value in locks.items()), 'Verifier/package receipt changed')
        require(all(sha(NATIVE/p) == value for p, value in SDK_PINS.items()), 'SDK tool changed')
        require(all(sha(HOST/p) == value for p, value in HOST_PINS.items()), 'Host tool changed')
        receipt.update(passed=True, verifier_sha256=locks[str(Path(__file__))],
                       package_result_sha256=locks[str(args.package_result)],
                       elapsed_seconds=time.monotonic()-started)
    except BaseException as error:
        receipt['failure'] = type(error).__name__+': '+str(error)
        raise
    finally:
        receipt['elapsed_seconds'] = time.monotonic()-started
        json_write(args.result, receipt)
    print('ROC_OS_002_INDEPENDENT_VERIFICATION_PASS', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('package-result', 'base-image', 'base-raw', 'base-system', 'work'):
        parser.add_argument('--'+option, type=Path, required=True)
    parser.add_argument('--result', type=Path,
                        default=REPO/'out/roc-os-0.0.2-20261114/independent-verify.json')
    main(parser.parse_args())

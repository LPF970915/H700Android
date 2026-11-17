"""Independently verify actual Test6 gzip bytes, startup, system and metadata.

The assembler/integrator is never imported. This verifier extracts the delivered
gzip into fresh ordinary files, inventories the entire rootfs, checks all node
owners/modes/SELinux labels, and inspects the actual APK/framework DEX. It never
opens a card, mounts an image, changes an input, or contacts a device.
"""
from pathlib import Path, PurePosixPath
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
import zipfile
import zlib

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained
from verify_002 import stream_ranges, verify_gpt, tree_inventory
from verify_h700_manual_selector import verify_prefix

NAME = 'ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test6_Navigation_20261115.img'
BASE_DIR = REPO / 'out/roc-os-h700-manual-selector-test5-20261114'
BASE_SYSTEM = Path('/home/lpf/roc-os-h700-manual-selector-20261114-v3/system.manual.raw')
BASE_RAW = BASE_SYSTEM.parent / 'ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test5_20261114.img'
ORIGINAL_RAW = Path('/home/lpf/roc-os-002-20261114-v1/ROC_OS_ARM64_ver0.0.2.img')
BASE_GZIP_SHA = '5ecd56492aef5bdc834ccd17444e5f5633b5684f4b7af1b49aab5a84d4d5f0ea'
BASE_RAW_SHA = '2baa84207517ebe77e57f2ff7c518dff115a2131a6027602ea3dca718f004002'
BASE_SYSTEM_SHA = '9ccb1d19cd78ecaabffdce16321e509146b45bc4807c38157d471c4616134e6e'
BASE_PREFIX_SHA = '4c83b0066b5f03da3f932aaf5b9628652bbeb5d3c001882a0bfc0356370b8f62'
BASE_ACCEPTANCE_SHA = '6a8e11d8b3cdde4686777e251713720d96d0e6bf6f3c147320a1900f857dca5f'
SOURCE_MANIFEST_SHA = 'c48f7f5dd07c73916ad5b5b10b0c215ab87e254a81453749393a15575761d8b9'
FRAMEWORK_SOURCE_SHA = 'e8110bc34ac032346b2da3fb625799420a72b278cc9e58e7d4b2aadf2b2044b3'
HIDDENAPI_SOURCE_SHA = '23f277953dafbf08e6100692eb06714bbd314ad33a04c8becb817250410a9965'
D8_JAR_SHA = '9b6750442852f290e07998e20b09c07d56071dc6190405cad73ecebf64cff396'
SPACE_SHA = '847b55c93f1c0a36983ada5a500d4311b18022ef86b2db2aa3dc5614f0f400d6'
CERT_SHA = 'fc30e834b3c2914a0646d0b46c4faaa045aa8d46189950012555a5f2c36745c9'
RAW_BYTES, PREFIX_BYTES, SYSTEM_BYTES = 32434554368, 222298112, 8589934592
NAV = '/system/app/ROCNavigation/ROCNavigation.apk'
FRAMEWORK = '/system/framework/framework.jar'
PROFILE_FILES = {'/system/etc/boot-image.prof', '/system/framework/framework.jar.prof',
                 '/system/framework/org.apache.http.legacy.jar.prof',
                 '/system/framework/services.rocsource.jar.prof',
                 '/system/framework/wifi-service.rocsource.jar.prof'}
KNOWN_ORPHANS = {f'/system/priv-app/ROCProvisioning/oat/arm64/ROCProvisioning.{suffix}'
                 for suffix in ('odex', 'vdex')}
GUARDS = {'Landroid/view/ViewRootImpl$RocDpadKeyGuard;',
          'Landroid/view/ViewRootImpl$RocJoystickGuard;'}
NAV_CLASSES = {'Lcom/roc/rgsp/navtrial/NavigationService;',
               'Lcom/roc/rgsp/navtrial/AxisNavigation;',
               'Lcom/roc/rgsp/navtrial/KeyNavigation;'}
BOOT_STEMS = ['boot', *('boot-' + name for name in (
    'core-libart', 'okhttp', 'bouncycastle', 'apache-xml', 'framework', 'ext',
    'telephony-common', 'voip-common', 'ims-common', 'android.test.base'))]
BOOT_FILES = {f'/system/framework/{arch}/{stem}.{suffix}'
              for arch in ('arm', 'arm64') for stem in BOOT_STEMS
              for suffix in ('art', 'oat')} | {
              f'/system/framework/{stem}.vdex' for stem in BOOT_STEMS}
BOOT_LINKS = {f'/system/framework/{arch}/{stem}.vdex': '../' + stem + '.vdex'
              for arch in ('arm', 'arm64') for stem in BOOT_STEMS}
PROTECTED = {
    '/init.environ.rc': 'd0d31c53f3e41b26a8ca360503a17f729346dfce2ed60f383c11ee7324e5f7af',
    '/system/build.prop': 'da093cf8ae3d0efa577565e37adee01de73a167df8473e5064de931e4a7006e2',
    '/system/framework/framework-res.apk': '37ff73e1b9332c23c685c433e9b2bf9e810be8b36744b40dc172c192d37d1975',
    '/system/priv-app/ROCReleaseLid/ROCReleaseLid.apk': '8b79b5f78914db5db250e3daa9410dab3d469cc6867d2189faded19cebd2b724',
    '/system/product/overlay/ROCTimeDefaults.apk': '5f4bba3f134cab9d60024badf468a62a7d6709b30836277d3630e65d0d66e842',
}
NATIVE = Path('/home/lpf/h700-android10/android')
HIDDENAPI_SOURCE = NATIVE / 'art/tools/hiddenapi/hiddenapi.cc'
D8_JAR = NATIVE / 'prebuilts/sdk/tools/linux/lib/d8.jar'
SDK_PINS = {
    'prebuilts/jdk/jdk9/linux-x86/bin/java': '0fc49ba9e906db74a7d3cb0b4a44b9e0916e1e487b45431c0cb7ed281cd7ef65',
    'prebuilts/sdk/tools/linux/bin/aapt': 'ad71b6a5dc04977ceb84697f45ef2e2c7e8e29f33c8a62f39205f0525fd52835',
    'prebuilts/sdk/tools/linux/bin/zipalign': '7c4efc4f8b3c7454f42473f653b758200a68dac4ed79df37c1d4b8661c83887f',
    'prebuilts/sdk/tools/linux/lib/apksigner.jar': 'b9b61b17a11523da8e10e454f35ef1093397014e22b67323576816456e64537c',
}
DEPENDENCIES = {
    'tools/release/verify_002.py': 'a737f350f8e8765b21105bc32ee497ef74f35ac6cea98d1c956caed88ab957a6',
    'tools/release/verify_h700_manual_selector.py': '5088a6fcf3891b4471cabf444d744588c3f793bdf830512ea928d4c897259c39',
    'tools/release/verify_h700_shared_panel.py': 'e4c4aac9c2655d9fbd2c17cc9f3a593b1c0772cee2d57e6f2dd4814068612faf',
    'tools/package_h700_v6a.py': '60dc0136f0c04c16d1ffda2257f063a018f48232e1374bfee0505483425def71',
}


def check(value, reason):
    if not value:
        raise ValueError(reason)


def regular(path):
    path = Path(path)
    check(not path.is_symlink() and stat.S_ISREG(path.lstat().st_mode), 'Ordinary file required: ' + str(path))
    return path


def sha(path):
    with regular(path).open('rb') as reader:
        return hashlib.file_digest(reader, 'sha256').hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def safe_path(name):
    check(isinstance(name, str) and name.startswith('/') and name != '/'
          and str(PurePosixPath(name)) == name and '..' not in PurePosixPath(name).parts
          and '\\' not in name and '"' not in name and not any(ord(c) < 32 for c in name),
          'Unsafe/noncanonical rootfs path')
    return name


def payload_kind(value):
    result = {'regular': 'file', 'symlink': 'link'}.get(value, value)
    check(result in ('file', 'directory', 'link'), 'Unknown payload kind')
    return result


def lid_runtime_path(name):
    match = re.fullmatch(r'/system/(?:(?:product|product_services)/)?(?:app|priv-app)/([^/]+)/(.*)', name)
    return bool(match and 'lid' in match[1].lower() and (
        'oat' in PurePosixPath(match[2]).parts or re.search(r'\.(?:odex|vdex|art|oat)$', match[2])))


def reviewed_orphans(production):
    fields = [production[key] for key in ('excluded_orphan_preopt_paths', 'excluded_historical_orphan_preopt_paths')
              if key in production]
    check(fields and all(value == fields[0] for value in fields), 'Missing/inconsistent production orphan exclusions')
    paths = fields[0]
    check(isinstance(paths, list) and paths == sorted(set(paths))
          and (not paths or set(paths) == KNOWN_ORPHANS), 'Unknown production orphan exclusion')
    check(set(paths) == KNOWN_ORPHANS & production['installed_files'].keys(),
          'Production orphan payload set differs from the explicit exclusions')
    return set(paths)


def allowed_delta(name, node_kind=None):
    if lid_runtime_path(name):
        return False
    if name in (NAV, FRAMEWORK) or name in BOOT_FILES or name in PROFILE_FILES:
        return True
    patterns = [r'/system/framework/(?:arm|arm64)/boot(?:-[\w.-]+)?\.vdex',
                r'/system/framework/oat/(?:arm|arm64)/[^/]+\.(?:odex|vdex|art)',
                r'/system/(?:app|priv-app)/[^/]+/oat/(?:arm|arm64)/[^/]+\.(?:odex|vdex|art)',
                r'/system/(?:product|product_services)/(?:app|priv-app)/[^/]+/oat/(?:arm|arm64)/[^/]+\.(?:odex|vdex|art)']
    return any(re.fullmatch(p, name) for p in patterns) or (node_kind == 'directory' and bool(re.fullmatch(
        r'/system/(?:(?:product|product_services)/)?(?:app|priv-app)/[^/]+/oat(?:/(?:arm|arm64))?', name)))


def read_interface(args):
    check(re.fullmatch(r'[0-9a-f]{64}', args.preparation_sha256), 'Invalid preparation SHA')
    check(sha(args.preparation) == args.preparation_sha256
          and sha(args.output / 'preparation.json') == args.preparation_sha256,
          'Preparation receipt/or published copy differs from pinned SHA')
    prep = json.loads(regular(args.preparation).read_text())
    check(prep['schema'] == 'roc.h700.navigation-test6.preparation.v1' and prep['passed'] is True,
          'Incomplete or foreign preparation')
    check(prep['base'] == {'test5_gzip_sha256': BASE_GZIP_SHA, 'raw_sha256': BASE_RAW_SHA,
                         'system_sha256': BASE_SYSTEM_SHA, 'prefix_sha256': BASE_PREFIX_SHA},
          'Another Test5 parent was prepared')
    check(prep['system']['bytes'] == SYSTEM_BYTES, 'Prepared system size mismatch')
    p = prep['production']
    check(p['framework_production_built'] is True and p['boot_images_built'] is True
          and p['architectures'] == ['arm', 'arm64']
          and p['dependent_preopt_strategy'] == 'rebuilt'
          and p['source_manifest_sha256'] == SOURCE_MANIFEST_SHA
          and p['framework_source_sha256'] == FRAMEWORK_SOURCE_SHA,
          'Missing reviewed real dual-ABI framework/ART production provenance')
    production_path = regular(Path(p['receipt_path']))
    check(sha(production_path) == p['receipt_sha256'], 'Production receipt changed')
    production = json.loads(production_path.read_text())
    check(all(production.get(flag) is True for flag in ('passed', 'framework_production_built', 'boot_images_built'))
          and production['source_manifest_sha256'] == SOURCE_MANIFEST_SHA
          and production['framework_source_sha256'] == FRAMEWORK_SOURCE_SHA,
          'Validation-only compilation is not a production framework/ART receipt')
    check(production['dependent_preopt_strategy'] == 'rebuilt', 'Complete rebuilt production runtime closure required')
    check(production['hiddenapi_source_sha256'] == HIDDENAPI_SOURCE_SHA
          and production['framework_dex_postprocessor'] == 'android10-hiddenapi-encode'
          and sha(HIDDENAPI_SOURCE) == HIDDENAPI_SOURCE_SHA,
          'Unreviewed platform framework hiddenapi production processing')
    check(production['d8_jar_sha256'] == D8_JAR_SHA and sha(D8_JAR) == D8_JAR_SHA,
          'Unreviewed Navigation D8 production processing')
    check(BOOT_FILES <= production['installed_files'].keys(), 'Incomplete same-build boot image artifact set')
    reviewed_orphans(production)
    check(production['boot_artifact_paths'] == sorted(BOOT_FILES), 'Production boot artifact topology differs from Test5')
    delta = prep['expected_delta']
    check(set(delta) == {'added', 'removed', 'changed'}, 'Expected delta keys differ')
    names = []
    for category, paths in delta.items():
        check(paths == sorted(set(paths)), 'Unsorted/duplicate reviewed delta: ' + category)
        names += [safe_path(path) for path in paths]
    check(len(names) == len(set(names)) and {NAV, FRAMEWORK} <= set(delta['changed']),
          'Overlapping delta or missing Navigation/framework update')
    check(set(prep['payloads']) == set(delta['added']) | set(delta['changed']), 'Payload/delta set mismatch')
    for path in names:
        item = prep['payloads'].get(path)
        check(allowed_delta(path, payload_kind(item['kind']) if item else None), 'Unreviewed system delta: ' + path)
    nav, framework = prep['navigation'], prep['framework']
    check(nav['path'] == NAV and nav['version_code'] == 18 and nav['certificate_sha256'] == CERT_SHA
          and nav['sha256'] == prep['payloads'][NAV]['sha256'], 'Wrong production Navigation18')
    check(framework['path'] == FRAMEWORK and framework['sha256'] == prep['payloads'][FRAMEWORK]['sha256']
          and GUARDS <= set(framework['required_descriptors']), 'Wrong production framework DEX identity')
    return prep, production, production_path


def verify_runtime_closure(after, production):
    """Bind every delivered dependency/profile to production, including unchanged nodes."""
    check(production['dependent_preopt_strategy'] == 'rebuilt', 'Only complete rebuilt runtime closure is accepted')
    installed = production['installed_files']
    excluded = reviewed_orphans(production)
    check(not KNOWN_ORPHANS & after.keys(), 'Historical orphan preopt survived in the delivered system')
    for name, row in after.items():
        # Empty inherited oat directories contain no precompiled code. A symlink
        # or any other node in such a directory must not bypass this prohibition.
        check(not (lid_runtime_path(name) and row['kind'] != 'directory'),
              'Retained Lid3 must have no oat/preopt payload: ' + name)

    def dependency(name):
        return bool(re.fullmatch(
            r'/system/(?:framework/oat/(?:arm|arm64)/[^/]+|'
            r'(?:(?:product|product_services)/)?(?:app|priv-app)/[^/]+/oat/(?:arm|arm64)/[^/]+)'
            r'\.(?:odex|vdex|art)', name))

    expected_preopt, actual_preopt = {}, {}
    for name, item in installed.items():
        if not re.search(r'\.(?:odex|vdex|art|oat)$', name) or name in BOOT_FILES or name in BOOT_LINKS:
            continue
        if name in excluded or lid_runtime_path(name):
            continue
        check(dependency(name), 'Unrecognized production preopt location: ' + name)
        expected_preopt[name] = item
    for name, row in after.items():
        if not re.search(r'\.(?:odex|vdex|art|oat)$', name) or name in BOOT_FILES or name in BOOT_LINKS:
            continue
        check(dependency(name) and row['kind'] == 'file', 'Unexpected delivered preopt node: ' + name)
        actual_preopt[name] = {key: row[key] for key in ('sha256', 'bytes')}
    check(actual_preopt == expected_preopt,
          'Complete delivered dependency preopt set/SHA/size differs from production')

    expected_profiles = {name: item for name, item in installed.items() if name.endswith('.prof')}
    actual_profiles = {}
    check(set(expected_profiles) <= PROFILE_FILES and '/system/etc/boot-image.prof' in expected_profiles,
          'Unreviewed or incomplete production runtime profile set')
    for name, row in after.items():
        if name.endswith('.prof'):
            check(name in PROFILE_FILES and row['kind'] == 'file', 'Unexpected delivered runtime profile: ' + name)
            actual_profiles[name] = {key: row[key] for key in ('sha256', 'bytes')}
    check(actual_profiles == expected_profiles,
          'Complete delivered runtime profile set/SHA/size differs from production')
    return {'dependent_preopt_paths': sorted(actual_preopt), 'dependent_preopt_files': len(actual_preopt),
            'profile_paths': sorted(actual_profiles), 'profile_files': len(actual_profiles),
            'excluded_orphan_preopt_paths': sorted(excluded),
            'all_preopt_and_profiles_bound_to_production': True, 'Lid_preopt_absent': True}


def dex_integrity(data, *, hiddenapi=False, pinned_d8=False):
    """Validate exact producer formats without modifying actual production bytes.

    Android10 hiddenapi.cc:657-710 appends hiddenapi class data and changes the map,
    then :845-846 only updates Adler32, matching ART's own verifier. This explicit
    mode is used solely for the production-SHA-bound framework.jar below. It
    validates the real hiddenapi section and records the nonstandard SHA1. The
    pinned legacy D8 producer uses SHA1(data[32:-52]); its exact format is allowed
    only by the production-SHA-bound Navigation call. Ordinary input is strict.
    """
    check(len(data) >= 112 and data[:4] == b'dex\n' and data[4:7] in (b'035', b'037', b'038', b'039')
          and data[7] == 0, 'Unsupported/truncated DEX header')
    check(struct.unpack_from('<III', data, 32) == (len(data), 112, 0x12345678), 'DEX length/header/endian mismatch')
    calculated = hashlib.sha1(data[32:]).digest()
    standard = data[12:32] == calculated
    check(not (hiddenapi and pinned_d8), 'DEX producer modes cannot be combined')
    check(struct.unpack_from('<I', data, 8)[0] == zlib.adler32(data[12:]) & 0xffffffff,
          'Actual DEX Adler32 checksum invalid')
    report = {'standard_sha1_matches': standard, 'stored_sha1': data[12:32].hex(),
              'calculated_standard_sha1': calculated.hex(), 'adler32_matches': True,
              'hiddenapi_producer_mode': hiddenapi, 'pinned_d8_producer_mode': pinned_d8,
              'producer_integrity_mode': 'standard' if standard else 'unaccepted'}
    if not hiddenapi:
        if pinned_d8:
            truncated = hashlib.sha1(data[32:-52]).digest()
            report['pinned_d8_truncated52_sha1_matches'] = data[12:32] == truncated
            report['calculated_pinned_d8_truncated52_sha1'] = truncated.hex()
            if not standard:
                check(data[4:7] in (b'038', b'039') and len(data) >= 164 and data[12:32] == truncated,
                      'Actual Navigation DEX differs from standard or exact pinned D8 signature format')
                report['producer_integrity_mode'] = 'pinned-d8-eof-minus52'
        else:
            check(standard, 'Actual DEX standard SHA1 signature invalid')
        return report
    check(data[:8] == b'dex\n039\0', 'Reviewed Android10 hiddenapi DEX must be version039')
    map_offset = struct.unpack_from('<I', data, 52)[0]
    check(112 <= map_offset <= len(data) - 4 and map_offset % 4 == 0,
          'Hiddenapi DEX map offset outside/alignment')
    map_count = struct.unpack_from('<I', data, map_offset)[0]
    check(0 < map_count and map_offset + 4 + map_count * 12 <= len(data),
          'Hiddenapi DEX map outside file')
    types, hidden = set(), []
    for index in range(map_count):
        item_type, unused, size, offset = struct.unpack_from('<HHII', data, map_offset + 4 + index * 12)
        check(unused == 0 and item_type not in types and size > 0 and offset < len(data),
              'Invalid/duplicate Hiddenapi DEX map item')
        types.add(item_type)
        if item_type == 0xf000:
            hidden.append((size, offset))
    check(len(hidden) == 1 and hidden[0][0] == 1, 'Required unique hiddenapi class-data map item absent')
    offset = hidden[0][1]
    check(112 <= offset <= len(data) - 4 and offset % 4 == 0,
          'Hiddenapi class-data offset outside/alignment')
    size = struct.unpack_from('<I', data, offset)[0]
    class_count = struct.unpack_from('<I', data, 96)[0]
    header_bytes = 4 + class_count * 4
    check(header_bytes <= size and offset + size <= map_offset,
          'Hiddenapi class-data section truncated or overlaps map')
    for index in range(class_count):
        class_offset = struct.unpack_from('<I', data, offset + 4 + index * 4)[0]
        check(class_offset == 0 or header_bytes <= class_offset < size,
              'Hiddenapi class flags outside section')
    report['hiddenapi_section'] = {'map_offset': map_offset, 'map_count': map_count,
                                  'offset': offset, 'bytes': size, 'class_count': class_count}
    report['producer_integrity_mode'] = 'android10-hiddenapi-encode'
    return report


def dex_classes(data, *, hiddenapi=False, pinned_d8=False):
    """Read real DEX class_defs, not occurrences of descriptor strings."""
    dex_integrity(data, hiddenapi=hiddenapi, pinned_d8=pinned_d8)
    string_count, string_offset = struct.unpack_from('<II', data, 56)
    type_count, type_offset = struct.unpack_from('<II', data, 64)
    class_count, class_offset = struct.unpack_from('<II', data, 96)
    for count, offset, stride in ((string_count, string_offset, 4), (type_count, type_offset, 4),
                                  (class_count, class_offset, 32)):
        check((count == 0 and offset == 0) or (112 <= offset <= offset + count * stride <= len(data)),
              'DEX indexed section outside file')
    result = set()
    for index in range(class_count):
        type_index = struct.unpack_from('<I', data, class_offset + index * 32)[0]
        check(type_index < type_count, 'DEX class type index out of range')
        string_index = struct.unpack_from('<I', data, type_offset + type_index * 4)[0]
        check(string_index < string_count, 'DEX type descriptor index out of range')
        cursor = struct.unpack_from('<I', data, string_offset + string_index * 4)[0]
        check(112 <= cursor < len(data), 'DEX descriptor offset outside file')
        for _ in range(5):
            check(cursor < len(data), 'Truncated DEX string length')
            value = data[cursor]
            cursor += 1
            if value < 128:
                break
        else:
            raise ValueError('Overlong DEX string length')
        end = data.find(b'\0', cursor)
        check(end > cursor, 'Unterminated DEX class descriptor')
        descriptor = data[cursor:end].decode('utf-8', errors='replace')
        check(descriptor.startswith('L') and descriptor.endswith(';') and descriptor not in result,
              'Invalid/duplicate DEX class definition')
        result.add(descriptor)
    return result


def jar_classes(path, *, hiddenapi=False, pinned_d8=False):
    with zipfile.ZipFile(regular(path)) as archive:
        names = archive.namelist()
        check(len(names) == len(set(names)), 'Duplicate ZIP members in actual Android artifact')
        check(not any(name.endswith('.class') for name in names), 'Java compile-check classes cannot be an Android framework/APK')
        dex_names = sorted(name for name in names if re.fullmatch(r'classes(?:[2-9]|[1-9][0-9]+)?\.dex', name))
        check(dex_names and 'classes.dex' in dex_names, 'Actual Android artifact contains no executable DEX')
        check(set(dex_names) == {name for name in names if name.endswith('.dex')}
              and set(dex_names) == {'classes' + (str(index) if index > 1 else '') + '.dex'
                                     for index in range(1, len(dex_names) + 1)},
              'Actual Android artifact has a noncanonical or incomplete multidex set')
        classes, members = set(), {}
        for name in dex_names:
            data = archive.read(name)
            definitions = dex_classes(data, hiddenapi=hiddenapi, pinned_d8=pinned_d8)
            check(not classes & definitions, 'Duplicate class definitions across Android DEX members')
            classes |= definitions
            members[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                             'defined_classes': len(definitions),
                             'integrity': dex_integrity(data, hiddenapi=hiddenapi, pinned_d8=pinned_d8)}
    return classes, members


def parse_metadata(text, name):
    kind = re.search(r'Type: (\w+)\s+Mode:\s+([0-7]+)', text)
    owners = re.search(r'User:\s+(\d+)\s+Group:\s+(\d+)', text)
    label = re.search(r'security\.selinux.*?= "([^"\\]+)', text)
    check(kind and owners, 'Incomplete actual ext4 metadata: ' + name)
    check(kind[1] in ('regular', 'directory', 'symlink'), 'Unexpected ext4 node kind: ' + name)
    return {'kind': {'regular': 'file', 'symlink': 'link'}.get(kind[1], kind[1]),
            'mode': format(int(kind[2], 8), '04o'), 'uid': int(owners[1]), 'gid': int(owners[2]),
            'selinux': label[1] if label else None}


def metadata_inventory(image, paths, folder, label, run):
    commands = folder / (label + '-metadata.commands')
    commands.write_text(''.join('stat ' + json.dumps(safe_path(name), ensure_ascii=False) + '\n'
                                for name in sorted(paths)), encoding='utf-8')
    output = run(['/usr/sbin/debugfs', '-f', commands, image], label + '-all-metadata')
    matches = list(re.finditer(r'^debugfs:\s+stat\s+(.+?)\s*$', output, re.M))
    result = {}
    for index, match in enumerate(matches):
        name = json.loads(match[1])
        check(name in paths and name not in result, 'Unexpected/duplicate debugfs metadata node')
        end = matches[index + 1].start() if index + 1 < len(matches) else len(output)
        result[name] = parse_metadata(output[match.end():end], name)
    check(set(result) == set(paths), 'Actual ext4 metadata scan incomplete')
    write_json(folder / (label + '-metadata.json'), result)
    return result


def main(args):
    constrained()
    started = time.monotonic()
    destination = args.output / 'independent-verify.json'
    folder = args.work / 'independent-verification'
    check(not destination.exists() and not folder.exists(), 'Fresh independent outputs required')
    check(args.work.is_dir() and args.output.is_dir(), 'Package work/output directories are missing')
    folder.mkdir()
    report = {'schema': 'roc.h700.navigation-test6.independent.v1', 'passed': False, 'independent': True,
              'physical_display_accepted': False, 'physical_navigation_accepted': False,
              'all_H700_models_accepted': False, 'device_accessed': False, 'images_modified': False}
    controls = {}
    sdk = NATIVE / 'prebuilts/sdk/tools/linux'
    env = os.environ.copy()
    env['LD_LIBRARY_PATH'] = str(sdk / 'lib64')

    def run(argv, name):
        result = subprocess.run(list(map(str, argv)), capture_output=True, text=True, errors='replace', env=env)
        output = result.stdout + result.stderr
        (folder / (name + '.log')).write_text(output, encoding='utf-8')
        with (folder / 'commands.log').open('a', encoding='utf-8') as writer:
            writer.write(json.dumps(list(map(str, argv))) + '\nexit=' + str(result.returncode) + '\n')
        check(result.returncode == 0, 'Independent command failed: ' + name)
        return output

    try:
        prep, production, production_path = read_interface(args)
        package_path, lock_path = args.output / 'image-result.json', args.work / 'input-lock.json'
        package = json.loads(regular(package_path).read_text())
        lock = json.loads(regular(lock_path).read_text())
        check(package['schema'] == 'roc.h700.navigation-test6.package.v1' and package['passed'] is True,
              'Package has not completed successfully')
        check(lock['schema'] == 'roc.h700.navigation-test6.package-inputs.v1'
              and sha(lock_path) == package['input_lock_sha256']
              and lock['preparation_sha256'] == args.preparation_sha256 == package['preparation_sha256']
              and lock['production_receipt_sha256'] == sha(production_path)
              and lock['system_sha256'] == prep['system']['sha256'], 'Package/preparation input-lock mismatch')
        check(Path(package['work']).resolve() == args.work.resolve()
              and Path(package['input_lock']).resolve() == lock_path.resolve(), 'Package work paths differ')
        controls = {str(path): sha(path) for path in [Path(__file__), regular(args.preparation), production_path,
                    package_path, lock_path, args.output / 'preparation.json',
                    BASE_DIR / 'acceptance.json', BASE_DIR / 'image-result.json',
                    HIDDENAPI_SOURCE, D8_JAR, REPO / 'build-support/public/source-manifest.json',
                    REPO / 'docs/SPACE_REVIEW_20261028.md']}
        check(controls[str(BASE_DIR / 'acceptance.json')] == BASE_ACCEPTANCE_SHA
              and controls[str(REPO / 'build-support/public/source-manifest.json')] == SOURCE_MANIFEST_SHA
              and controls[str(REPO / 'docs/SPACE_REVIEW_20261028.md')] == SPACE_SHA, 'Frozen baseline/source identities changed')
        check(all(sha(Path(path)) == value for path, value in lock['controls'].items()), 'Packaging control input changed')
        for name, value in DEPENDENCIES.items():
            check(sha(REPO / name) == value, 'Independent verifier dependency changed: ' + name)
            controls[str(REPO / name)] = value
        for name, value in SDK_PINS.items():
            check(sha(NATIVE / name) == value, 'APK inspection tool changed: ' + name)
            controls[str(NATIVE / name)] = value
        parent = json.loads(regular(BASE_DIR / 'image-result.json').read_text())
        check(parent['passed'] is True and parent['raw_sha256'] == BASE_RAW_SHA
              and parent['sha256'] == BASE_GZIP_SHA
              and parent['ranges']['prefix']['sha256'] == BASE_PREFIX_SHA
              and parent['ranges']['system']['sha256'] == BASE_SYSTEM_SHA, 'Frozen Test5 receipt differs')
        image, raw = regular(args.output / (NAME + '.gz')), regular(args.work / NAME)
        check(Path(package['image']).resolve() == image.resolve() and Path(package['raw']).resolve() == raw.resolve(),
              'Actual package paths differ')
        check(image.stat().st_size == package['bytes'] and sha(image) == package['sha256'], 'Actual delivered gzip SHA/size differs')
        print('PHASE=independent_complete_Test6_gzip_and_all_ranges', flush=True)
        actual_prefix, actual_system = folder / 'prefix.raw', folder / 'system.raw'
        with gzip.open(image, 'rb') as reader:
            streamed = stream_ranges(reader, {'prefix': actual_prefix, 'system': actual_system})
        check(streamed['bytes'] == package['raw_bytes'] == RAW_BYTES and streamed['sha256'] == package['raw_sha256'],
              'Complete expanded gzip SHA/length mismatch')
        check(raw.stat().st_size == RAW_BYTES and sha(raw) == streamed['sha256'], 'Ordinary raw and actual delivered gzip differ')
        for name, value in streamed['ranges'].items():
            check(value == package['ranges'][name]['sha256']
                  and package['ranges'][name]['base_sha256'] == parent['ranges'][name]['sha256'],
                  'Full-stream range/parent receipt mismatch: ' + name)
            if name != 'system':
                check(value == parent['ranges'][name]['sha256'], 'Test5 non-system range changed: ' + name)
        check(sha(actual_system) == prep['system']['sha256'] and actual_system.stat().st_size == SYSTEM_BYTES,
              'Actual delivered system differs from pinned preparation')
        check(sha(actual_prefix) == BASE_PREFIX_SHA, 'Complete Test5 startup prefix changed')
        print('PHASE=independent_exact_Test5_boot_and_menu_proof', flush=True)
        with regular(BASE_RAW).open('rb') as reader:
            frozen_prefix = reader.read(PREFIX_BYTES)
        check(hashlib.sha256(frozen_prefix).hexdigest() == BASE_PREFIX_SHA
              and actual_prefix.read_bytes() == frozen_prefix, 'Actual complete prefix is not byte-exact Test5')
        with regular(ORIGINAL_RAW).open('rb') as reader:
            original_prefix = reader.read(PREFIX_BYTES)
        shared_path = BASE_RAW.parent / 'prefix.shared.raw'
        prefix_proof = verify_prefix(original_prefix, regular(shared_path).read_bytes(), frozen_prefix,
                                     REPO / 'out/boot-selector-integration-20261114')
        check(prefix_proof['integrated_models'] == ['rg34xxsp', 'rgsp', 'rg35xxh']
              and prefix_proof['menu_models'] == 12, 'Test5 three-profile/twelve-model menu structure changed')
        gpt = verify_gpt(streamed['head'], streamed['tail'])
        del frozen_prefix, original_prefix
        print('PHASE=independent_entire_system_inventory_and_metadata', flush=True)
        check(sha(BASE_SYSTEM) == BASE_SYSTEM_SHA, 'Actual parent Test5 system differs')
        trees, metas = [], []
        for label, image_path in [('base', BASE_SYSTEM), ('actual', actual_system)]:
            target = folder / (label + '-tree')
            target.mkdir()
            run(['/usr/sbin/debugfs', '-R', 'rdump / ' + str(target), image_path], label + '-rootfs-rdump')
            inventory = tree_inventory(target)
            write_json(folder / (label + '-filesystem.json'), inventory)
            trees.append(inventory)
            metas.append(metadata_inventory(image_path, inventory.keys(), folder, label, run))
        before, after = trees
        old_meta, new_meta = metas
        delta = {'added': sorted(after.keys() - before.keys()), 'removed': sorted(before.keys() - after.keys()),
                 'changed': sorted(path for path in before.keys() & after.keys() if before[path] != after[path])}
        check(delta == prep['expected_delta'], 'Actual whole-filesystem delta differs from exact reviewed preparation')
        for path, item in prep['payloads'].items():
            actual = after[path]
            node_kind = payload_kind(item['kind'])
            # rdump creates host symlinks whose mode is always 0777; ownership,
            # permissions and labels are checked against the actual ext4 inode.
            check(actual['kind'] == node_kind, 'Actual node kind differs: ' + path)
            check(new_meta[path] == {key: (node_kind if key == 'kind' else item[key])
                                    for key in ('kind', 'mode', 'uid', 'gid', 'selinux')},
                  'Actual ext4 ownership/SELinux metadata differs: ' + path)
            if node_kind == 'file':
                check(actual['sha256'] == item['sha256'] and actual['bytes'] == item['bytes']
                      and production['installed_files'][path] == {'sha256': actual['sha256'], 'bytes': actual['bytes']},
                      'Actual payload differs from same-build production artifact: ' + path)
            elif node_kind == 'link':
                check(actual['target'] == item['target'], 'Actual symlink target differs: ' + path)
        for path in before.keys() & after.keys() - prep['payloads'].keys():
            check(old_meta[path] == new_meta[path], 'Unreviewed filesystem metadata change: ' + path)
        for path in BOOT_FILES:
            check(after[path]['kind'] == 'file' and production['installed_files'][path] == {
                'sha256': after[path]['sha256'], 'bytes': after[path]['bytes']},
                'Actual dual-ABI/shared boot artifact differs from production receipt: ' + path)
            check(old_meta[path] == new_meta[path], 'Boot image filesystem metadata changed: ' + path)
        for path, target in BOOT_LINKS.items():
            check(after[path]['kind'] == before[path]['kind'] == 'link'
                  and after[path]['target'] == before[path]['target'] == target
                  and old_meta[path] == new_meta[path], 'Shared VDEX symlink topology/metadata changed: ' + path)
        runtime_closure = verify_runtime_closure(after, production)
        for path, value in PROTECTED.items():
            check(after[path] == before[path] and after[path]['sha256'] == value
                  and old_meta[path] == new_meta[path], 'Inherited system startup/Lid/time/framework resources changed: ' + path)
        run(['/usr/sbin/e2fsck', '-f', '-n', actual_system], 'actual-system-readonly-fsck')
        print('PHASE=inspect_actual_production_APK_and_framework_DEX', flush=True)
        actual_tree = folder / 'actual-tree'
        apk = regular(actual_tree / NAV.lstrip('/'))
        framework = regular(actual_tree / FRAMEWORK.lstrip('/'))
        check(sha(apk) == prep['navigation']['sha256'] and sha(framework) == prep['framework']['sha256'],
              'Actual Android executable payload SHA differs')
        java = NATIVE / 'prebuilts/jdk/jdk9/linux-x86/bin/java'
        signature = run([java, '-Xmx256m', '-jar', sdk / 'lib/apksigner.jar', 'verify',
                         '--min-sdk-version', '29', '--max-sdk-version', '29', '--verbose', '--print-certs', apk],
                        'actual-navigation-signature')
        check(re.findall(r'certificate SHA-256 digest: (\w+)', signature) == [CERT_SHA], 'Actual Navigation production signer differs')
        run([sdk / 'bin/zipalign', '-c', '4', apk], 'actual-navigation-alignment')
        badging = run([sdk / 'bin/aapt', 'dump', 'badging', apk], 'actual-navigation-badging')
        check(re.search(r"package: name='com\.roc\.rgsp\.navtrial' versionCode='18'", badging)
              and "sdkVersion:'29'" in badging and "targetSdkVersion:'29'" in badging
              and re.findall(r"uses-permission: name='([^']+)'", badging) == ['android.permission.EXPAND_STATUS_BAR'],
              'Actual Navigation18 package/version/SDK/permission differs')
        nav_classes, nav_dex = jar_classes(apk, pinned_d8=True)
        framework_classes, framework_dex = jar_classes(framework, hiddenapi=True)
        check(NAV_CLASSES <= nav_classes, 'Actual Navigation DEX omits a reviewed controller class')
        check(set(prep['framework']['required_descriptors']) <= framework_classes,
              'Actual framework DEX omits a defined navigation guard class')
        check(all(sha(Path(path)) == value for path, value in controls.items())
              and all(sha(Path(path)) == value for path, value in lock['controls'].items()),
              'Verification/package source inputs changed while inspecting delivery')
        report.update(passed=True, gzip_sha256=package['sha256'], gzip_bytes=image.stat().st_size,
                      raw_sha256=streamed['sha256'], raw_bytes=streamed['bytes'], ranges=streamed['ranges'], GPT=gpt,
                      prefix=prefix_proof, complete_Test5_prefix_byte_exact=True,
                      vendor_userdata_GPT_unchanged=True, filesystem_delta=delta,
                      entire_filesystem_metadata_nodes_checked=len(new_meta),
                      unchanged_node_metadata_preserved=True, actual_payload_metadata_verified=True,
                      same_production_boot_regular_files_verified=len(BOOT_FILES),
                      entire_runtime_closure=runtime_closure,
                      shared_VDEX_symlinks_preserved=len(BOOT_LINKS), inherited_Lid3_time_defaults_startup_preserved=True,
                      actual_Navigation_sha256=sha(apk), actual_framework_sha256=sha(framework),
                      Navigation_Android10_production_signature_verified=True, Navigation_DEX=nav_dex,
                      framework_DEX=framework_dex, actual_framework_guard_class_definitions=sorted(GUARDS),
                      system_readonly_fsck_passed=True, production_receipt_sha256=sha(production_path),
                      preparation_sha256=args.preparation_sha256, controls=controls,
                      menu_models=12, integrated_models=['rg34xxsp', 'rgsp', 'rg35xxh'],
                      physical_display_and_navigation_acceptance_pending=True)
        print('H700_MANUAL_MODEL_NAVIGATION_TEST6_INDEPENDENT_VERIFICATION_PASS', flush=True)
    except BaseException as error:
        report['failure'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        report['elapsed_seconds'] = time.monotonic() - started
        write_json(destination, report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('work', 'output', 'preparation'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--preparation-sha256', required=True)
    main(parser.parse_args())

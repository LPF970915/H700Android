"""Package a reviewed production Android delta on the byte-exact Test5 card.

This assembler does not build framework/ART, prepare a filesystem, open a card,
mount anything, or operate a device. A separately pinned preparation receipt
must bind the real production outputs to an ordinary prepared system image.
Run only through the existing resource-capped/global-lock wrapper.
"""
from pathlib import Path, PurePosixPath
import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import sys
import time

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained
from package_002 import regular, sha, sparse_copy, range_sha, write_json

NAME = 'ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test6_Navigation_20261115.img'
BASE_DIR = REPO / 'out/roc-os-h700-manual-selector-test5-20261114'
BASE_NAME = 'ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test5_20261114.img'
BASE_RAW = Path('/home/lpf/roc-os-h700-manual-selector-20261114-v3') / BASE_NAME
BASE_SYSTEM = BASE_RAW.parent / 'system.manual.raw'
BASE_GZIP = BASE_DIR / (BASE_NAME + '.gz')
BASE_GZIP_SHA = '5ecd56492aef5bdc834ccd17444e5f5633b5684f4b7af1b49aab5a84d4d5f0ea'
BASE_RAW_SHA = '2baa84207517ebe77e57f2ff7c518dff115a2131a6027602ea3dca718f004002'
BASE_SYSTEM_SHA = '9ccb1d19cd78ecaabffdce16321e509146b45bc4807c38157d471c4616134e6e'
BASE_PREFIX_SHA = '4c83b0066b5f03da3f932aaf5b9628652bbeb5d3c001882a0bfc0356370b8f62'
BASE_ACCEPTANCE_SHA = '6a8e11d8b3cdde4686777e251713720d96d0e6bf6f3c147320a1900f857dca5f'
SOURCE_MANIFEST_SHA = 'c48f7f5dd07c73916ad5b5b10b0c215ab87e254a81453749393a15575761d8b9'
FRAMEWORK_SOURCE_SHA = 'e8110bc34ac032346b2da3fb625799420a72b278cc9e58e7d4b2aadf2b2044b3'
HIDDENAPI_SOURCE_SHA = '23f277953dafbf08e6100692eb06714bbd314ad33a04c8becb817250410a9965'
HIDDENAPI_SOURCE = Path('/home/lpf/h700-android10/android/art/tools/hiddenapi/hiddenapi.cc')
D8_JAR_SHA = '9b6750442852f290e07998e20b09c07d56071dc6190405cad73ecebf64cff396'
D8_JAR = Path('/home/lpf/h700-android10/android/prebuilts/sdk/tools/linux/lib/d8.jar')
SPACE_SHA = '847b55c93f1c0a36983ada5a500d4311b18022ef86b2db2aa3dc5614f0f400d6'
CERT_SHA = 'fc30e834b3c2914a0646d0b46c4faaa045aa8d46189950012555a5f2c36745c9'
RAW_BYTES, SYSTEM_BYTES = 32434554368, 8589934592
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
BOOT_STEMS = ['boot', *('boot-' + name for name in (
    'core-libart', 'okhttp', 'bouncycastle', 'apache-xml', 'framework', 'ext',
    'telephony-common', 'voip-common', 'ims-common', 'android.test.base'))]
BOOT_FILES = {f'/system/framework/{arch}/{stem}.{suffix}'
              for arch in ('arm', 'arm64') for stem in BOOT_STEMS
              for suffix in ('art', 'oat')} | {
              f'/system/framework/{stem}.vdex' for stem in BOOT_STEMS}
RANGES = {'prefix': (0, 222298112), 'system': (222298112, SYSTEM_BYTES),
          'vendor': (8812232704, 2147483648),
          'userdata': (10959716352, 21474836480),
          'backup_gpt': (32434552832, 1536)}
EXPECTED_BASE = {'test5_gzip_sha256': BASE_GZIP_SHA, 'raw_sha256': BASE_RAW_SHA,
                 'system_sha256': BASE_SYSTEM_SHA, 'prefix_sha256': BASE_PREFIX_SHA}


def check(value, message):
    if not value:
        raise ValueError(message)


def digest(value):
    check(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value), 'Invalid SHA256')
    return value


def system_path(name):
    check(isinstance(name, str) and name.startswith('/') and '\\' not in name
          and not any(ord(c) < 32 for c in name) and '"' not in name,
          'Unsafe rootfs path')
    path = PurePosixPath(name)
    check('..' not in path.parts and str(path) == name and name != '/', 'Noncanonical rootfs path')
    return name


def kind(value):
    result = {'regular': 'file', 'symlink': 'link'}.get(value, value)
    check(result in ('file', 'directory', 'link'), 'Unknown rootfs node kind')
    return result


def lid_runtime_path(name):
    match = re.fullmatch(r'/system/(?:(?:product|product_services)/)?(?:app|priv-app)/([^/]+)/(.*)', name)
    return bool(match and 'lid' in match[1].lower() and (
        'oat' in PurePosixPath(match[2]).parts or re.search(r'\.(?:odex|vdex|art|oat)$', match[2])))


def orphan_exclusions(built):
    values = [built[key] for key in ('excluded_orphan_preopt_paths', 'excluded_historical_orphan_preopt_paths')
              if key in built]
    check(values and all(value == values[0] for value in values), 'Missing/inconsistent explicit orphan exclusions')
    paths = values[0]
    check(isinstance(paths, list) and paths == sorted(set(paths))
          and (not paths or set(paths) == KNOWN_ORPHANS), 'Unreviewed historical preopt exclusion')
    check(set(paths) == KNOWN_ORPHANS & built['installed_files'].keys(),
          'Production orphan payloads must match the exact declared exclusions')
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
    if any(re.fullmatch(pattern, name) for pattern in patterns):
        return True
    return node_kind == 'directory' and bool(re.fullmatch(
        r'/system/(?:(?:product|product_services)/)?(?:app|priv-app)/[^/]+/oat(?:/(?:arm|arm64))?', name))


def load_preparation(path, expected_sha):
    """Validate only a pinned interface; no compile-check JAR is accepted here."""
    path = regular(path)
    check(sha(path) == digest(expected_sha), 'Preparation receipt SHA mismatch')
    prep = json.loads(path.read_text())
    check(prep['schema'] == 'roc.h700.navigation-test6.preparation.v1'
          and prep['passed'] is True, 'Incomplete or foreign system preparation')
    check(prep['base'] == EXPECTED_BASE, 'Preparation has another Test5 parent')
    system = regular(Path(prep['system']['path']))
    check(system.is_absolute() and system.stat().st_size == prep['system']['bytes'] == SYSTEM_BYTES,
          'Prepared system path/size mismatch')
    digest(prep['system']['sha256'])
    check(prep['system']['sha256'] != BASE_SYSTEM_SHA, 'Prepared system is unchanged Test5')
    production = prep['production']
    check(production['framework_production_built'] is True and production['boot_images_built'] is True
          and production['architectures'] == ['arm', 'arm64']
          and production['dependent_preopt_strategy'] == 'rebuilt',
          'Real dual-ABI framework/ART production preparation required')
    check(production['source_manifest_sha256'] == SOURCE_MANIFEST_SHA
          and production['framework_source_sha256'] == FRAMEWORK_SOURCE_SHA,
          'Production source identities differ from the reviewed repair')
    production_path = regular(Path(production['receipt_path']))
    check(production_path.is_absolute() and sha(production_path) == digest(production['receipt_sha256']),
          'Production receipt path/SHA mismatch')
    built = json.loads(production_path.read_text())
    check(all(built.get(flag) is True for flag in ('passed', 'framework_production_built', 'boot_images_built')),
          'A real completed production framework/ART build receipt is required')
    check(built['dependent_preopt_strategy'] == 'rebuilt', 'Complete rebuilt runtime closure required')
    check(built['source_manifest_sha256'] == SOURCE_MANIFEST_SHA
          and built['framework_source_sha256'] == FRAMEWORK_SOURCE_SHA,
          'Production receipt used other source')
    check(built['hiddenapi_source_sha256'] == HIDDENAPI_SOURCE_SHA
          and built['framework_dex_postprocessor'] == 'android10-hiddenapi-encode'
          and sha(HIDDENAPI_SOURCE) == HIDDENAPI_SOURCE_SHA,
          'Platform framework must retain the reviewed Android10 hiddenapi production processing')
    check(built['d8_jar_sha256'] == D8_JAR_SHA and sha(D8_JAR) == D8_JAR_SHA,
          'Production Navigation must use the pinned D8 producer')
    installed = built['installed_files']
    check(isinstance(installed, dict) and BOOT_FILES <= installed.keys(),
          'Production receipt must bind all 55 regular boot image artifacts')
    orphan_exclusions(built)
    check(built['boot_artifact_paths'] == sorted(BOOT_FILES),
          'Production boot artifact list differs from the fixed dual-ABI Test5 topology')
    for name, item in installed.items():
        system_path(name)
        digest(item['sha256'])
        check(type(item['bytes']) is int and item['bytes'] >= 0, 'Invalid production file size')
    delta = prep['expected_delta']
    check(set(delta) == {'added', 'removed', 'changed'}, 'Expected delta must have three exact lists')
    flattened = []
    for category, names in delta.items():
        check(isinstance(names, list) and names == sorted(set(names)), 'Unsorted/duplicate delta: ' + category)
        flattened += [system_path(name) for name in names]
    check(len(set(flattened)) == len(flattened) and {NAV, FRAMEWORK} <= set(delta['changed']),
          'Delta overlaps or omits the updated Navigation/framework')
    payloads = prep['payloads']
    check(set(payloads) == set(delta['added']) | set(delta['changed']),
          'Every added/changed node must have one exact reviewed payload')
    for name, item in payloads.items():
        node_kind = kind(item['kind'])
        check(allowed_delta(name, node_kind), 'Unreviewed system change: ' + name)
        check(re.fullmatch(r'0[0-7]{3}', item['mode']) and type(item['uid']) is int
              and type(item['gid']) is int and item['uid'] >= 0 and item['gid'] >= 0
              and isinstance(item['selinux'], str) and item['selinux'].startswith('u:object_r:'),
              'Missing/invalid exact payload metadata: ' + name)
        if node_kind == 'file':
            digest(item['sha256'])
            check(type(item['bytes']) is int and item['bytes'] > 0 and name in installed,
                  'Regular payload absent from production receipt: ' + name)
            check({key: item[key] for key in ('sha256', 'bytes')} == installed[name],
                  'Payload differs from production artifact: ' + name)
        elif node_kind == 'link':
            check(isinstance(item['target'], str) and item['target'] and '\x00' not in item['target'],
                  'Invalid link target')
    for name in delta['removed']:
        check(allowed_delta(name), 'Unreviewed removed system node: ' + name)
    nav, framework = prep['navigation'], prep['framework']
    check(nav['path'] == NAV and nav['version_code'] == 18 and nav['certificate_sha256'] == CERT_SHA
          and nav['sha256'] == payloads[NAV]['sha256'], 'Navigation18 identity mismatch')
    check(framework['path'] == FRAMEWORK and framework['sha256'] == payloads[FRAMEWORK]['sha256'],
          'Production framework.jar identity mismatch')
    descriptors = framework['required_descriptors']
    check(isinstance(descriptors, list) and len(descriptors) == len(set(descriptors))
          and GUARDS <= set(descriptors) and all(re.fullmatch(r'L[^\s;]+;', name) for name in descriptors),
          'The real framework DEX must define both navigation guards')
    return prep, built, system, production_path


def parent_receipts():
    acceptance_path = regular(BASE_DIR / 'acceptance.json')
    check(sha(acceptance_path) == BASE_ACCEPTANCE_SHA, 'Frozen Test5 acceptance changed')
    acceptance = json.loads(acceptance_path.read_text())
    check(acceptance['offline_passed'] is True and acceptance['image']['sha256'] == BASE_GZIP_SHA
          and acceptance['image']['raw_sha256'] == BASE_RAW_SHA, 'Test5 acceptance identity mismatch')
    paths = [acceptance_path]
    for entry in acceptance['evidence']:
        target = regular(REPO / entry['path'])
        check(sha(target) == entry['sha256'], 'Frozen Test5 evidence changed: ' + entry['path'])
        paths.append(target)
    receipt = json.loads(regular(BASE_DIR / 'image-result.json').read_text())
    check(receipt['passed'] is True and receipt['raw_sha256'] == BASE_RAW_SHA
          and receipt['sha256'] == BASE_GZIP_SHA
          and receipt['ranges']['prefix']['sha256'] == BASE_PREFIX_SHA
          and receipt['ranges']['system']['sha256'] == BASE_SYSTEM_SHA,
          'Test5 package receipt identity mismatch')
    return receipt, paths


def main(args):
    constrained()
    started = time.monotonic()
    check(not args.work.exists() and not args.output.exists(), 'Fresh work/output directories required')
    prep, built, system, production_path = load_preparation(args.preparation, args.preparation_sha256)
    parent, parent_paths = parent_receipts()
    manifest, space = REPO / 'build-support/public/source-manifest.json', REPO / 'docs/SPACE_REVIEW_20261028.md'
    check(sha(manifest) == SOURCE_MANIFEST_SHA and sha(space) == SPACE_SHA, 'Reviewed source/protected SPACE_REVIEW changed')
    controls = {str(p): sha(p) for p in [regular(args.preparation), production_path,
                Path(__file__), REPO / 'tools/release/verify_h700_navigation_test6.py',
                REPO / 'tools/release/package_h700_navigation_test6.ps1',
                REPO / 'tools/release/package_002.py', REPO / 'tools/package_h700_v6a.py',
                REPO / 'tools/release/verify_002.py', REPO / 'tools/release/verify_h700_manual_selector.py',
                REPO / 'tools/release/verify_h700_shared_panel.py', HIDDENAPI_SOURCE, D8_JAR, manifest, space, *parent_paths]}
    args.work.mkdir(parents=True)
    args.output.mkdir(parents=True)
    lock = {'schema': 'roc.h700.navigation-test6.package-inputs.v1', 'controls': controls,
            'preparation_path': str(args.preparation.resolve()), 'preparation_sha256': args.preparation_sha256,
            'production_receipt_path': str(production_path), 'production_receipt_sha256': sha(production_path),
            'parent_gzip_sha256': BASE_GZIP_SHA, 'parent_raw_sha256': BASE_RAW_SHA,
            'system_path': str(system), 'system_sha256': prep['system']['sha256']}
    write_json(args.work / 'input-lock.json', lock)
    shutil.copyfile(args.preparation, args.output / 'preparation.json')
    check(sha(args.output / 'preparation.json') == args.preparation_sha256, 'Preparation copy changed')
    raw, image = args.work / NAME, args.output / (NAME + '.gz')
    report = {'schema': 'roc.h700.navigation-test6.package.v1', 'passed': False, 'version': '0.0.2',
              'scope': 'one shared manual-model Test6; exact Test5 startup bytes with production Navigation18/framework/ART system delta',
              'physical_card_written': False, 'device_accessed': False, 'physical_display_accepted': False,
              'all_H700_models_accepted': False, 'automatic_hardware_identity': False,
              'integrated_models': ['rg34xxsp', 'rgsp', 'rg35xxh'], 'menu_models': 12,
              'first_boot_model': 'rg35xxh', 'first_menu_visible_on_all_panels': False,
              'input_lock': str(args.work / 'input-lock.json'), 'input_lock_sha256': sha(args.work / 'input-lock.json')}
    try:
        print('PHASE=verify_frozen_Test5_and_prepared_production_system', flush=True)
        check(sha(BASE_GZIP) == BASE_GZIP_SHA and regular(BASE_RAW).stat().st_size == RAW_BYTES
              and sha(BASE_RAW) == BASE_RAW_SHA, 'Actual frozen Test5 gzip/raw identity mismatch')
        check(sha(system) == prep['system']['sha256'], 'Prepared production system bytes changed')
        print('PHASE=copy_Test5_and_replace_system_only', flush=True)
        sparse_copy(BASE_RAW, raw)
        with raw.open('r+b') as writer, system.open('rb') as reader:
            writer.seek(RANGES['system'][0])
            shutil.copyfileobj(reader, writer, 4 * 1024**2)
            writer.flush()
            os.fsync(writer.fileno())
        ranges = {}
        for name, (offset, length) in RANGES.items():
            actual = range_sha(raw, offset, length)
            expected = prep['system']['sha256'] if name == 'system' else parent['ranges'][name]['sha256']
            check(actual == expected, 'Unexpected full-card range delta: ' + name)
            ranges[name] = {'offset': offset, 'bytes': length, 'sha256': actual,
                            'base_sha256': parent['ranges'][name]['sha256']}
        check(raw.stat().st_size == RAW_BYTES and ranges['prefix']['sha256'] == BASE_PREFIX_SHA,
              'Test5 startup prefix/card length changed')
        print('PHASE=compress_complete_Test6_and_read_back_gzip', flush=True)
        raw_digest = hashlib.sha256()
        with raw.open('rb') as reader, image.open('xb') as writer:
            with gzip.GzipFile(filename='', fileobj=writer, mode='wb', mtime=0, compresslevel=6) as stream:
                while block := reader.read(4 * 1024**2):
                    raw_digest.update(block)
                    stream.write(block)
            writer.flush()
            os.fsync(writer.fileno())
        with gzip.open(image, 'rb') as reader:
            check(hashlib.file_digest(reader, 'sha256').hexdigest() == raw_digest.hexdigest(), 'Complete gzip readback mismatch')
        check(sha(system) == prep['system']['sha256'] and all(sha(Path(p)) == value for p, value in controls.items()),
              'Preparation/production/source controls changed during packaging')
        report.update(passed=True, image=str(image), bytes=image.stat().st_size, sha256=sha(image),
                      raw=str(raw), raw_bytes=RAW_BYTES, raw_sha256=raw_digest.hexdigest(), ranges=ranges,
                      work=str(args.work), system=str(system), preparation_sha256=args.preparation_sha256,
                      production_receipt_sha256=sha(production_path), navigation_sha256=prep['navigation']['sha256'],
                      framework_sha256=prep['framework']['sha256'], framework_source_sha256=FRAMEWORK_SOURCE_SHA,
                      filesystem_delta=prep['expected_delta'], Test5_complete_prefix_byte_exact=True,
                      vendor_userdata_GPT_unchanged=True, existing_production_signer_retained=True,
                      framework_production_built=True, boot_images_built=True, Android_full_rebuild_performed=False,
                      independent_actual_gzip_filesystem_acceptance_pending=True)
        (args.output / (NAME + '.gz.sha256')).write_text(report['sha256'] + '  ' + NAME + '.gz\n', encoding='ascii')
        print(json.dumps({'passed': True, 'image': str(image), 'sha256': report['sha256']}), flush=True)
    except BaseException as error:
        report['failure'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        report['elapsed_seconds'] = time.monotonic() - started
        write_json(args.output / 'image-result.json', report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('work', 'output', 'preparation'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--preparation-sha256', required=True)
    main(parser.parse_args())

"""Merge the verified production Java runtime closure onto the exact Test5 system.

No device access or mounts. Run after the real build and artifact audit, inside
the ordinary resource-capped global-lock wrapper. The original Test5 boot chain
and its model-aware lid, USB, time and release configuration remain the base.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tools/release'))
from package_h700_v6a import constrained
from package_002 import (debugfs, extract_tree, install, metadata, regular, run,
                         sha, sparse_copy, tree_delta, tree_inventory, write_json)

BUILD = Path('/home/lpf/roc-os-navigation-test6-build-20261115-v1')
DELIVERY = ROOT / 'out/nav-test6-production-20261115'
BASE_WORK = Path('/home/lpf/roc-os-h700-manual-selector-20261114-v3')
BASE = BASE_WORK / 'system.manual.raw'
MANIFEST_SHA = 'c48f7f5dd07c73916ad5b5b10b0c215ab87e254a81453749393a15575761d8b9'
FRAMEWORK_SHA = 'e8110bc34ac032346b2da3fb625799420a72b278cc9e58e7d4b2aadf2b2044b3'
BASE_SHA = '9ccb1d19cd78ecaabffdce16321e509146b45bc4807c38157d471c4616134e6e'
CERT = 'fc30e834b3c2914a0646d0b46c4faaa045aa8d46189950012555a5f2c36745c9'
NAV = '/system/app/ROCNavigation/ROCNavigation.apk'
FRAMEWORK = '/system/framework/framework.jar'
LID = '/system/priv-app/ROCReleaseLid/'
PROFILE_FILES = {'/system/etc/boot-image.prof', '/system/framework/framework.jar.prof',
                 '/system/framework/org.apache.http.legacy.jar.prof',
                 '/system/framework/services.rocsource.jar.prof',
                 '/system/framework/wifi-service.rocsource.jar.prof'}
GUARDS = ['Landroid/view/ViewRootImpl$RocDpadKeyGuard;',
          'Landroid/view/ViewRootImpl$RocJoystickGuard;']
CAMERA = '/system/product/app/Camera2/Camera2.apk'
CAMERA_BEFORE_SHA = '0966043654f91066331d87f50dc213ba596538981b1461de9ebf4d39772df9c9'
CAMERA_AFTER_SHA = '2799ea03e41f0d2b2e7a6469f2daf11afe2022083b15838563ab32801c477985'


def check(condition, reason):
    if not condition:
        raise ValueError(reason)


def read(path):
    return json.loads(regular(path).read_text())


def signature(row):
    return {k: v for k, v in row.items() if k != 'mode'}


def bind_art_audit(audit, directory, inventory):
    check(audit['system_tree'] == str(directory.resolve())
          and audit['source_manifest_sha256'] == MANIFEST_SHA
          and audit['framework_source_sha256'] == FRAMEWORK_SHA,
          'ART audit belongs to a different runtime tree or source')
    expected = {}
    for name, row in inventory.items():
        if row['kind'] == 'file':
            expected['/system' + name] = {key: row[key] for key in ('kind', 'sha256', 'bytes')}
        elif row['kind'] == 'link':
            expected['/system' + name] = {key: row[key] for key in ('kind', 'target')}
    check(audit['installed_files'] == expected, 'ART audit payload map differs from the actual runtime tree')
    check(len(audit['boot_artifact_paths']) == 55
          and set(audit['boot_artifact_paths']) <= expected.keys(), 'ART audit boot inventory is incomplete')


def preopt(name):
    return bool(re.fullmatch(
        r'/system/(?:framework/oat/(?:arm|arm64)/[^/]+|'
        r'(?:(?:product|product_services)/)?(?:app|priv-app)/[^/]+/oat/(?:arm|arm64)/[^/]+)'
        r'\.(?:odex|vdex|art)', name))


def reviewed_camera_build_version_drift(controls):
    """Retain Test5 APK: only the HAS_BUILD_NUMBER type bit changed, not DEX.

    Its new preopt remains valid for the retained identical DEX; the final ART
    audit verifies the actual retained APK against that preopt again.
    """
    paths = [BUILD / phase / CAMERA.lstrip('/') for phase in ('before', 'after')]
    check([sha(path) for path in paths] == [CAMERA_BEFORE_SHA, CAMERA_AFTER_SHA],
          'Unreviewed Camera2 build drift')
    with zipfile.ZipFile(paths[0]) as before, zipfile.ZipFile(paths[1]) as after:
        names = before.namelist()
        check(len(names) == len(set(names)) and set(names) == set(after.namelist()),
              'Camera2 archive membership changed')
        changed = sorted(name for name in names if before.read(name) != after.read(name))
        check(changed == ['AndroidManifest.xml', 'META-INF/CERT.RSA',
                          'META-INF/CERT.SF', 'META-INF/MANIFEST.MF'],
              'Camera2 changed executable code or resources')
        dex = {name: hashlib.sha256(before.read(name)).hexdigest()
               for name in names if name.endswith('.dex')}
        check(bool(dex), 'Retained Camera2 has no executable DEX')
    aapt = Path('/home/lpf/h700-android10/android/prebuilts/sdk/tools/linux/bin/aapt')
    controls[str(aapt)] = sha(aapt)
    manifests = [run([aapt, 'dump', 'xmltree', path, 'AndroidManifest.xml']) for path in paths]
    lines = [re.findall(r'^.*android:versionCode.*$', text, re.M) for text in manifests]
    check(len(lines[0]) == len(lines[1]) == 1
          and lines[0][0].endswith('0x13134d0') and lines[1][0].endswith('0x1313534')
          and manifests[0].replace(lines[0][0], lines[1][0]) == manifests[1],
          'Camera2 manifest changed outside the reviewed versionCode')
    return {'path': CAMERA, 'retained_Test5_sha256': CAMERA_BEFORE_SHA,
            'production_sha256': CAMERA_AFTER_SHA, 'identical_dex_sha256': dex,
            'only_manifest_versionCode_changed': [20002000, 20002100],
            'new_production_APK_copied': False, 'final_ART_revalidation_required': True}


def apply_metadata(image, name, meta, work):
    prefix = {'regular': '010', 'directory': '004', 'symlink': '012'}[meta['kind']]
    for field, value in [('mode', prefix + meta['mode']), ('uid', meta['uid']), ('gid', meta['gid'])]:
        debugfs(image, f'set_inode_field {name} {field} {value}', True)
    label = work / 'selinux-label.bin'
    label.write_bytes(meta['selinux'].encode() + b'\0')
    debugfs(image, f'ea_set -f {label} {name} security.selinux', True)
    check(metadata(image, name) == meta, 'Metadata installation mismatch: ' + name)


def main(args):
    constrained()
    start = time.monotonic()
    check(not args.work.exists() and not args.output.exists(), 'Use fresh integration paths')
    check(sha(args.art_audit) == args.art_audit_sha256, 'Production ART audit changed')
    audit = read(args.art_audit)
    check(audit.get('passed') is True and audit.get('phase') == 'production',
          'Production ART audit has not passed')
    built = read(DELIVERY / 'build-result.json')
    check(built['passed'] is True and built['compile_exit_status'] == 0
          and built['source_manifest_sha256'] == MANIFEST_SHA
          and built['framework_source_sha256'] == FRAMEWORK_SHA,
          'Real production build has not completed for these sources')
    check(sha(ROOT / 'build-support/public/source-manifest.json') == MANIFEST_SHA, 'Source manifest changed')
    check(sha(BUILD / 'after/system.img') == built['system_image_sha256'], 'Frozen production image changed')
    after_host = tree_inventory(BUILD / 'after/system')
    check(after_host == read(BUILD / 'after/system-tree.json'), 'Frozen production tree changed')
    bind_art_audit(audit, BUILD / 'after/system', after_host)
    before_host = read(BUILD / 'before/system-tree.json')
    installed_rows = read(BUILD / 'after/installed-files.json')
    installed = {row['Name']: {'sha256': row['SHA256'], 'bytes': row['Size']}
                 for row in installed_rows}
    check(len(installed) == len(installed_rows), 'Duplicate official installed-files names')
    check(set(installed) == {'/system' + name for name, row in after_host.items()
                             if row['kind'] in ('file', 'link')},
          'Official installed-files has missing or extra payload names')
    for name, row in after_host.items():
        if row['kind'] == 'file':
            check(installed.get('/system' + name) == {k: row[k] for k in ('sha256', 'bytes')},
                  'Official installed-files mismatches the built tree: ' + name)
        elif row['kind'] == 'link':
            target = row['target'].encode('utf-8')
            check(installed['/system' + name] == {'sha256': hashlib.sha256(target).hexdigest(),
                                                 'bytes': len(target)},
                  'Official installed-files mismatches the built symlink: ' + name)

    args.work.mkdir(parents=True)
    args.output.mkdir(parents=True)
    report = {'passed': False, 'schema': 'roc.h700.navigation-test6.integration.v1',
              'device_accessed': False, 'physical_card_written': False,
              'all_H700_models_accepted': False}
    try:
        controls = {str(p): sha(p) for p in [Path(__file__), args.art_audit,
                    DELIVERY / 'build-result.json', DELIVERY / 'input-lock.json',
                    BUILD / 'after/system-tree.json', BUILD / 'after/installed-files.json',
                    BUILD / 'after/filesystem-delta.json',
                    ROOT / 'tools/release/package_002.py',
                    ROOT / 'tools/release/audit_navigation_test6_art.py',
                    ROOT / 'tools/release/run_navigation_test6_stage.ps1',
                    ROOT / 'tools/release/package_h700_navigation_test6.py',
                    ROOT / 'tools/release/verify_h700_navigation_test6.py']}
        print('PHASE=verify_Test5_and_actual_production_system', flush=True)
        check(BASE.stat().st_size == 8589934592 and sha(BASE) == BASE_SHA, 'Test5 system identity changed')
        base_tree = extract_tree(BASE, args.work / 'base-tree')
        base_system = {name: row for name, row in base_tree.items() if name.startswith('/system/')}
        old = {'/system' + name: row for name, row in before_host.items()}
        baseline_delta = {
            'added': sorted(base_system.keys() - old.keys()),
            'removed': sorted(old.keys() - base_system.keys()),
            'changed': sorted(name for name in old.keys() & base_system.keys()
                              if signature(old[name]) != signature(base_system[name]))}
        check(baseline_delta == {
            'added': ['/system/product/overlay/ROCTimeDefaults.apk'],
            'removed': sorted([f'/system/{kind}/{app}/oat/arm64/{app}.{suffix}'
                               for kind, app in [('app', 'ROCNavigation'), ('priv-app', 'ROCReleaseLid')]
                               for suffix in ('odex', 'vdex')]),
            'changed': sorted([NAV, '/system/build.prop', LID + 'ROCReleaseLid.apk',
                               '/system/etc/init/h700-usb-configfs.rc'])},
              'Test5 differs from archived pre-build system outside the known retained fixes')
        write_json(args.output / 'retained-Test5-delta.json', baseline_delta)

        candidate_raw = args.work / 'production-system.raw'
        simg = Path('/home/lpf/roc-os-user-20261104/out/host/linux-x86/bin/simg2img')
        controls[str(simg)] = sha(simg)
        run([simg, BUILD / 'after/system.img', candidate_raw])
        check(candidate_raw.stat().st_size == 8589934592, 'Production system size changed')
        (args.output / 'production-fsck.txt').write_text(run(['/usr/sbin/e2fsck', '-f', '-n', candidate_raw]))
        candidate_tree = extract_tree(candidate_raw, args.work / 'production-tree')
        actual = {name: signature(row) for name, row in candidate_tree.items() if name.startswith('/system/')}
        check(actual == {'/system' + name: signature(row) for name, row in after_host.items()},
              'The actual production image differs from its frozen installation tree')

        boot_files = sorted(name for name, row in candidate_tree.items()
                            if row['kind'] == 'file' and re.fullmatch(
                                r'/system/framework/(?:(?:arm|arm64)/boot(?:-[\w.-]+)?\.(?:art|oat)|boot(?:-[\w.-]+)?\.vdex)', name))
        boot_links = sorted(name for name, row in candidate_tree.items()
                            if row['kind'] == 'link' and re.fullmatch(
                                r'/system/framework/(?:arm|arm64)/boot(?:-[\w.-]+)?\.vdex', name))
        check(len(boot_files) == 55 and len(boot_links) == 22
              and boot_files == audit['boot_artifact_paths']
              and boot_links == audit['boot_artifact_link_paths'],
              'Unexpected dual-ABI boot image closure')
        excluded_orphans = set(audit.get('excluded_orphan_preopt_paths', []))
        known_orphans = {f'/system/priv-app/ROCProvisioning/oat/arm64/ROCProvisioning.{suffix}'
                         for suffix in ('odex', 'vdex')}
        check(not excluded_orphans or excluded_orphans == known_orphans,
              'Unreviewed production preopt exclusion')
        for name in excluded_orphans:
            check(signature(candidate_tree[name]) == signature(old[name])
                  and '/system/priv-app/ROCProvisioning/ROCProvisioning.apk' not in candidate_tree,
                  'Historical orphan differs from the archived pre-build payload: ' + name)
        if excluded_orphans:
            check('/system/priv-app/ROCReleaseProvisioning/ROCReleaseProvisioning.apk' in candidate_tree,
                  'Current provisioning APK is absent')
        selected = set(boot_files + boot_links) | {NAV, FRAMEWORK}
        selected |= {name for name in candidate_tree if preopt(name) and not name.startswith(LID)
                     and name not in excluded_orphans}
        check(set(audit['profile_paths']) <= PROFILE_FILES, 'Unknown runtime profile path needs review')
        selected |= set(audit['profile_paths'])
        # All existing preopt files must come from this graph. Lid3 deliberately
        # remains without preopt because its APK differs from the old source.
        removed = sorted(name for name in base_tree if preopt(name) and not name.startswith(LID)
                         and (name not in candidate_tree or name in excluded_orphans))
        check(not any(name.startswith(LID) and preopt(name) for name in base_tree), 'Test5 has unexpected Lid preopt')
        check(NAV in installed and FRAMEWORK in installed, 'Missing new production core payload')
        all_source_changes = tree_delta(before_host, after_host)
        check(all_source_changes == read(BUILD / 'after/filesystem-delta.json'),
              'Stored production delta differs from the actual before/after trees')
        camera_drift = reviewed_camera_build_version_drift(controls)
        unexplained = []
        for category, names in all_source_changes.items():
            for relative in names:
                name = '/system' + relative
                if category == 'changed' and name == CAMERA:
                    continue
                if name in selected or preopt(name) or name in PROFILE_FILES:
                    continue
                if candidate_tree.get(name, {}).get('kind') == 'directory' and (
                        '/oat' in name or name == '/system/app/ROCNavigation'):
                    continue
                unexplained.append((category, name))
        check(not unexplained, 'Unrelated production changes require review: ' + str(unexplained))

        system = args.work / 'system.navigation.raw'
        sparse_copy(BASE, system)
        for name in removed:
            debugfs(system, 'rm ' + name, True)
        # Create only the parent directories needed by newly generated files.
        required_dirs = set()
        for name in selected:
            parent = Path(name).parent.as_posix()
            while parent not in base_tree and parent not in ('/', '.'):
                required_dirs.add(parent)
                parent = Path(parent).parent.as_posix()
        for name in sorted(required_dirs, key=lambda item: (item.count('/'), item)):
            check(candidate_tree[name]['kind'] == 'directory', 'Missing production parent directory: ' + name)
            debugfs(system, 'mkdir ' + name, True)
            apply_metadata(system, name, metadata(candidate_raw, name), args.work)

        print('PHASE=merge_complete_same_graph_Java_runtime_closure', flush=True)
        for name in sorted(selected):
            row = candidate_tree[name]
            previous = base_tree.get(name)
            if previous is not None and row == previous:
                continue
            meta = metadata(candidate_raw, name)
            if previous is not None:
                check(metadata(BASE, name) == meta, 'Production metadata unexpectedly changed: ' + name)
            if row['kind'] == 'file':
                check(installed.get(name) == {k: row[k] for k in ('sha256', 'bytes')},
                      'Merge payload is not from actual installed-files: ' + name)
                install(system, args.work / 'production-tree' / name.lstrip('/'), name, meta,
                        args.work, replace=previous is not None)
            elif row['kind'] == 'link':
                if previous is not None:
                    debugfs(system, 'rm ' + name, True)
                check(not any(c.isspace() for c in row['target']), 'Unsafe symlink target')
                debugfs(system, f"symlink {name} {row['target']}", True)
                apply_metadata(system, name, meta, args.work)
            else:
                raise ValueError('Unexpected selected runtime node: ' + name)
        (args.output / 'final-fsck.txt').write_text(run(['/usr/sbin/e2fsck', '-f', '-n', system]))
        final = extract_tree(system, args.work / 'final-tree')
        delta = tree_delta(base_tree, final)
        check(delta['removed'] == removed, 'Unexpected removed node')
        check(set(delta['added']) <= selected | required_dirs and set(delta['changed']) <= selected,
              'Merged filesystem has unreviewed changes')
        for name in selected:
            check(final[name] == candidate_tree[name], 'Final runtime payload differs from its production graph: ' + name)
        for name in base_tree.keys() - selected - set(removed):
            check(final[name] == base_tree[name], 'Retained Test5 node changed: ' + name)
        write_json(args.output / 'filesystem-delta.json', delta)
        write_json(args.output / 'final-filesystem.json', final)
        payloads = {}
        for name in delta['added'] + delta['changed']:
            row = final[name]
            meta = metadata(system, name)
            payloads[name] = {**meta, **{k: v for k, v in row.items() if k not in ('mode', 'kind')}}
        # The final independent ART audit is deliberately a separate phase.
        # Preparation is emitted only after that proof is supplied to finalize.
        report.update(passed=True, prepared_system=str(system), system_sha256=sha(system),
                      final_tree=str(args.work / 'final-tree/system'), filesystem_delta=delta,
                      payloads=payloads, installed_files=installed, boot_artifact_paths=boot_files,
                      selected_runtime_paths=sorted(selected), retained_Test5_delta=baseline_delta,
                      excluded_historical_orphan_preopt_paths=sorted(excluded_orphans),
                      retained_Camera2_build_version_drift=camera_drift,
                      controls=controls, production_art_audit=str(args.art_audit),
                      production_art_audit_sha256=args.art_audit_sha256,
                      elapsed_seconds=time.monotonic() - start,
                      final_art_audit_pending=True)
        check(all(sha(Path(path)) == value for path, value in controls.items()), 'Integration controls changed')
    except BaseException as error:
        report['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        write_json(args.output / 'integration.json', report)


def finalize(args):
    constrained()
    integration = read(args.output / 'integration.json')
    check(integration['passed'] is True and integration['final_art_audit_pending'] is True,
          'Integration is incomplete or already finalized')
    check(sha(args.art_audit) == args.art_audit_sha256, 'Final ART audit changed')
    final_audit = read(args.art_audit)
    production_audit = read(Path(integration['production_art_audit']))
    check(final_audit.get('passed') is True and final_audit.get('phase') == 'integrated'
          and production_audit.get('passed') is True and production_audit.get('phase') == 'production',
          'Both actual runtime trees require passing artifact audits')
    check(sha(Path(integration['production_art_audit'])) == integration['production_art_audit_sha256'],
          'Production ART proof changed')
    check(all(sha(Path(path)) == value for path, value in integration['controls'].items()),
          'Integration controls changed')
    system = regular(Path(integration['prepared_system']))
    check(system.stat().st_size == 8589934592 and sha(system) == integration['system_sha256'],
          'Integrated system changed after its tree and ART audit')
    final = read(args.output / 'final-filesystem.json')
    check(tree_inventory(Path(integration['final_tree']).parent) == final,
          'Audited final extracted tree changed')
    final_system_inventory = {name[len('/system'):]: row for name, row in final.items()
                              if name.startswith('/system/')}
    bind_art_audit(final_audit, Path(integration['final_tree']), final_system_inventory)
    check(final_audit['production_audit_sha256'] == integration['production_art_audit_sha256'],
          'Final ART audit belongs to another production proof')
    provenance_path = Path('/home/lpf/roc-os-user-20261104/out/ROC_NAVIGATION_TEST6_CACHE_PROVENANCE.json')
    provenance = read(provenance_path)
    check(provenance['passed'] is True and provenance['source_manifest_sha256'] == MANIFEST_SHA,
          'Shared cache provenance changed')
    nav_sha, framework_sha = final[NAV]['sha256'], final[FRAMEWORK]['sha256']
    production = {
        'schema': 'roc.h700.navigation-test6.production.v1', 'passed': True,
        'framework_production_built': True, 'boot_images_built': True,
        'source_manifest_sha256': MANIFEST_SHA, 'framework_source_sha256': FRAMEWORK_SHA,
        'hiddenapi_source_sha256': '23f277953dafbf08e6100692eb06714bbd314ad33a04c8becb817250410a9965',
        'framework_dex_postprocessor': 'android10-hiddenapi-encode',
        'd8_jar_sha256': '9b6750442852f290e07998e20b09c07d56071dc6190405cad73ecebf64cff396',
        'architectures': ['arm', 'arm64'], 'dependent_preopt_strategy': 'rebuilt',
        'framework_sha256': framework_sha, 'navigation_sha256': nav_sha,
        'installed_files': integration['installed_files'],
        'boot_artifact_paths': integration['boot_artifact_paths'],
        'build_receipt': {'path': str(DELIVERY / 'build-result.json'),
                          'sha256': sha(DELIVERY / 'build-result.json')},
        'production_art_audit': {'path': integration['production_art_audit'],
                                 'sha256': integration['production_art_audit_sha256']},
        'final_art_audit': {'path': str(args.art_audit), 'sha256': args.art_audit_sha256},
        'final_runtime_audit_repeated': True, 'retained_Test5_model_lid_without_preopt': True,
        'excluded_historical_orphan_preopt_paths': integration['excluded_historical_orphan_preopt_paths'],
        'Native_source_written': False, 'device_accessed': False,
        'physical_runtime_accepted': False,
        'integration_receipt_sha256': sha(args.output / 'integration.json')}
    production_path = args.output / 'production.json'
    check(not production_path.exists() and not (args.output / 'preparation.json').exists(),
          'Final receipts already exist; preserve them')
    write_json(production_path, production)
    prep = {
        'schema': 'roc.h700.navigation-test6.preparation.v1', 'passed': True,
        'base': {'test5_gzip_sha256': '5ecd56492aef5bdc834ccd17444e5f5633b5684f4b7af1b49aab5a84d4d5f0ea',
                 'raw_sha256': '2baa84207517ebe77e57f2ff7c518dff115a2131a6027602ea3dca718f004002',
                 'system_sha256': BASE_SHA,
                 'prefix_sha256': '4c83b0066b5f03da3f932aaf5b9628652bbeb5d3c001882a0bfc0356370b8f62'},
        'system': {'path': str(system), 'bytes': system.stat().st_size, 'sha256': integration['system_sha256']},
        'production': {'receipt_path': str(production_path), 'receipt_sha256': sha(production_path),
                       'source_manifest_sha256': MANIFEST_SHA, 'framework_source_sha256': FRAMEWORK_SHA,
                       'framework_production_built': True, 'boot_images_built': True,
                       'architectures': ['arm', 'arm64'], 'dependent_preopt_strategy': 'rebuilt'},
        'navigation': {'path': NAV, 'sha256': nav_sha, 'version_code': 18, 'certificate_sha256': CERT},
        'framework': {'path': FRAMEWORK, 'sha256': framework_sha, 'required_descriptors': GUARDS},
        'expected_delta': integration['filesystem_delta'], 'payloads': integration['payloads']}
    write_json(args.output / 'preparation.json', prep)
    provenance.update(framework_production_built=True, boot_images_built=True,
                      artifact_verification_pending=False,
                      production_artifact_receipt=str(production_path),
                      production_artifact_receipt_sha256=sha(production_path),
                      original_source_restored_but_cache_is_fixed_revision=True,
                      previous_source_receipts_historical=True)
    write_json(provenance_path, provenance)
    print('PREPARATION_SHA256=' + sha(args.output / 'preparation.json'), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'finalize'])
    parser.add_argument('--art-audit', type=Path, required=True)
    parser.add_argument('--art-audit-sha256', required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    {'prepare': main, 'finalize': finalize}[args.phase](args)

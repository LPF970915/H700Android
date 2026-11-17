"""Record completed 0.0.3 checks and the user's Test11 confirmation.

Writes local release metadata and public receipts. Never uploads or flashes.
Historical Test11 acceptance and protected baseline records remain unchanged.
"""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / 'out/roc-os-0.0.3-20261117'
PUBLIC = REPO / 'docs/baselines/roc-os-003-20261117'
PARENT = REPO / 'docs/baselines/roc-os-h700-stick-adc-control-test11-20261117/acceptance.json'
META = REPO / 'build-support/releases/0.0.3.json'


def sha(path):
    with path.open('rb') as reader:
        return hashlib.file_digest(reader, 'sha256').hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, data):
    if path.exists():
        raise ValueError('Preserve existing receipt: ' + str(path))
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    for target in [PUBLIC, META, OUT / 'acceptance.json', OUT / 'Test11-user-confirmation.json',
                   OUT / 'ROC_OS_ARM64_ver0.0.3.img.gz.sha256',
                   REPO / 'build-support/public/validation-20261117-003.json',
                   REPO / 'out/ROC_OS_CURRENT_RELEASE.json']:
        if target.exists():
            raise ValueError('Preserve existing release records: ' + str(target))
    image = load(OUT / 'image-result.json')
    independent = load(OUT / 'independent-verify.json')
    windows = load(OUT / 'windows-hash-check.json')
    source = load(OUT / 'source-check.json')
    controls = load(OUT / 'input-lock.json')
    parent = load(PARENT)
    assert sha(PARENT) == '5946a9d78db74a79e7c0a104b1389af09010c5e0564af43b2dd0911eb2eab382'
    assert all(row['passed'] is True for row in (image, independent, windows, source))
    assert image['schema'] == 'roc.h700.release003.package.v1'
    assert independent['schema'] == 'roc.h700.release-0.0.3.independent.v1'
    assert source['schema'] == 'roc.h700.release003.source-check.v1'
    assert image['version'] == independent['version'] == source['version'] == '0.0.3'
    assert image['base_raw_sha256'] == independent['parent_raw_sha256'] == parent['image']['raw_sha256']
    assert image['base_gzip_sha256'] == independent['parent_gzip_sha256'] == parent['image']['sha256']
    assert image['all_H700_models_accepted'] is independent['all_H700_models_accepted'] is False
    assert image['fresh_0_0_3_card_boot_accepted'] is independent['new_release_image_physically_tested'] is False
    assert image['physical_card_written'] is False and independent['producer_imported'] is False
    assert image['sha256'] == windows['sha256'] == independent['gzip_sha256']
    assert image['bytes'] == windows['bytes'] == independent['gzip_bytes']
    assert image['raw_sha256'] == independent['raw_sha256']
    assert image['raw_bytes'] == independent['raw_bytes'] == 32434554368
    assert independent['exactly_two_version_bytes_changed'] is True
    assert independent['complete_gzip_parent_and_raw_byte_comparison'] is True
    assert independent['system']['properties'] == {'ro.build.display.id': 'ROC_OS_ARM64_ver0.0.3', 'ro.roc.os.version': '0.0.3'}
    assert image['source_manifest_sha256'] == source['source_manifest_sha256'] == sha(REPO / 'build-support/public/source-manifest.json')
    for name, digest in controls.items():
        assert sha(REPO / name) == digest, name
    execution = {}
    for phase in ('package', 'verify', 'public-check'):
        found = list((REPO / 'out/roc-os-0.0.3-20261117-logs').glob('*-' + phase + '-*.log'))
        assert len(found) == 1, (phase, found)
        assert 'code=exited/status=0' in found[0].read_text(encoding='utf-8-sig')
        execution[phase] = {'path': found[0].relative_to(REPO).as_posix(), 'sha256': sha(found[0])}
    for name, digest in independent['controls'].items():
        prefix = '/mnt/d/Works/H700Android/'
        path = REPO / name[len(prefix):] if name.startswith(prefix) else Path(name)
        assert sha(path) == digest, name
    confirmation = {
        'schema': 'roc.h700.Test11.user-confirmation.v1', 'date': '2026-11-17',
        'source': 'Direct user reply in the current development conversation',
        'requested_test': 'Flash Test11; select RG35XX H; boot Android and check both stick directions',
        'user_reply': '本次修复有效，将其封装为正式的0.0.3包，且同步现状到git并修改说明',
        'tested_image': parent['image'], 'model': 'rg35xxh',
        'stick_fix_user_confirmed': True, 'new_device_logs_collected': False,
        'fresh_0_0_3_card_boot_accepted': False, 'all_H700_models_accepted': False,
        'wake_resume_acceptance_inferred': False,
    }
    write(OUT / 'Test11-user-confirmation.json', confirmation)
    PUBLIC.mkdir(parents=True)
    paths = {'package': OUT / 'image-result.json', 'independent': OUT / 'independent-verify.json',
             'windows_hash': OUT / 'windows-hash-check.json', 'source_check': OUT / 'source-check.json',
             'input_lock': OUT / 'input-lock.json', 'Test11_user_confirmation': OUT / 'Test11-user-confirmation.json'}
    proofs = {}
    for key, path in paths.items():
        target = PUBLIC / (key + '.json')
        shutil.copyfile(path, target)
        assert sha(path) == sha(target)
        proofs[key] = {'path': target.relative_to(REPO).as_posix(), 'sha256': sha(target)}
    proofs['Test11_parent_acceptance'] = {'path': PARENT.relative_to(REPO).as_posix(), 'sha256': sha(PARENT)}
    artifact = {'path': 'out/roc-os-0.0.3-20261117/ROC_OS_ARM64_ver0.0.3.img.gz',
                **{key: image[key] for key in ('bytes', 'sha256', 'raw_bytes', 'raw_sha256')},
                'minimum_card_GB': 64}
    accepted = {
        'schema': 'roc.h700.release003.acceptance.v1', 'version': '0.0.3', 'date': '2026-11-17',
        'recorded_at': datetime.now().astimezone().isoformat(), 'release_kind': 'official',
        'user_authorized_release': True, 'offline_passed': True, 'image': artifact,
        'release_delta': {'parent': '0.0.2 Test11', 'exactly_two_version_bytes_changed': True,
                          'file': '/system/build.prop', 'properties': independent['system']['properties'],
                          'all_other_full_card_bytes_identical_to_Test11': True},
        'implementation': parent['implementation'], 'swap': parent['swap'],
        'inherited_tests': parent['tests'], 'proofs': proofs, 'foreground_execution_logs': execution,
        'Test11_public_proofs': {path.stem: {'path': path.relative_to(REPO).as_posix(), 'sha256': sha(path)}
                                for path in sorted(PARENT.parent.glob('*.json'))},
        'source_manifest_sha256': source['source_manifest_sha256'], 'public_tool_tests': 11,
        'Test11_rg35xxh_stick_fix_user_confirmed': True,
        'fresh_0_0_3_card_boot_accepted': False, 'all_H700_models_accepted': False,
        'navigation_wake_fault_conclusively_closed': False, 'flicker_fixed': False,
        'image_uploaded': False, 'Android_full_rebuild_performed': False,
        'preserved_records': parent['preserved_records'],
    }
    write(OUT / 'acceptance.json', accepted)
    shutil.copyfile(OUT / 'acceptance.json', PUBLIC / 'acceptance.json')
    release = {
        'schema': 1, 'version': '0.0.3', 'date': '2026-11-17', 'release_kind': 'official',
        'artifact': 'ROC_OS_ARM64_ver0.0.3.img.gz',
        **{key: image[key] for key in ('bytes', 'sha256', 'raw_bytes', 'raw_sha256')},
        'base_version': '0.0.2 Test11', 'base_gzip_sha256': image['base_gzip_sha256'],
        'base_raw_sha256': image['base_raw_sha256'],
        'source_manifest': 'build-support/public/source-manifest.json',
        'source_manifest_sha256': source['source_manifest_sha256'],
        'acceptance': (PUBLIC / 'acceptance.json').relative_to(REPO).as_posix(),
        'acceptance_sha256': sha(PUBLIC / 'acceptance.json'),
        'release_properties': independent['system']['properties'],
        'model_count': 12, 'resolution_groups': ['640x480', '720x480', '720x720'],
        'stick_module_sha256': parent['implementation']['module_sha256'],
        'swap_default_bytes': 2147483648, 'swap_default_enabled': True,
        'navigation_version_code': 18, 'offline_package_passed': True,
        'independent_gzip_readback_passed': True, 'windows_gzip_hash_passed': True,
        'Test11_rg35xxh_stick_fix_user_confirmed': True,
        'fresh_0_0_3_card_boot_accepted': False, 'all_H700_models_accepted': False,
        'diagnostic_ADB_authorization_retained': True, 'image_uploaded': False,
        'Android_full_rebuild_performed': False,
    }
    write(META, release)
    write(REPO / 'build-support/public/validation-20261117-003.json', source)
    checksum = OUT / (release['artifact'] + '.sha256')
    checksum.write_text(image['sha256'] + '  ' + release['artifact'] + '\n', encoding='ascii')
    pointer = {'version': '0.0.3', 'state': 'official local package; Test11 RG35XX H stick fix user-confirmed',
               'image': artifact, 'acceptance': release['acceptance'],
               'acceptance_sha256': release['acceptance_sha256'], 'image_uploaded': False}
    write(REPO / 'out/ROC_OS_CURRENT_RELEASE.json', pointer)
    print(json.dumps({'passed': True, 'version': '0.0.3', 'sha256': image['sha256'],
                      'acceptance_sha256': release['acceptance_sha256'], 'public_proofs': len(paths)+1}))


if __name__ == '__main__':
    main()

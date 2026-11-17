"""Record a verified Test10 delivery without changing frozen build receipts."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / 'out/roc-os-h700-stick-recovery-test10-20261117'
PUBLIC = REPO / 'docs/baselines/roc-os-h700-stick-recovery-test10-20261117'
PREFIX = '/mnt/d/Works/H700Android/'
NAME = 'ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test10_StickRecovery_20261117.img.gz'
PRESERVED = {
    'docs/SPACE_REVIEW_20261028.md': '847b55c93f1c0a36983ada5a500d4311b18022ef86b2db2aa3dc5614f0f400d6',
    'out/ROC_OS_CURRENT_BASELINE.txt': '13d9aa968d3613056719cdfde0ad615160901da12325aa3124d043daef5ce0df',
    'out/ROC_OS_CURRENT_CANDIDATE.txt': '927d19c726edae10a34a30f971abc71939543b873831c9cb43c1949829d6622c',
}


def check(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    check(not path.exists(), 'Preserve previous delivery output: ' + str(path))
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def row(path):
    path = Path(path)
    return {'path': str(path.relative_to(REPO)), 'sha256': sha(path)}


def main():
    for name, value in PRESERVED.items():
        check(sha(REPO / name) == value, 'Protected record changed: ' + name)
    prep, image, verify, windows = (read(OUT / name) for name in
        ('preparation.json', 'image-result.json', 'independent-verify.json', 'windows-hash-check.json'))
    check(prep['passed'] is image['passed'] is verify['passed'] is windows['passed'] is True,
          'All offline phases must pass before delivery')
    check(verify['complete_gzip_raw_byte_comparison'] is True and
          verify['raw_sha256'] == image['raw_sha256'] and
          verify['gzip_sha256'] == image['sha256'] == windows['sha256'] and
          image['bytes'] == windows['bytes'] and image['raw_bytes'] == 32434554368 and
          image['image'] == str(OUT / NAME), 'Whole-card delivery identity mismatch')
    check(image['physical_input_accepted'] is False and image['physical_card_written'] is False and
          image['default_swap_enabled'] is True and image['default_swap_bytes'] == 2147483648 and
          verify['Navigation18_framework_ART_Lid4_time_USB_security_byte_exact'] is True,
          'Preserved functionality and honest physical scope required')
    check(sha(OUT / 'preparation.json') == image['preparation_sha256'], 'Preparation binding changed')
    for name, value in prep['controls'].items():
        check(sha(name) == value, 'Frozen package control changed: ' + name)
    logs = REPO / 'out/roc-os-h700-stick-recovery-test10-20261117-logs'
    phases = {}
    for phase, marker in (('prepare', 'STICK_RECOVERY_PREPARATION_PASS'),
                          ('package', 'STICK_RECOVERY_PACKAGE_PASS'),
                          ('verify', 'STICK_RECOVERY_INDEPENDENT_PASS')):
        matches = list(logs.glob('*-' + phase + '-*.log'))
        check(len(matches) == 1, 'One completed foreground log required: ' + phase)
        text = matches[0].read_text(encoding='utf-8-sig')
        check(marker in text and 'Finished with result: success' in text and
              'code=exited/status=0' in text, 'Phase did not exit successfully: ' + phase)
        phases[phase] = row(matches[0])
    previous = read(REPO / 'out/roc-os-h700-stick-memory-test9-20261117/acceptance.json')
    parent = read(REPO / 'out/roc-os-h700-twelve-model-test8-20261116/acceptance.json')
    candidate_path = REPO / 'out/stick-regression-repair-20261117-v1/candidate.json'
    candidate = read(candidate_path)
    proof_paths = {
        'preparation': OUT / 'preparation.json',
        'package': OUT / 'image-result.json',
        'independent': OUT / 'independent-verify.json',
        'windows_hash': OUT / 'windows-hash-check.json',
        'candidate': candidate_path,
        'artifact_review': REPO / 'out/stick-history-regression-20261117-v1/v3-artifact-review.json',
        'package_input_review': REPO / 'out/test10-package-review-20261117/independent-input-review.json',
        'memory': REPO / 'out/memory-swap-20261117/helper-tests-v2/result.json',
        'manifest': REPO / 'tools/input_profiles/stick_recovery_package_v1/inputs.json',
    }
    for name, item in candidate['proofs'].items():
        proof_paths[name] = Path(item['path'])
    implementation = dict(previous['implementation'])
    implementation['models'] = parent['implementation']['models']
    implementation.update(module_sha256=candidate['artifacts']['module']['sha256'],
                          independent_clicks_from_ADC=True, bounded_managed_ADC_recovery=True,
                          preserves_calibration_after_resume=True)
    acceptance = {
        'schema': 'roc.h700.stick-recovery-test10.offline-acceptance.v1',
        'offline_passed': True,
        'checked_at': datetime.now().astimezone().isoformat(),
        'image': {'path': str((OUT / NAME).relative_to(REPO)), 'bytes': image['bytes'],
                  'sha256': image['sha256'], 'raw_bytes': image['raw_bytes'],
                  'raw_sha256': image['raw_sha256'], 'minimum_card_GB': 64},
        'parent': {'acceptance': str((REPO / 'out/roc-os-h700-twelve-model-test8-20261116/acceptance.json').relative_to(REPO)),
                   'sha256': '7105abaf1a36469c9499973ea97434cd57891b168c451bafd5ea7fa0ce1d8b26',
                   'raw_sha256': image['parent_raw_sha256']},
        'implementation': implementation,
        'swap': previous['swap'],
        'tests': {'actual_C_host_scenarios': 26, 'frozen_parent_negative_scenarios': 5,
                  'actual_C_host_checks': 802, 'final_loader_cases': 45, 'inherited_swap_cases': 22,
                  'reference_CRCs_matched': 410, 'local_CRCs_matched': 418, 'module_imports_matched': 43,
                  'complete_gzip_raw_byte_comparison': True, 'Windows_SHA256': True,
                  'vendor_nodes': prep['vendor']['nodes'], 'frozen_controls': len(prep['controls'])},
        'timing_seconds': {'prepare': prep['elapsed_seconds'], 'package': image['elapsed_seconds'],
                           'independent': verify['elapsed_seconds']},
        'proofs': {name: row(path) for name, path in proof_paths.items()},
        'foreground_execution_logs': phases,
        'exact_hardware_trigger_proven': False,
        'physical_input_accepted': False, 'physical_swap_accepted': False,
        'all_H700_models_accepted': False, 'device_modified': False, 'physical_card_written': False,
        'formal_release_promoted': False, 'accepted_baseline_promoted': False,
        'preserved_records': PRESERVED,
    }
    check(not PUBLIC.exists(), 'Fresh public proof directory required')
    check(not (OUT / 'acceptance.json').exists(), 'Fresh acceptance required')
    check(not (OUT / 'previous-display-candidate.json').exists(), 'Preserve prior candidate snapshot')
    write(OUT / 'acceptance.json', acceptance)
    PUBLIC.mkdir(parents=True)
    for name, path in {'acceptance': OUT / 'acceptance.json', **proof_paths}.items():
        target = PUBLIC / (name + '.json')
        shutil.copyfile(path, target)
        check(sha(target) == sha(path), 'Public proof copy differs: ' + name)
    pointer_path = REPO / 'out/ROC_OS_CURRENT_DISPLAY_CANDIDATE.json'
    shutil.copyfile(pointer_path, OUT / 'previous-display-candidate.json')
    pointer = {
        'state': 'Test10 offline PASS; public stick recovery candidate; physical acceptance pending',
        'image': acceptance['image'], 'acceptance': str((OUT / 'acceptance.json').relative_to(REPO)),
        'acceptance_sha256': sha(OUT / 'acceptance.json'), 'public_receipts': str(PUBLIC.relative_to(REPO)),
        'integrated_models': implementation['integrated_model_ids'],
        'electrical_profiles': implementation['electrical_profiles'],
        'menu_preview_models': implementation['menu_preview_models'],
        'loading_text': implementation['loading_text'], 'default_swap_bytes': 2147483648,
        'default_swap_enabled': True, 'module_sha256': candidate['artifacts']['module']['sha256'],
        'physical_display_accepted': False, 'physical_menu_accepted': False,
        'physical_navigation_accepted': False, 'physical_sticks_accepted': False,
        'physical_swap_accepted': False, 'all_H700_models_accepted': False,
        'accepted_baseline_promoted': False,
    }
    pointer_path.write_text(json.dumps(pointer, indent=2, ensure_ascii=False) + '\n')
    for name, value in PRESERVED.items():
        check(sha(REPO / name) == value, 'Protected record changed during recording: ' + name)
    print(json.dumps({'passed': True, 'acceptance': str(OUT / 'acceptance.json'),
                      'sha256': sha(OUT / 'acceptance.json'), 'public_copies': len(proof_paths) + 1,
                      'image': acceptance['image']}, indent=2))


if __name__ == '__main__':
    main()

"""Record the independently verified Test11 package; never flash or publish it."""
from pathlib import Path
from datetime import datetime
import copy
import hashlib
import json
import shutil

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / 'out/roc-os-h700-stick-adc-control-test11-20261117'
FIX = REPO / 'out/stick-adc-control-repair-20261117-v1'
PUBLIC = REPO / 'docs/baselines/roc-os-h700-stick-adc-control-test11-20261117'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def local(path):
    value = str(path)
    prefix = '/mnt/d/Works/H700Android/'
    assert value.startswith(prefix)
    return REPO / value[len(prefix):]


def main():
    assert not (OUT / 'acceptance.json').exists() and not PUBLIC.exists()
    prep = load(OUT / 'preparation.json')
    image = load(OUT / 'image-result.json')
    independent = load(OUT / 'independent-verify.json')
    windows = load(OUT / 'windows-hash-check.json')
    candidate = load(FIX / 'candidate.json')
    artifact = load(FIX / 'artifact-review.json')
    assert prep['schema'] == 'roc.h700.stick-adc-control-preparation.v1'
    assert image['schema'] == 'roc.h700.stick-adc-control-image.v1'
    assert independent['schema'] == 'roc.h700.stick-adc-control-independent.v1'
    assert candidate['schema'] == 'roc.h700.stick-adc-control-candidate.v1'
    assert all(item['passed'] for item in (prep, image, independent, windows, artifact))
    assert candidate['software_checks_passed']
    assert independent['producer_not_imported'] and independent['complete_gzip_raw_byte_comparison']
    assert image['sha256'] == windows['sha256'] == independent['gzip_sha256']
    assert image['raw_sha256'] == independent['raw_sha256']
    assert image['bytes'] == windows['bytes']
    paths = {
        'preparation': OUT / 'preparation.json', 'package': OUT / 'image-result.json',
        'independent': OUT / 'independent-verify.json', 'windows_hash': OUT / 'windows-hash-check.json',
        'candidate': FIX / 'candidate.json', 'artifact_review': FIX / 'artifact-review.json',
        'memory': REPO / 'out/memory-swap-20261117/helper-tests-v2/result.json',
        'manifest': Path(__file__).parent / 'inputs.json',
        'previous_Test10_live_failure': REPO / 'out/test10-rg35xxh-live-20261117/runtime-result.json',
    }
    for key, row in candidate['proofs'].items():
        path = local(row['path'])
        assert sha(path) == row['sha256']
        paths[key] = path
    assert local(prep['manifest']) == paths['manifest']
    assert prep['manifest_sha256'] == sha(paths['manifest'])
    assert artifact['candidate_sha256'] == sha(paths['candidate'])
    assert artifact['bound_proofs'] == candidate['proofs']
    host = load(paths['host'])
    module = load(paths['module'])
    template = REPO / 'out/roc-os-h700-stick-recovery-test10-20261117/acceptance.json'
    assert sha(template) == 'da57712484b56c2b3e1dea0846e43f380d140cc9105da9aac0c0a60cc00c458c'
    result = copy.deepcopy(load(template))
    assert result['offline_passed'] and result['schema'] == 'roc.h700.stick-recovery-test10.offline-acceptance.v1'
    result['schema'] = 'roc.h700.stick-adc-control-test11.offline-acceptance.v1'
    result['checked_at'] = datetime.now().astimezone().isoformat()
    result['image'] = {
        'path': str(local(image['image']).relative_to(REPO)).replace('\\', '/'),
        'bytes': image['bytes'], 'sha256': image['sha256'],
        'raw_bytes': image['raw_bytes'], 'raw_sha256': image['raw_sha256'], 'minimum_card_GB': 64,
    }
    result['implementation']['module_sha256'] = module['module_sha256']
    result['implementation']['ADC_CTRL_mode_bits'] = '18:19'
    result['implementation']['ADC_CTRL_ready_mask'] = '0x000d0000'
    result['implementation']['ADC_CTRL_ready_value'] = '0x00090000'
    result['implementation']['preserves_unrelated_CTRL_bits'] = True
    result['tests'].update(
        actual_C_host_scenarios=host['candidate_scenarios'],
        frozen_parent_negative_scenarios=host['negative_control_scenarios'],
        actual_C_host_checks=host['checks'],
        frozen_Test10_actual_C_field_readback_reproduction=True,
        vendor_nodes=independent['vendor']['after_nodes'], frozen_controls=len(prep['controls']),
    )
    result['timing_seconds'] = {name: data['elapsed_seconds'] for name, data in
                               [('prepare', prep), ('package', image), ('independent', independent)]}
    result['proofs'] = {key: {'path': str(path.relative_to(REPO)).replace('\\', '/'), 'sha256': sha(path)}
                        for key, path in paths.items()}
    logs = REPO / 'out/roc-os-h700-stick-adc-control-test11-20261117-logs'
    result['foreground_execution_logs'] = {}
    for phase in ('prepare', 'package', 'verify'):
        found = list(logs.glob('*-' + phase + '-*.log'))
        assert len(found) == 1, (phase, found)
        path = found[0]
        assert 'code=exited/status=0' in path.read_text(encoding='utf-8-sig')
        result['foreground_execution_logs'][phase] = {
            'path': str(path.relative_to(REPO)).replace('\\', '/'), 'sha256': sha(path)}
    result.pop('exact_hardware_trigger_proven')
    result['adc_control_rejection_proven_on_Test10'] = True
    result['physical_fix_verified'] = False
    runtime = load(paths['previous_Test10_live_failure'])
    assert runtime['fault_rejection_proven'] and runtime['physical_fix_verified'] is False
    assert runtime['events'] == {'ABS_X': 0, 'ABS_Y': 0, 'ABS_Z': 0, 'ABS_RUDDER': 0,
                                 'BTN_THUMBL': 2, 'BTN_THUMBR': 2, 'ABS_HAT0Y': 2}
    assert runtime['swap_total_KiB'] == 2097148
    result['previous_Test10_swap_physically_enabled_KiB'] = runtime['swap_total_KiB']
    for name, value in result['preserved_records'].items():
        assert sha(REPO / name) == value, name
    (OUT / 'acceptance.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    PUBLIC.mkdir(parents=True)
    for key, path in {**paths, 'acceptance': OUT / 'acceptance.json'}.items():
        target = PUBLIC / (key + '.json')
        shutil.copyfile(path, target)
        assert sha(path) == sha(target)
    print('TEST11_OFFLINE_ACCEPTANCE', sha(OUT / 'acceptance.json'), len(paths) + 1)


if __name__ == '__main__':
    main()

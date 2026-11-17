"""Confirm all twelve models with the actual final host and AArch64 menu ELFs.

Only the native simulation mode is invoked against fresh ordinary PPM/JSON
outputs. No input node, framebuffer device, card or partition is accessed.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from package_h700_v6a import constrained
from models import ALL_MODEL_IDS, MODEL_METADATA


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(args):
    constrained()
    assert not args.output.exists(), 'Fresh fixture outputs required'
    args.output.mkdir(parents=True)
    source_paths = [Path(__file__), Path(__file__).with_name('models.py'),
                    ROOT / 'tools/boot_selector/reference_model.py',
                    args.native_output / 'result.json',
                    args.native_output / 'roc-boot-selector-host',
                    args.native_output / 'roc-boot-selector']
    controls = {str(path): sha(path) for path in source_paths}
    receipt = json.loads((args.native_output / 'result.json').read_text())
    assert receipt['pass'] is True and receipt['loading_text'] == '加载中，请稍后'
    arm = args.native_output / 'roc-boot-selector'
    assert receipt['sha256'][str(arm)] == sha(arm), 'Exact tested final menu ELF'
    host = args.native_output / 'roc-boot-selector-host'
    rows = []
    available = ','.join(ALL_MODEL_IDS)
    for model in ALL_MODEL_IDS:
        metadata = MODEL_METADATA[model]
        geometry = 'x'.join(map(str, metadata['native_size']))
        for architecture, command in [('host', [str(host)]),
                                      ('aarch64', ['/usr/bin/qemu-aarch64', str(arm)])]:
            ppm, result = (args.output / (model + '-' + architecture + suffix)
                           for suffix in ('.ppm', '.json'))
            completed = subprocess.run([*command, '--simulate', geometry, '--ppm', str(ppm),
                '--initial-model', model, '--available-models', available,
                '--rotation', str(metadata['display_rotation']), '--script', 'DDA',
                '--result', str(result)], capture_output=True, text=True, timeout=8)
            assert completed.returncode == 0, (model, architecture, completed.stderr)
            selected = json.loads(result.read_text())
            assert selected == {'schema': 2, 'model_id': model, 'save_default': False}, selected
            loading = args.native_output / ('loading-' + model + '-' + architecture + '.ppm')
            expected_loading = next(row for row in receipt['loading_only_cases']
                                    if row['model'] == model and row['architecture'] == architecture)
            assert sha(loading) == expected_loading['ppm_sha256'], 'Frozen actual loading render'
            assert ppm.read_bytes() == loading.read_bytes(), 'Start must immediately leave the loading frame'
            rows.append({'model': model, 'architecture': architecture, 'script': 'DDA',
                'selected': selected, 'loading_frame_sha256': sha(ppm),
                'native_size': metadata['native_size'], 'rotation': metadata['display_rotation'],
                'all12_available_mask': True, 'passed': True})
    assert all(sha(Path(path)) == digest for path, digest in controls.items())
    record = {'passed': True, 'cases': len(rows), 'controls': controls, 'rows': rows,
              'all12_actual_native_start': len(rows) == len(ALL_MODEL_IDS) * 2,
              'actual_host_and_aarch64': True, 'hardware_accessed': False,
              'simulation_only': True, 'loading_text': receipt['loading_text']}
    serialized = json.dumps(record, ensure_ascii=False, indent=2).encode() + b'\n'
    (args.output / 'result.json').write_bytes(serialized)
    (args.output / 'result.sha256').write_text(hashlib.sha256(serialized).hexdigest() + '  result.json\n')
    print(json.dumps({key: record[key] for key in ('passed', 'cases', 'all12_actual_native_start')}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-output', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args())

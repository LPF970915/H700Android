"""Actual-C H700 CTRL tests with frozen-v3/v2 controls; no hardware."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / 'stick_recovery_v3'
LEGACY_V2 = HERE.parent / 'stick_sampling_v2'
NO_STICKS = ('rg34xx', 'rgsp', 'rg35xxplus', 'rg35xx_2025', 'rg28xx', 'rg35xxsp')
CANDIDATE_CASES = [('healthy', model) for model in (
    'rg34xxsp', 'rg35xxh', 'rg40xxh', 'rg40xxv', 'rgcubexx', 'rg35xxpro')]
CANDIDATE_CASES += [(name,) for name in (
    'adc-fault-clicks', 'ccu-fault-clicks', 'recover-disabled', 'recover-mode',
    'recover-selection', 'recover-single-cycle', 'recover-burst',
    'ctrl-readback-fixture', 'live-ctrl-readback',
    'startup-single', 'startup-single-cycle', 'startup-burst', 'startup-disabled',
    'pm-hibernation', 'pm-suspend', 'pm-restore',
    'bounded-fault', 'refuse-selection', 'refuse-adc-owner',
    'refuse-missing-node', 'refuse-lost-claims', 'unstable-success-budget',
    'exit-unrelated-selection', 'exit-unrelated-driver', 'exit-clock-off', 'single')]
CANDIDATE_CASES += [('no-sticks', model) for model in NO_STICKS]
V2_NEGATIVE_CASES = [(name,) for name in (
    'legacy-adc-click-blocked', 'legacy-ccu-click-blocked',
    'legacy-control-not-restored', 'legacy-selection-unchecked',
    'legacy-post-no-reconfigure')]
V3_NEGATIVE_CASES = [('frozen-v3-live-readback-blocked',)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert os.sched_getaffinity(0) <= {0, 1}
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    sources = [HERE / name for name in (
        'h700_stick_axes.c', 'axis_math.h', 'h700_profile_policy.h',
        'h700_profile_table.h', 'Makefile', 'test_kernel_shim.h', 'test_recovery.c',
        'run_host.py', 'parent-inputs.json', 'README.md')]
    for directory in (PARENT, LEGACY_V2):
        sources += [directory / name for name in (
            'h700_stick_axes.c', 'axis_math.h', 'h700_profile_policy.h',
            'h700_profile_table.h', 'test_kernel_shim.h')]
    frozen = {str(path): sha(path) for path in sources}
    parent_manifest = json.loads((HERE / 'parent-inputs.json').read_text())
    assert parent_manifest['schema'] == 'roc.h700.stick-recovery-v4-parent.v1'
    for name, expected in parent_manifest['parent_source_sha256'].items():
        assert sha(PARENT / name) == expected
    assert frozen[str(LEGACY_V2 / 'h700_stick_axes.c')] == '31825f757a4ce95b3c96510db02acb08e3865b1d0467ac0baa634cfc7d164507'
    results = {}
    total = 0
    for role, cases in (
            ('candidate', CANDIDATE_CASES),
            ('frozen_v3_negative', V3_NEGATIVE_CASES),
            ('frozen_v2_negative', V2_NEGATIVE_CASES)):
        binary = output / role
        command = ['gcc', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror',
                   '-Wno-sign-compare', str(HERE / 'test_recovery.c'), '-o', str(binary)]
        if role == 'frozen_v3_negative':
            command.insert(1, '-DDRIVER_SOURCE="' + str(PARENT / 'h700_stick_axes.c') + '"')
        elif role == 'frozen_v2_negative':
            command.insert(1, '-DDRIVER_SOURCE="' + str(LEGACY_V2 / 'h700_stick_axes.c') + '"')
            command.insert(1, '-DH700_LEGACY_V2_FIXTURE=1')
        compiled = subprocess.run(command, text=True, capture_output=True)
        (output / (role + '-compile.txt')).write_text(compiled.stdout + compiled.stderr)
        assert compiled.returncode == 0, compiled.stdout + compiled.stderr
        runs = []
        for case in cases:
            ran = subprocess.run([str(binary), *case], text=True, capture_output=True)
            runs.append({'case': list(case), 'exit_code': ran.returncode,
                         'stdout': ran.stdout, 'stderr': ran.stderr})
            (output / (role + '-' + '-'.join(case) + '.txt')).write_text(ran.stdout + ran.stderr)
            assert ran.returncode == 0, (case, ran.stdout, ran.stderr)
            match = re.search(r'/ (\d+) checks;', ran.stdout)
            assert match
            total += int(match[1])
            print(ran.stdout, end='', flush=True)
        results[role] = {
            'compile_command': command, 'binary_sha256': sha(binary), 'runs': runs,
            'CTRL_bits_8_9_ignored': role != 'frozen_v2_negative',
            'CTRL_mode_field': '18:19' if role != 'frozen_v2_negative' else 'retained old array fixture',
            'fixture': 'H700_real_CTRL_readback' if role != 'frozen_v2_negative' else 'retained_v2_plain_array',
        }
    assert frozen == {str(path): sha(path) for path in sources}
    receipt = {
        'schema': 'roc.h700.stick-recovery-v4-host.v1', 'passed': True,
        'candidate_scenarios': len(CANDIDATE_CASES),
        'negative_control_scenarios': len(V2_NEGATIVE_CASES) + len(V3_NEGATIVE_CASES),
        'frozen_v3_real_readback_scenarios': len(V3_NEGATIVE_CASES),
        'frozen_v2_legacy_fixture_scenarios': len(V2_NEGATIVE_CASES), 'checks': total,
        'source_sha256': {name: frozen[str(HERE / name)] for name in (
            'h700_stick_axes.c', 'axis_math.h', 'h700_profile_policy.h',
            'h700_profile_table.h', 'Makefile')},
        'controls': frozen, 'details': results,
        'actual_candidate_C_executed': True, 'actual_frozen_v3_C_executed': True,
        'actual_frozen_v2_C_executed': True,
        'real_readback_fixture': {
            'CTRL_reserved_write_ignored_mask': '0x00000300',
            'CTRL_mode_mask': '0x000c0000', 'CTRL_continuous': '0x00080000',
            'CTRL_enable': '0x00010000', 'captured_CTRL': '0x00890000',
            'captured_centers': [2092, 2058, 2066, 2036],
            'data_read_requires_continuous_enabled_channel0_and_clock': True,
        },
        'PM_values': {'HIBERNATION_PREPARE': 1, 'POST_HIBERNATION': 2,
                      'SUSPEND_PREPARE': 3, 'POST_SUSPEND': 4,
                      'RESTORE_PREPARE': 5, 'POST_RESTORE': 6},
        'hardware_apis_mocked': True, 'physical_acceptance': False,
        'device_accessed': False, 'kernel_module_built': False,
        'limitations': 'ADC/MMIO/GPIO/time/workqueue/DT are host fixtures. No physical raw data, real IRQ timing, actual suspend, electrical identification or module load is exercised.',
    }
    (output / 'host-result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('HOST_RECEIPT', output / 'host-result.json', flush=True)


if __name__ == '__main__':
    main()

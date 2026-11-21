"""Exercise group boundaries on the compiled picker, state writer and init hook."""

import json
import runpy
import subprocess

from five_panel_menu import GROUPS, GROUP_OF, REPS
from models import MODEL_METADATA
from shared_trials import SOURCE, replace
import test_selector_init_rescue as fixtures


def picker_tests(work, binary):
    command = ['/usr/bin/qemu-aarch64', binary]
    result = json.loads(subprocess.check_output([*command, '--selftest']))
    assert result['pass']
    cases = []
    def select(model, keys, *, blind=False, preview=False, save=False):
        ppm, output = work / 'view.ppm', work / 'native-result.json'
        ppm.unlink(missing_ok=True)
        output.unlink(missing_ok=True)
        meta = MODEL_METADATA[model or 'rg35xxh']
        size = 'x'.join(map(str, meta['native_size']))
        args = ['--simulate', size, '--rotation', str(meta['display_rotation']),
                '--ppm', ppm, '--script', keys, '--output', output]
        if model:
            args += ['--initial-model', model]
        if blind:
            args += ['--blind']
        rc = subprocess.run(command + args, capture_output=True)
        assert rc.returncode == (4 if preview else 0), (model, keys, rc.stderr)
        parsed = json.loads(output.read_bytes())
        assert parsed['schema'] == 2 and parsed['save_default'] is save
        cases.append(dict(initial=model, keys=keys, chosen=parsed['model_id'], blind=blind, preview=preview))
        return parsed['model_id']
    assert select(None, 'DDA') == REPS[0]
    for i, group in enumerate(GROUPS):
        for model in group:
            walks = []
            for direction in 'LR':
                visited = [select(model, direction * j + 'DDA') for j in range(len(group) + 1)]
                assert visited[0] == visited[-1] == model and set(visited[:-1]) == set(group)
                walks.append(visited)
            assert walks[0] == walks[1][::-1]
            assert select(model, 'DADA', save=True) == model
            for key, target in [('N', REPS[(i+1) % 5]), ('P', REPS[i-1])]:
                assert select(model, 'RR' + key, preview=True) == target
                assert select(model, key, preview=True, blind=True) == target
    return dict(selftest=result, cases=cases)


def state_tests(work, binary, seed):
    path = work / 'test20-environment.part'
    path.write_bytes(seed)
    command = ['/usr/bin/qemu-aarch64', binary, '--fixture', path]
    def invoke(*args):
        return subprocess.check_output(command + list(args), text=True)
    def status(saved='', model='', marker=''):
        assert invoke('status').splitlines() == ['saved='+saved, 'next='+model, 'next_start='+marker]
    status()
    for saved in GROUP_OF:
        invoke('save', saved)
        for target in REPS:
            invoke('preview', target)
            status(saved, target, '2')
        invoke('once', saved)
        status(saved, saved, '1')
        invoke('clear-next')
        status(saved)
    snapshot = path.read_bytes()
    for target in set(GROUP_OF) - set(REPS):
        assert subprocess.run(command + ['preview', target], capture_output=True).returncode != 0
    assert path.read_bytes() == snapshot and snapshot[128*1024:] == seed[128*1024:]
    return dict(saved_models=12, previews_read_back=60, invalid_previews_rejected=7)


def hook_tests(work):
    # Reuse the path-isolated Test14 harness and substitute the per-group CLI expectation.
    harness = (SOURCE / 'test_selector_init_rescue.py').read_text()
    all_csv = "'rg34xx,rg34xxsp,rgsp,rgcubexx,rg35xxplus,rg35xx_2025,rg28xx,rg35xxh,rg40xxh,rg40xxv,rg35xxsp,rg35xxpro'"
    harness = replace(harness, "('--available-models'," + all_csv + ")",
                      "('--available-models', config['expected_models'])")
    path = work / 'group-hook-fixtures.py'
    path.write_text(harness)
    run = runpy.run_path(str(path))['run_case']
    run.__globals__['SOURCE'] = work / 'selector-init.sh'
    rows = []
    for i, group in enumerate(GROUPS):
        for active in group:
            lid = str(int(MODEL_METADATA[active]['lid']))
            def case(name, cfg, **kwargs):
                cfg['expected_models'] = ','.join(group)
                row = run(work, name + '-' + active, cfg, model=active, lid=lid, **kwargs)
                rows.append({k: row[k] for k in ('case','actions','returncode','final_environment')})
                return row['final_environment']
            for chosen in group:
                restart = chosen != active or chosen in ('rg34xx','rg40xxv')
                for save in (0, 1):
                    action = 'save' if save else 'once' if restart else 'clear-next'
                    state = case(f'start-{chosen}-{save}', dict(chosen=chosen,save=save),
                                 actions=['status', action], expected_rc=77 if restart else 0)
                    assert state == dict(saved=chosen if save else '', next=chosen if restart and not save else '',
                                         next_start='1' if restart and not save else '')
            for key, target in [('down',REPS[(i+1)%5]), ('up',REPS[i-1])]:
                state = case('preview-'+key, dict(chosen=target,selector_rc=[4],initial_saved='rgsp',
                                    reboot_no_return=True), actions=['status','preview','status'], expected_rc=77)
                assert state == dict(saved='rgsp',next=target,next_start='2')
            for bad in set(GROUP_OF) - set(group):
                # Exit the second fixture picker with an error to prove the first
                # (cross-group) result returned to the picker without a state write.
                state = case('reject-'+bad, dict(chosen=bad,save=1,selector_rc=[0,2]),
                             actions=['status'], selector_count=2, expected_rc=1)
                assert state is None
            for route in ('start_saved','start_once'):
                case(route, {}, route=route, actions=['status','clear-next'], selector_count=0)
    return rows

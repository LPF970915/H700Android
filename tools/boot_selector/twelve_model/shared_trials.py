"""Build the shared 720×480 menu trial from the frozen selector."""

import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

import test_selector_init_rescue as fixtures
from models import MODEL_METADATA

SOURCE = Path(__file__).resolve().parent
ROOT = SOURCE.parents[2]
ASSETS = SOURCE / 'assets'
FROZEN = {
    'selector_rescue.c': '39252acaa97c51b1280ec2d1ec5c500dd1bf9a2ea90ad959754ea002a9616676',
    'selector_init_rescue.sh': '9a61941cab19dc492b364ce0e5baa323eeda1f71a84856cf11d37eb582d380ed',
    'boot_state_preview.c': '45a50bff04b19ee8ef86c740284494d7f35f5ffc77c6f84cf8a13d7fb3b4b368',
}
CYCLE = ('rg35xxh', 'rg34xx', 'rgcubexx')
LEGACY_PREVIEW = 'rg34xxsp'
SH_GROUPS = ('*', 'rg34xx|rg34xxsp|rgsp', 'rgcubexx')


def replace(source, old, new, count=1):
    if source.count(old) != count:
        raise ValueError('Frozen selector anchor did not match: ' + old)
    return source.replace(old, new)


def source_of(name):
    payload = (SOURCE / name).read_bytes()
    if name in FROZEN and hashlib.sha256(payload).hexdigest() != FROZEN[name]:
        raise ValueError('Frozen selector source changed: ' + name)
    return payload.decode('utf-8')


def adjacent(index, direction):
    return CYCLE[(index + direction) % len(CYCLE)]


def group(model):
    return {'640x480': 0, '720x480': 1, '720x720': 2}[MODEL_METADATA[model]['geometry']]


def write_sources(work):
    native = replace(source_of('selector_rescue.c'),
                     '/* Three user-requested trial representatives; normal Start retains all models. */\n'
                     'static const char *preview_cycle[] = {"rg35xxh","rg34xxsp","rgcubexx"};',
                     '/* Menu panel trials; normal Start retains all model choices. */\n'
                     'static const char *preview_cycle[] = {' + ', '.join(json.dumps(x) for x in CYCLE) + '};')
    (work / 'selector.c').write_text(native)
    guard = '||'.join('!strcmp(s,' + json.dumps(model) + ')' for model in (*CYCLE, LEGACY_PREVIEW))
    helper = replace(source_of('boot_state_preview.c'),
                     '!strcmp(s,"rg35xxh")||!strcmp(s,"rg34xxsp")||!strcmp(s,"rgcubexx")', guard)
    helper = helper.replace('a three-panel representative', 'a supported panel representative')
    (work / 'state.c').write_text(helper)
    script = source_of('selector_init_rescue.sh')
    rows = '\n'.join(f'        {SH_GROUPS[index]}) TRIAL_NEXT={adjacent(index, 1)}; '
                     f'TRIAL_PREV={adjacent(index, -1)};;' for index in (1, 2, 0))
    script = replace(script, '''    # Resolve adjacency from the initialized model's logical geometry, never
    # the mutable highlighted choice. Other electrical profiles stay available
    # through the normal twelve-model confirmation route.
    case "$MODEL" in
        rg34xx|rg34xxsp|rgsp) TRIAL_NEXT=rgcubexx; TRIAL_PREV=rg35xxh;;
        rgcubexx) TRIAL_NEXT=rg35xxh; TRIAL_PREV=rg34xxsp;;
        *) TRIAL_NEXT=rg34xxsp; TRIAL_PREV=rgcubexx;;
    esac''', '    # Use the initialized panel, independently of the highlighted model.\n'
                          '    case "$MODEL" in\n' + rows + '\n    esac')
    script = replace(script, '''if [ "$SAVE" = 1 ]; then
    /grow/roc-boot-state --partition "$ENV_DEV" save "$CHOSEN" || exit 1
elif [ "$CHOSEN" != "$MODEL" ]; then''', '''# RG34XX enters Android after a fresh panel initialization, even when its
# profile was already used by the menu.
RESTART=1
if [ "$CHOSEN" = "$MODEL" ] && [ "$CHOSEN" != rg34xx ]; then RESTART=0; fi
if [ "$SAVE" = 1 ]; then
    /grow/roc-boot-state --partition "$ENV_DEV" save "$CHOSEN" || exit 1
elif [ "$RESTART" = 1 ]; then''')
    script = replace(script, '''if [ "$CHOSEN" = "$MODEL" ]; then
    note 'selection matches initialized hardware; continuing to Android'
    exit 0
fi''', '''if [ "$RESTART" = 0 ]; then
    note 'selection matches initialized hardware; continuing to Android'
    exit 0
fi''')
    (work / 'selector-init.sh').write_text(script)


def run(args):
    return subprocess.check_output([str(arg) for arg in args], text=True)


def native_tests(work, host, arm):
    test = replace(source_of('test_native_rescue.py'),
                   "CYCLE = ('rg35xxh', 'rg34xxsp', 'rgcubexx')", 'CYCLE = ' + repr(CYCLE))
    test = replace(test, "'model_id': 'rg34xxsp', 'save_default': False",
                   "'model_id': 'rg34xx', 'save_default': False")
    path = work / 'test_native_shared.py'
    path.write_text(test)
    return runpy.run_path(str(path))['exercise'](host, arm, work / 'native_tests', work / 'fifo')


def state_tests(work, host, arm, environment_partition):
    test = source_of('test_boot_state_preview.py')
    all_previews = (*CYCLE, LEGACY_PREVIEW)
    test = replace(test, '("rg35xxh", "rg34xxsp", "rgcubexx")', repr(all_previews))
    for spacing in (', ', ','):
        old_set = '{' + spacing.join(repr(model) for model in ('rg35xxh', LEGACY_PREVIEW, 'rgcubexx')) + '}'
        test = replace(test, old_set, f'set({all_previews!r})')
    test = replace(test, 'preview-only-three-representatives', 'preview-only-supported-representatives')
    test = replace(test, '        stream.seek(ENV_OFFSET)\n', '')
    test = replace(test, 'for key, value in source_rows]',
                   'for key, value in source_rows if key not in ("roc_selector_schema", "roc_selector_apply")]')
    path = work / 'test_state_shared.py'
    path.write_text(test)
    seed = work / 'test13-environment.part'
    seed.write_bytes(environment_partition)
    receipt = work / 'state_tests.json'
    env = dict(os.environ, PYTHONPATH=str(SOURCE))
    subprocess.run([sys.executable, '-B', str(path),
                    '--prefix', str(seed),
                    '--work', str(work / 'state_fixtures'), '--host', str(host), '--arm', str(arm),
                    '--output', str(receipt)], env=env, check=True, stdout=subprocess.DEVNULL)
    result = json.loads(receipt.read_text())
    if result.get('pass') is not True:
        raise ValueError('Boot-state tests failed')
    return result


def hook_tests(work):
    fixtures.SOURCE = work / 'selector-init.sh'
    root = work / 'hook-fixtures'
    root.mkdir()
    cases = []
    for model, meta in MODEL_METADATA.items():
        lid = str(int(meta['lid']))
        for direction, name in ((1, 'down'), (-1, 'up')):
            target = adjacent(group(model), direction)
            case = fixtures.run_case(root, model + '-' + name,
                                     {'chosen': target, 'selector_rc': [4], 'initial_saved': 'rgsp',
                                      'reboot_no_return': True},
                                     model=model, lid=lid, absent_fb=True, expected_rc=77,
                                     actions=['status', 'preview', 'status'])
            if case['final_environment'] != {'saved': 'rgsp', 'next': target, 'next_start': '2'}:
                raise ValueError('Preview changed the saved model or boot route')
            cases.append(case)
        action = 'once' if model == 'rg34xx' else 'clear-next'
        cases.append(fixtures.run_case(root, model + '-confirm-same', {'chosen': model},
                                       model=model, lid=lid, actions=['status', action],
                                       expected_rc=77 if action == 'once' else 0))
    cases.append(fixtures.run_case(root, '34xx-confirm-saved', {'chosen': 'rg34xx', 'save': 1},
                                  model='rg34xx', lid='0', actions=['status', 'save'], expected_rc=77))
    for active, selected in (('rg34xx', 'rg34xxsp'), ('rg34xx', 'rgsp'), ('rg35xxh', 'rg40xxv')):
        case = fixtures.run_case(root, active + '-select-' + selected, {'chosen': selected},
                                 model=active, lid='0', actions=['status', 'once'], expected_rc=77)
        if case['final_environment']['next'] != selected or case['final_environment']['next_start'] != '1':
            raise ValueError('Model selection did not request its own one-time boot')
        cases.append(case)
    for model in ('rg34xx', 'rg40xxv'):
        cases.append(fixtures.run_case(root, model + '-continue-android', {}, model=model, lid='0',
                                      route='start_once', actions=['status', 'clear-next'], selector_count=0))
    return cases


def build(work, environment_partition):
    work.mkdir(parents=True)
    write_sources(work)
    binaries = {}
    for label, compiler, extra in (('host', '/usr/bin/cc', []),
                                   ('arm', '/usr/bin/aarch64-linux-gnu-gcc', ['-static'])):
        for kind, source in (('selector', 'selector.c'), ('state', 'state.c')):
            target = work / (kind + '-' + label)
            run([compiler, *extra, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                 '-Wno-misleading-indentation', '-fstack-protector-strong', '-D_FORTIFY_SOURCE=2',
                 '-I', ASSETS, work / source, '-o', target])
            binaries[kind, label] = target
    host = binaries['selector', 'host']
    arm = binaries['selector', 'arm']
    host_selftest = json.loads(run([host, '--selftest']))
    if host_selftest != json.loads(run(['/usr/bin/qemu-aarch64', arm, '--selftest'])):
        raise ValueError('Host and actual AArch64 selector selftests differ')
    if host_selftest.get('pass') is not True:
        raise ValueError('Native selector selftest failed')
    native = native_tests(work, host, arm)
    state = state_tests(work, binaries['state', 'host'], binaries['state', 'arm'], environment_partition)
    hooks = hook_tests(work)
    return {
        'grow/roc-boot-selector': arm.read_bytes(),
        'grow/roc-boot-state': binaries['state', 'arm'].read_bytes(),
        'grow/roc-selector-init.sh': (work / 'selector-init.sh').read_bytes(),
    }, {'native': native, 'state': state, 'hook': hooks, 'selftest': host_selftest}

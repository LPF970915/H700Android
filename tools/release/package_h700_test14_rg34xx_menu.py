"""Make a Test14 control image with only the RG34XX 720×480 menu repair."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from package_h700_shared_menu_test16 import (
    BOOT_BYTES, BOOT_OFFSET, CHUNK, ENV_OFFSET, PREFIX_BYTES, REPO,
    constrained, digest, json_write, patch_boot, prove_early, regular, require, sha,
    shared_trials, stream_ranges, verify_gpt,
)
from package_h700_usb_device_test14 import IMAGE as TEST14_IMAGE, boot_proof

PARENT = REPO / 'out/roc-os-h700-usb-gamepad-test14-20261120'
PARENT_SHA = 'a6bea615982ac7893d53383da9d8709fd5db11be039ae263285d5fec3ed60969'
IMAGE = 'ROC_OS_ARM64_ver0.0.3_H700_Test14_RG34XX_720Menu_20261121.img.gz'


def selector_hook():
    replace = shared_trials.replace
    original = shared_trials.source_of('selector_init_rescue.sh')
    first = original.index('    read_status() {')
    last = original.index('    if ! read_status "$INITIAL_STATUS"', first)
    helper = '\n'.join(line.removeprefix('    ') for line in original[first:last].splitlines())
    hook = original[:first] + original[last:]
    hook = replace(hook, 'if [ "$status" = 4 ]; then\n    if [ "$SAVE"',
                   helper + '\nif [ "$status" = 4 ]; then\n    if [ "$SAVE"')
    hook = replace(hook, '    preview_ok=0\n    if /grow/roc-boot-state --partition "$ENV_DEV" preview "$CHOSEN" &&',
                   '''    # Keep the Test14 menu's volume result and adjacency check. Only the
    # accepted 720×480 trial is mapped to the proven RG34XX panel.
    TRIAL_PROFILE=$CHOSEN
    if [ "$TRIAL_PROFILE" = rg34xxsp ]; then TRIAL_PROFILE=rg34xx; fi
    preview_ok=0
    if /grow/roc-boot-state --partition "$ENV_DEV" preview "$TRIAL_PROFILE" &&''')
    hook = replace(hook, '[ "$STATUS_NEXT" = "$CHOSEN" ] && [ "$STATUS_START" = 2 ]',
                   '[ "$STATUS_NEXT" = "$TRIAL_PROFILE" ] && [ "$STATUS_START" = 2 ]')
    hook = replace(hook, '''fi
if [ "$SAVE" = 1 ]; then
    /grow/roc-boot-state --partition "$ENV_DEV" save "$CHOSEN" || exit 1
elif [ "$CHOSEN" != "$MODEL" ]; then''', '''fi
RESTART=0
if [ "$CHOSEN" != "$MODEL" ]; then
    RESTART=1
elif [ "$CHOSEN" = rg34xx ] && read_status "$INITIAL_STATUS" &&
     [ "$STATUS_NEXT" = rg34xx ] && [ "$STATUS_START" = 2 ]; then
    # Test14 normally restarts after confirming 34XX from the 720×480 menu.
    # Reuse that route when the trial has already initialized the 34XX panel.
    RESTART=1
fi
if [ "$SAVE" = 1 ]; then
    /grow/roc-boot-state --partition "$ENV_DEV" save "$CHOSEN" || exit 1
elif [ "$RESTART" = 1 ]; then''')
    return replace(hook, '''if [ "$CHOSEN" = "$MODEL" ]; then
    note 'selection matches initialized hardware; continuing to Android'
    exit 0
fi''', '''if [ "$RESTART" = 0 ]; then
    note 'selection matches initialized hardware; continuing to Android'
    exit 0
fi''')


def build(work, environment):
    work.mkdir(parents=True)
    source = work / 'state.c'
    helper = shared_trials.replace(shared_trials.source_of('boot_state_preview.c'),
                                  '!strcmp(s,"rg34xxsp")', '!strcmp(s,"rg34xxsp")||!strcmp(s,"rg34xx")')
    source.write_text(helper.replace('a three-panel representative', 'a supported panel representative'))
    hook = work / 'selector-init.sh'
    hook.write_text(selector_hook())
    host, arm = work / 'state-host', work / 'state-arm'
    flags = ['-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', source]
    shared_trials.run(['/usr/bin/cc', *flags, '-o', host])
    shared_trials.run(['/usr/bin/aarch64-linux-gnu-gcc', '-static', *flags, '-o', arm])
    state = shared_trials.state_tests(work, host, arm, environment)
    fixtures = shared_trials.fixtures
    fixtures.SOURCE = hook
    cases = []
    run_case = fixtures.run_case
    trial_settings = {'selector_rc': [4], 'reboot_no_return': True, 'initial_saved': 'rgsp'}
    for model, chosen, target in (('rg35xxh', 'rg34xxsp', 'rg34xx'),
                                  ('rg35xxh', 'rgcubexx', 'rgcubexx'),
                                  ('rg34xx', 'rgcubexx', 'rgcubexx'),
                                  ('rg34xx', 'rg35xxh', 'rg35xxh')):
        case = run_case(work, model + '-preview-' + chosen,
                        dict(trial_settings, selection_sequence=[{'chosen': chosen}, {'chosen': target}]),
                        model=model, lid='0', absent_fb=True, expected_rc=77,
                        actions=['status', 'preview', 'status'])
        require(case['final_environment'] == {'saved': 'rgsp', 'next': target, 'next_start': '2'},
                'Incorrect Test14 trial route')
        cases.append(case)
    fixtures.SOURCE = shared_trials.SOURCE / 'selector_init_rescue.sh'
    original_choice = run_case(work, 'test14-original-34xx-choice', {'chosen': 'rg34xx'},
                               actions=['status', 'once'], expected_rc=77)
    fixtures.SOURCE = hook
    from_new_menu = run_case(work, '34xx-confirm-from-repaired-menu',
                             {'chosen': 'rg34xx', 'initial_next': 'rg34xx', 'initial_start': '2'},
                             model='rg34xx', lid='0', actions=['status', 'once'], expected_rc=77)
    require(original_choice['final_environment'] == from_new_menu['final_environment'] ==
            {'saved': '', 'next': 'rg34xx', 'next_start': '1'}, 'Test14 Android route diverged')
    cases.extend([original_choice, from_new_menu])
    cases.append(run_case(work, '34xx-start-once', {}, model='rg34xx', lid='0', route='start_once',
                          actions=['status', 'clear-next'], selector_count=0))
    cases.append(run_case(work, '34xx-saved-reopen-confirm', {'chosen': 'rg34xx', 'initial_saved': 'rg34xx'},
                          model='rg34xx', lid='0', actions=['status', 'clear-next']))
    cases.append(run_case(work, '40xxv-test14-path', {'chosen': 'rg40xxv'}, model='rg35xxh', lid='0',
                          actions=['status', 'once'], expected_rc=77))
    return {'grow/roc-boot-state': arm.read_bytes(), 'grow/roc-selector-init.sh': hook.read_bytes()}, {
        'state': state, 'hook': cases, 'test14_once_matches_repaired_menu_once': True,
    }


def package(work, output):
    constrained()
    parent_image = PARENT / TEST14_IMAGE
    baseline = json.loads((PARENT / 'verify-result.json').read_text())
    require(baseline['passed'] and baseline['image_sha256'] == PARENT_SHA
            and sha(parent_image) == PARENT_SHA, 'Exact verified Test14 gzip required')
    output.mkdir(parents=True)
    with gzip.open(regular(parent_image), 'rb') as reference:
        prefix = reference.read(PREFIX_BYTES)
    require(digest(prefix) == baseline['raw']['ranges']['prefix'], 'Expected the exact Test14 boot prefix')
    env = next(entry for entry in baseline['gpt'] if entry['name'] == 'env')
    require(env['offset'] == ENV_OFFSET and env['bytes'] == 16 * 1024**2, 'Expected Test14 environment')
    replacements, component_tests = build(work, prefix[ENV_OFFSET:ENV_OFFSET + env['bytes']])
    json_write(output / 'component-tests.json', component_tests)
    print('Test14 volume routing and one-time Android entry passed. Checking actual U-Boot.', flush=True)
    boot, changed = patch_boot(prefix[BOOT_OFFSET:BOOT_OFFSET + BOOT_BYTES], replacements)
    candidate = prefix[:BOOT_OFFSET] + boot
    prefix_hash = digest(candidate)
    routes = prove_early(candidate)
    raw_prefix = work / 'candidate-prefix.raw'
    raw_prefix.write_bytes(candidate)
    handoff_cases = boot_proof(raw_prefix, prefix_hash, output / 'handoff')
    image = output / IMAGE
    partial = image.with_suffix('.gz.partial')
    old_digest = hashlib.sha256(prefix)
    print('Packaging the exact Test14 partition data.', flush=True)
    with gzip.open(parent_image, 'rb') as source, partial.open('xb') as file:
        require(digest(source.read(PREFIX_BYTES)) == baseline['raw']['ranges']['prefix'],
                'Test14 prefix changed between reads')
        with gzip.GzipFile(fileobj=file, filename='', mode='wb', compresslevel=1, mtime=0) as writer:
            writer.write(candidate)
            while block := source.read(CHUNK):
                old_digest.update(block)
                writer.write(block)
    require(old_digest.hexdigest() == baseline['raw']['sha256'], 'Parent differs from the verified Test14')
    print('Reading back the complete control image.', flush=True)
    with gzip.open(partial, 'rb') as stream:
        raw = stream_ranges(stream)
    require(raw['ranges'] == dict(baseline['raw']['ranges'], prefix=prefix_hash), 'Unexpected partition delta')
    require(verify_gpt(raw.pop('head'), raw.pop('tail')) == baseline['gpt'], 'GPT changed')
    partial.rename(image)
    image_hash = sha(image)
    (output / (IMAGE + '.sha256')).write_text(f'{image_hash}  {IMAGE}\n', encoding='ascii')
    json_write(output / 'verify-result.json', {
        'passed': True, 'physical_menu_and_flicker_verified': False,
        'image': IMAGE, 'bytes': image.stat().st_size, 'image_sha256': image_hash,
        'parent_gzip_sha256': PARENT_SHA, 'parent_raw_sha256': old_digest.hexdigest(), 'raw': raw,
        'changed_ramdisk_payloads': changed, 'early_routes': routes,
        'test14_once_matches_repaired_menu_once': True, 'usb_peripheral_handoff_cases': handoff_cases,
        'component_tests_sha256': sha(output / 'component-tests.json'),
        'handoff_sha256': sha(output / 'handoff/result.json'),
    })
    print(image_hash, image, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    package(args.work, args.output)

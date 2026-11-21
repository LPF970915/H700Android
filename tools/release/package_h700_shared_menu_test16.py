"""Package one H700 image with a shared 720×480 menu trial."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys

from package_h700_rg34xx_first_menu import (BASE_GZIP, CHUNK, IMAGE as TEST15_IMAGE,
                                           REPO, TEST13_RECEIPT, TEST13_RECEIPT_SHA, constrained)
from package_h700_rg34xx_usb_diagnosis import PARENT as TEST15, PARENT_HASH as TEST15_SHA
from package_h700_twelve_model import repack_ramdisk
from h700_manual_selector_twelve import align, parts
from h700_panel_boot import ENV_OFFSET, ENV_SIZE, decode_env
from rg35xxh_display import BOOT_OFFSET, BOOT_BYTES, PREFIX_BYTES, TOC_OFFSET, TOC_BYTES, read_toc
from verify_002 import json_write, regular, require, sha, stream_ranges, verify_gpt

import early_profile_bridge_rescue as bridge
from models import MODEL_PROFILE, VALUES
import shared_trials
import verify_final_handoff

IMAGE = 'ROC_OS_ARM64_ver0.0.3_H700_Test16_SharedMenu_20261121.img.gz'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def patch_boot(original, replacements):
    components = parts(original)
    ramdisk, changed = repack_ramdisk(components['ramdisk']['data'], replacements)
    updated = bytearray(original[:2048])
    struct.pack_into('<I', updated, 16, len(ramdisk))
    for name in ('kernel', 'ramdisk', 'second', 'dtb'):
        data = ramdisk if name == 'ramdisk' else components[name]['data']
        updated.extend(data)
        updated.extend(bytes(align(len(updated)) - len(updated)))
    require(len(updated) < BOOT_BYTES and original[components['end']:] ==
            b'\xff' * (BOOT_BYTES - components['end']), 'Unexpected boot partition padding')
    updated.extend(b'\xff' * (BOOT_BYTES - len(updated)))
    result = parts(updated)
    for name in ('kernel', 'second', 'dtb'):
        require(result[name]['data'] == components[name]['data'], 'Unrelated boot content changed: ' + name)
    return bytes(updated), changed


def prove_early(prefix):
    toc = prefix[TOC_OFFSET:TOC_OFFSET + TOC_BYTES]
    items = read_toc(toc)['items']
    components = {item['name']: toc[item['offset']:item['offset'] + item['bytes']] for item in items}
    original = regular(bridge.ORIGINAL).read_bytes()
    receipt = json.loads((REPO / 'docs/baselines/roc-os-h700-twelve-model-test8-20261116/'
                          'early-receipt.json').read_text())
    symbols = {key: int(value, 16) for key, value in receipt['symbols'].items()}
    scenarios = [({}, 'rg35xxh', 'selector')]
    for model in (*shared_trials.CYCLE, shared_trials.LEGACY_PREVIEW):
        scenarios.append(({'roc_next_model': model, 'roc_next_start': '2'}, model, 'selector'))
    for model in ('rg34xx', 'rg34xxsp', 'rg40xxv'):
        scenarios.append(({'roc_next_model': model, 'roc_next_start': '1'}, model, 'start_once'))
    cases = []
    for slide in (0, 0x1000000):
        for env, model, route in scenarios:
            result = bridge.execute(original, components['u-boot'], symbols, env=env, slide=slide,
                                    fdt_blob=components['dtb'])
            require(result['r0'] == 0 and result['sets'] == {'roc_active_model': model, 'roc_boot_route': route}
                    and result['profile_values'] == list(VALUES[MODEL_PROFILE[model]])
                    and 'display_after_profile' in result['calls'], 'Early route or LCD profile mismatch')
            cases.append(result)
    return cases


def package(work, output):
    constrained()
    require(sha(TEST13_RECEIPT) == TEST13_RECEIPT_SHA, 'Test13 receipt changed')
    baseline = json.loads(TEST13_RECEIPT.read_text())
    parent_image = TEST15 / TEST15_IMAGE
    require(sha(parent_image) == TEST15_SHA and not output.exists() and not work.exists(),
            'Exact Test15 payload and fresh work/output required')
    output.mkdir(parents=True)
    with gzip.open(regular(BASE_GZIP), 'rb') as reference:
        prefix = reference.read(PREFIX_BYTES)
    require(digest(prefix) == baseline['raw']['ranges']['prefix'], 'Exact Test13 boot prefix required')
    env = dict(decode_env(prefix[ENV_OFFSET:ENV_OFFSET + ENV_SIZE]))
    require(not any(key in env for key in ('roc_saved_model', 'roc_next_model', 'roc_next_start')),
            'Shared image must start with fresh selector state')
    require(env['roc_fdt_addr'] == 'fdt addr ${fdtcontroladdr}', 'Expected runtime FDT handoff')
    env_layout = next(entry for entry in baseline['gpt'] if entry['name'] == 'env')
    require(env_layout['offset'] == ENV_OFFSET and env_layout['bytes'] == 16 * 1024**2,
            'Unexpected Test13 environment partition')
    environment_partition = prefix[ENV_OFFSET:ENV_OFFSET + env_layout['bytes']]
    replacements, component_tests = shared_trials.build(work, environment_partition)
    json_write(output / 'component-tests.json', component_tests)
    print('Native, boot-state and selector-hook tests passed.', flush=True)
    boot, changed = patch_boot(prefix[BOOT_OFFSET:BOOT_OFFSET + BOOT_BYTES], replacements)
    candidate = prefix[:BOOT_OFFSET] + boot
    cases = prove_early(candidate)
    candidate_hash = digest(candidate)
    proof_prefix = work / 'new-prefix.raw'
    proof_prefix.write_bytes(candidate)
    require(verify_final_handoff.main(argparse.Namespace(
        prefix=proof_prefix, prefix_sha256=candidate_hash, output=output / 'handoff')) == 0,
        'Final kernel handoff did not pass')
    print('Actual U-Boot routes passed. Packaging the shared test image.', flush=True)
    image = output / IMAGE
    partial = image.with_suffix('.gz.partial')
    parent = json.loads((TEST15 / 'verify-result.json').read_text())
    with gzip.open(parent_image, 'rb') as source, partial.open('xb') as file:
        require(digest(source.read(PREFIX_BYTES)) == parent['raw']['ranges']['prefix'],
                'Source compressed prefix identity')
        with gzip.GzipFile(fileobj=file, filename='', mode='wb', compresslevel=1, mtime=0) as writer:
            writer.write(candidate)
            while block := source.read(CHUNK):
                writer.write(block)
    print('Reading back the whole shared test image.', flush=True)
    with gzip.open(partial, 'rb') as source:
        raw = stream_ranges(source)
    require(raw['ranges'] == dict(baseline['raw']['ranges'], prefix=candidate_hash),
            'Readback or untouched partition identity failed')
    gpt = verify_gpt(raw.pop('head'), raw.pop('tail'))
    require(gpt == baseline['gpt'], 'GPT changed')
    partial.rename(image)
    image_hash = sha(image)
    (output / (IMAGE + '.sha256')).write_text(f'{image_hash}  {IMAGE}\n', encoding='ascii')
    json_write(output / 'verify-result.json', {
        'passed': True, 'candidate_only': True, 'physical_menu_verified': False,
        'fresh_menu_model': 'rg35xxh', 'volume_down_cycle': list(shared_trials.CYCLE),
        'rg40xxv_uses_common_640_menu': True,
        'rg34xx_restarts_through_one_shot_if_unsaved': True, 'android_bytes_match_test13': True,
        'image': IMAGE, 'bytes': image.stat().st_size, 'image_sha256': image_hash,
        'raw': raw, 'gpt': gpt, 'early_routes': cases, 'changed_ramdisk_payloads': changed,
        'handoff_sha256': sha(output / 'handoff/result.json'),
        'component_tests_sha256': sha(output / 'component-tests.json'),
    })
    print(image_hash, image, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    package(args.work, args.output)

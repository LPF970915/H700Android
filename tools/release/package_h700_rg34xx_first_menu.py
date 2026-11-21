"""Make a Test13-derived diagnostic image that opens the menu on RG34XX."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / 'tools'), str(REPO / 'tools/boot_selector/twelve_model')]

from package_h700_v6a import constrained
from rg35xxh_display import PREFIX_BYTES, TOC_BYTES, TOC_OFFSET, read_toc
from verify_002 import RANGES, json_write, regular, require, sha, stream_ranges, verify_gpt

TEST13_RECEIPT = REPO / 'out/roc-os-h700-gamepad-triggers-test13-20261120/verify-result.json'
TEST13_RECEIPT_SHA = '34a4a9d7d6e04faa2a730499d509669d6759f67e22fdd8a7af44bb9849056037'
BASE_GZIP = REPO / 'out/roc-os-0.0.3-20261117/ROC_OS_ARM64_ver0.0.3.img.gz'
BASE_GZIP_SHA = '34dcf5f43c0a75675530ff9b6c052351985d51b379a6e6189b388f331c6aaa52'
TEST13_SYSTEM = Path('/home/lpf/roc-h700-digital-triggers-image-20261120-v1/test13-from-gzip.raw')
UBOOT_SHA = '226a0e1e972538b408e584346d5e1d108ecb65aea8c45bbf1bdc70f1c067f0cd'
IMAGE = 'ROC_OS_ARM64_ver0.0.3_H700_Test15_RG34XX_FirstMenu_20261121.img.gz'
CHUNK = 8 * 1024**2

# In the pinned early bridge these are the fresh-menu MOVS r5,#1 and
# the string loaded by the preceding ADR. The lookup table is elsewhere.
PATCHES = (
    (0x26514, bytes.fromhex('0125'), bytes.fromhex('0225')),
    (0x26a4e, b'rg35xxh\0', b'rg34xx\0\0'),
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def patch_prefix(prefix):
    toc = prefix[TOC_OFFSET:TOC_OFFSET + TOC_BYTES]
    items = read_toc(toc)
    require(items['bytes'] == TOC_BYTES, 'Unexpected TOC length')
    original = {}
    for item in items['items']:
        start = item['offset']
        original[item['name']] = toc[start:start + item['bytes']]
    uboot = original['u-boot']
    require(digest(uboot) == UBOOT_SHA, 'Unexpected Test13 U-Boot')
    updated = bytearray(toc)
    uboot_offset = next(item['offset'] for item in items['items'] if item['name'] == 'u-boot')
    for offset, before, after in PATCHES:
        require(uboot[offset:offset + len(before)] == before, 'Early-bridge byte identity failed')
        start = uboot_offset + offset
        updated[start:start + len(after)] = after
    struct.pack_into('<I', updated, 20, 0x5f0a6c39)
    checksum = sum(word for word, in struct.iter_unpack('<I', updated)) & 0xffffffff
    struct.pack_into('<I', updated, 20, checksum)
    readback = read_toc(updated)
    for item in readback['items']:
        if item['name'] != 'u-boot':
            start = item['offset']
            require(updated[start:start + item['bytes']] == original[item['name']],
                    'Unexpected TOC component change')
    patched = bytes(updated[uboot_offset:uboot_offset + len(uboot)])
    return prefix[:TOC_OFFSET] + updated + prefix[TOC_OFFSET + TOC_BYTES:], original, patched


def prove_route(parent, patched, control):
    import early_profile_bridge_rescue as bridge
    from models import MODEL_PROFILE, VALUES

    receipt = json.loads((REPO / 'docs/baselines/roc-os-h700-twelve-model-test8-20261116/'
                          'early-receipt.json').read_text())
    symbols = {name: int(value, 16) for name, value in receipt['symbols'].items()}
    original = regular(bridge.ORIGINAL).read_bytes()
    scenarios = (
        ('fresh', {}, 'rg34xx', 'selector'),
        ('saved', {'roc_saved_model': 'rg35xxh'}, 'rg35xxh', 'start_saved'),
        ('once', {'roc_next_model': 'rg34xx', 'roc_next_start': '1'}, 'rg34xx', 'start_once'),
        ('trial', {'roc_next_model': 'rg34xxsp', 'roc_next_start': '2'}, 'rg34xxsp', 'selector'),
        ('invalid', {'roc_next_model': 'bad', 'roc_next_start': '1'}, 'rg34xxsp', 'selector'),
    )
    cases = []
    for slide in (0, 0x1000000):
        for name, env, model, route in scenarios:
            before = bridge.execute(original, parent, symbols, env=env, slide=slide, fdt_blob=control)
            after = bridge.execute(original, patched, symbols, env=env, slide=slide, fdt_blob=control)
            require(after['sets'] == {'roc_active_model': model, 'roc_boot_route': route}
                    and after['profile_values'] == list(VALUES[MODEL_PROFILE[model]])
                    and after['r0'] == 0 and 'display_after_profile' in after['calls'],
                    'Early display route mismatch: ' + name)
            if name == 'fresh':
                require(before['sets']['roc_active_model'] == 'rg35xxh', 'Baseline fresh route mismatch')
            else:
                require(before == after, 'Changed established boot route: ' + name)
            cases.append({'name': name, **after})
    return cases


def package(output):
    constrained()
    require(sha(TEST13_RECEIPT) == TEST13_RECEIPT_SHA and sha(BASE_GZIP) == BASE_GZIP_SHA,
            'Retained Test13 receipt or shared release image changed')
    parent = json.loads(TEST13_RECEIPT.read_text())
    system_size = RANGES['system'][1]
    require(parent['passed'] and regular(TEST13_SYSTEM).stat().st_size == system_size,
            'Expected verified Test13 system partition')
    output.mkdir(parents=True)
    packed = output / IMAGE
    partial = packed.with_suffix('.gz.partial')
    with gzip.open(BASE_GZIP, 'rb') as source:
        prefix = source.read(PREFIX_BYTES)
        require(len(prefix) == PREFIX_BYTES and digest(prefix) == parent['raw']['ranges']['prefix'],
                'Exact Test13 prefix required')
        candidate, old, new = patch_prefix(prefix)
        cases = prove_route(old['u-boot'], new, old['dtb'])
        print('Early U-Boot proof passed. Packaging and hashing the exact Test13 parent.', flush=True)
        exact_parent = hashlib.sha256(prefix)
        changed_image = hashlib.sha256(candidate)
        with regular(TEST13_SYSTEM).open('rb') as system, partial.open('xb') as artifact:
            with gzip.GzipFile(fileobj=artifact, filename='', mode='wb', compresslevel=1, mtime=0) as writer:
                writer.write(candidate)
                remaining = system_size
                while remaining:
                    original_system = source.read(min(CHUNK, remaining))
                    block = system.read(len(original_system))
                    require(original_system and len(block) == len(original_system), 'Truncated system range')
                    remaining -= len(block)
                    exact_parent.update(block)
                    changed_image.update(block)
                    writer.write(block)
                while block := source.read(CHUNK):
                    exact_parent.update(block)
                    changed_image.update(block)
                    writer.write(block)
        require(exact_parent.hexdigest() == parent['raw']['sha256'],
                'Reconstructed unpatched parent differs from the verified Test13')
    print('Independently reading every byte of the candidate gzip.', flush=True)
    with gzip.open(partial, 'rb') as reader:
        raw = stream_ranges(reader)
    expected_ranges = dict(parent['raw']['ranges'], prefix=digest(candidate))
    require(raw['ranges'] == expected_ranges and raw['sha256'] == changed_image.hexdigest(),
            'Readback failed or a range outside the prefix changed')
    require(verify_gpt(raw.pop('head'), raw.pop('tail')) == parent['gpt'], 'GPT changed')
    partial.rename(packed)
    gzip_sha = sha(packed)
    (output / (IMAGE + '.sha256')).write_text(f'{gzip_sha}  {IMAGE}\n', encoding='ascii')
    json_write(output / 'verify-result.json', {
        'passed': True, 'candidate_only': True, 'physical_menu_verified': False,
        'fresh_menu_model': 'rg34xx', 'automatic_hardware_detection': False,
        'image': IMAGE, 'image_bytes': packed.stat().st_size, 'image_sha256': gzip_sha,
        'parent_raw_sha256': exact_parent.hexdigest(), 'raw': raw,
        'parent_uboot_sha256': UBOOT_SHA, 'uboot_sha256': digest(new),
        'early_route_cases': cases,
    })
    print(gzip_sha, packed, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    package(parser.parse_args().output)

"""Stream pinned regular-file ranges into Test2 gzip and verify every byte."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
import package_h700_v6a as base
base.constrained()
STAGE = Path('/home/lpf/h700-dualabi-parity-20261101/sealed-stage-v1')
OUT = REPO / 'out/dualabi-parity-test2-20261101-final'
OUT.mkdir(exist_ok=False)
RELEASE = 'H700_RG34XXSP_2GB_ARM64_Parity_Test2_20261101_NoROM'
parent = json.loads((REPO / 'docs/baselines/rg34xxsp-arm64-test1-20261031/image-lock.json').read_text())
stage = json.loads((REPO / 'out/dualabi-parity-20261101/sealed-stage-v1.json').read_text())
payload = json.loads((REPO / 'out/dualabi-parity-20261101/payload64-v1.json').read_text())
assert stage['e2fsck_both_exit_0'] and stage['shared_user_signatures_unified']
assert stage['navigation_version'] == 12 and stage['native_systemui_navigation_marker']
assert len(payload['apps']) == 7 and all(a['install_abi'] == 'arm64-v8a' for a in payload['apps'])
assert payload['rom_files'] == payload['bios_files'] == 0 and not payload['accounts_saves']
assert all(a['package'] != 'com.retroarch.ra32' for a in payload['apps'])
ranges = []
for entry in parent['ranges']:
    name = entry['name']
    directory = STAGE if name == 'system' else Path('/home/lpf/h700-dualabi-parity-20261101/final-stage-v2') if name == 'vendor' else Path('/home/lpf/h700-dualabi-image-20261031')
    path = directory / (name + '.candidate.raw')
    base.regular(path)
    expected = stage[name]['sha256'] if name in stage else entry['sha256']
    print('TEST2_VERIFY_INPUT', name, flush=True)
    assert path.stat().st_size == entry['bytes'] and base.sha(path) == expected
    ranges.append({**entry, 'sha256': expected, 'source': path})
assert all(r['offset'] == sum(p['bytes'] for p in ranges[:i]) for i, r in enumerate(ranges))
target = OUT / (RELEASE + '.img.gz')
whole = hashlib.sha256()
with target.open('xb') as output, gzip.GzipFile(fileobj=output, mode='wb', compresslevel=6, mtime=0, filename='') as zipped:
    for entry in ranges:
        print('TEST2_COMPRESS', entry['name'], flush=True)
        with entry['source'].open('rb') as source:
            while block := source.read(8 * 1024**2):
                whole.update(block)
                zipped.write(block)
verify, total = hashlib.sha256(), 0
with gzip.open(target, 'rb') as source:
    for entry in ranges:
        print('TEST2_FULL_DECOMPRESS_VERIFY', entry['name'], flush=True)
        remaining, digest = entry['bytes'], hashlib.sha256()
        while remaining:
            block = source.read(min(remaining, 8 * 1024**2))
            assert block, 'Short decompression'
            remaining -= len(block)
            total += len(block)
            digest.update(block)
            verify.update(block)
        assert digest.hexdigest() == entry['sha256'], entry['name']
    assert not source.read(1), 'Extra decompressed tail'
assert total == parent['bytes'] and whole.hexdigest() == verify.hexdigest()
gzip_sha = base.sha(target)
(OUT / (target.name + '.sha256')).write_text(gzip_sha + '  ' + target.name + '\n')
result = {'release': RELEASE, 'image_marker': 'dualabi-parity-test2-20261101',
          'bytes': total, 'sha256': whole.hexdigest(), 'gzip_bytes': target.stat().st_size, 'gzip_sha256': gzip_sha,
          'ranges': [{k: v for k, v in e.items() if k != 'source'} for e in ranges],
          'layout': parent['layout'], 'runtime_marker': parent['runtime_marker'], 'entry_revision': parent['entry_revision'],
          'full_gzip_decompression_verified': True, 'all_decompressed_range_hashes_verified': True,
          'factory_tail_from_pinned_clean_parent': True, 'hardware_prefix_unchanged_from_test1': True,
          'final_stage_lock_sha256': base.sha(REPO / 'out/dualabi-parity-20261101/sealed-stage-v1.json'),
          'payload_lock_sha256': base.sha(REPO / 'out/dualabi-parity-20261101/payload64-v1.json'),
          'selected_arm64_apps': [a['package'] for a in payload['apps']],
          'fresh_whole_card_flash': False, 'fresh_first_boot': False, 'whole_framework_rebuild': False,
          'rom_bios_accounts_saves': False, 'contains_diagnostic_core_cube_or_probe_apk': False}
base.jsonwrite(OUT / 'image-lock.json', result)
print('TEST2_IMAGE_ALL_RANGES_AND_FULL_DECOMPRESSION_PASS', flush=True)

"""Prepare only a new product and output directory; never contact a device."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained
constrained()
NATIVE = Path('/home/lpf/h700-android10/android')
ROOT = Path('/home/lpf/roc-os-source64-20261103')
OUT = REPO / 'out/roc-os-source64-20261103'
ROOT.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

lockfile = REPO / 'docs/baselines/h700-v5i-usb-network-20261028/source-lock.json'
frozen = json.loads(lockfile.read_text())
paths = set(frozen['files']) | {
    'device/roc/rgsp/BoardConfig.mk', 'device/roc/rgsp/h700_rgsp.mk',
    'device/roc/h700-common/BoardConfigCommon.mk', 'device/roc/h700-common/device.mk',
    'device/roc/rgsp64proto/BoardConfig.mk', 'device/roc/rgsp64proto/h700_rgsp64proto.mk',
    'build/make/core/version_defaults.mk', 'build/make/core/build_id.mk',
    'build/soong/soong_ui.bash', 'prebuilts/jdk/jdk9/linux-x86/bin/java',
    'prebuilts/clang/host/linux-x86/clang-r353983c/bin/clang',
}
protected = {}
missing = []
for name in sorted(paths):
    p = NATIVE / name
    if p.is_file(): protected[name] = sha(p)
    else: missing.append(name)
assert not missing, missing
previous = OUT / 'latest-prepare.json'
if previous.exists():
    old = json.loads((OUT / json.loads(previous.read_text())['receipt']).read_text())
    assert old['protected_native_sha256'] == protected, 'Protected source changed since previous attempt'

destination = NATIVE / 'device/roc/roc_os_source64'
source = REPO / 'android/h700-android10/device/roc/roc_os_source64'
destination.mkdir(exist_ok=True)
(destination / 'configs').mkdir(exist_ok=True)  # Optional vendor efuse search path.
for p in sorted(source.rglob('*')):
    if p.is_dir(): continue
    assert p.is_file() and not p.is_symlink()
    target = destination / p.relative_to(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() != p.read_bytes():
        backup = ROOT / 'source-backups' / (str(p.relative_to(source)) + '.' + sha(target))
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists(): shutil.copyfile(target, backup)
    if not target.exists() or target.read_bytes() != p.read_bytes(): shutil.copyfile(p, target)

# Copy the already audited prototype fork, leaving both old Gralloc trees intact.
variant = NATIVE / 'device/roc/rgsp64proto/gralloc-variant'
variant_pin = json.loads((REPO / 'out/dualabi-prototype-20261030/gralloc-variant-inputs.json').read_text())['variant']
for relative, digest in variant_pin.items():
    p = variant / relative
    assert sha(p) == digest, relative
    content = p.read_bytes()
    if relative == 'src/Android.mk':
        assert content.count(b'LOCAL_MODULE := gralloc.h700proto') == 1
        content = content.replace(b'LOCAL_MODULE := gralloc.h700proto', b'LOCAL_MODULE := gralloc.rocsource')
    target = destination / 'gralloc-variant' / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists(): assert target.read_bytes() == content, 'Do not overwrite an experimental fork'
    else: target.write_bytes(content)
assert protected == {name: sha(NATIVE / name) for name in protected}, 'Protected native source changed'
receipt = {
    'product': 'roc_os_source64-eng', 'out_dir': str(ROOT / 'out'),
    'native_root': str(NATIVE), 'has_repo_manifest': (NATIVE / '.repo/manifest.xml').exists(),
    'protected_native_sha256': protected,
    'freeze_deltas': {name: {'frozen': record['sha256'], 'current': protected[name]}
                      for name, record in frozen['files'].items() if record['sha256'] != protected[name]},
    'product_sha256': {p.relative_to(destination).as_posix(): sha(p)
                       for p in sorted(destination.rglob('*')) if p.is_file()},
    'prototype_gralloc_unchanged': all(sha(variant / n) == v for n, v in variant_pin.items()),
    'whole_source_manifest_complete': False, 'full_build_passed': False,
    'current_GSI_or_card_modified': False, 'new_partition_layout': False,
}
name = 'prepare-v%d.json'
record = next(OUT / (name % n) for n in range(1, 100) if not (OUT / (name % n)).exists())
record.write_text(json.dumps(receipt, indent=2) + '\n')
(OUT / 'latest-prepare.json').write_text(json.dumps({'receipt': record.name, 'out_dir': receipt['out_dir']}) + '\n')
print('SOURCE64_PRODUCT_PREPARED', len(protected), 'protected inputs;', len(receipt['freeze_deltas']), 'historical deltas', flush=True)

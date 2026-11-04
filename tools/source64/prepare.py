"""Prepare only a new product and output directory; never contact a device."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import os
import struct
import subprocess
import tarfile

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained
constrained()
NATIVE = Path('/home/lpf/h700-android10/android')
ROOT = Path('/home/lpf/roc-os-source64-20261103')
OUT = REPO / 'out/roc-os-source64-round2-20261103'
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
parent_out = REPO / 'out/roc-os-source64-20261103'
parent_result = json.loads((parent_out / 'images-result-v2.json').read_text())
parent = json.loads((parent_out / parent_result['prepare_receipt']).read_text())
assert parent_result['passed'] and parent['protected_native_sha256'] == protected

# Preserve the accepted round1 files before incremental Ninja may replace them.
preserved = ROOT / 'round1-preserved'
preserved.mkdir(exist_ok=True)
if not (preserved / 'receipt.json').exists():
    for name, item in parent_result['images'].items():
        source_image = ROOT / 'out/target/product/roc_os_source64' / name
        assert sha(source_image) == item['sha256'], 'Round1 image changed before preservation'
        target_image = preserved / name
        if target_image.exists(): assert sha(target_image) == item['sha256']
        else: shutil.copyfile(source_image, target_image)
    archive = preserved / 'product-source.tar.gz'
    if archive.exists():
        with tarfile.open(archive, 'r:gz') as tar:
            assert all(hashlib.sha256(tar.extractfile(name).read()).hexdigest() == digest
                       for name, digest in parent['product_sha256'].items())
    else:
        with tarfile.open(archive, 'x:gz') as tar:
            for name, digest in parent['product_sha256'].items():
                original = NATIVE / 'device/roc/roc_os_source64' / name
                assert sha(original) == digest
                tar.add(original, arcname=name, recursive=False)
    (preserved / 'receipt.json').write_text(json.dumps({'images': parent_result['images'],
        'product_source_archive_sha256': sha(archive), 'original_product_file_count': len(parent['product_sha256'])}, indent=2)+'\n')
for name, item in parent_result['images'].items():
    assert sha(preserved / name) == item['sha256'], 'Preserved round1 image changed'

destination = NATIVE / 'device/roc/roc_os_source64'
source = REPO / 'android/h700-android10/device/roc/roc_os_source64'
destination.mkdir(exist_ok=True)
attempt = next(OUT / ('attempt-v%d.json' % n) for n in range(1, 100) if not (OUT / ('attempt-v%d.json' % n)).exists())
before_archive = ROOT / 'source-backups' / (attempt.stem + '.tar.gz')
before_archive.parent.mkdir(exist_ok=True)
with tarfile.open(before_archive, 'x:gz') as tar:
    for item in sorted(destination.rglob('*')):
        if item.is_file(): tar.add(item, arcname=item.relative_to(destination).as_posix(), recursive=False)
attempt.write_text(json.dumps({'prior_product_archive': str(before_archive), 'sha256': sha(before_archive)}, indent=2)+'\n')
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
from round2 import generate, boot_contract
derived = ROOT / 'round2-derived' / attempt.stem
derived.mkdir(parents=True, exist_ok=False)
generate(REPO, NATIVE, derived)
for item in sorted(derived.rglob('*')):
    if not item.is_file(): continue
    target = destination / item.relative_to(derived)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or target.read_bytes() != item.read_bytes():
        shutil.copyfile(item, target)
boot = boot_contract(REPO, ROOT, OUT)
# Removed install targets can linger in an incremental Android staging tree.
# Retain them outside the candidate tree instead of deleting any old artifact.
retired = []
staging = ROOT / 'out/target/product/roc_os_source64'
for relative in [
    'system/etc/init/roc-factory.rc', 'system/bin/roc-factory.sh',
    'system/etc/init/roc-os-branding.rc', 'system/bin/roc-os-branding.sh',
    'system/app/RGSPNavigation',
    'system/framework/services.jar',
    'system/framework/services.jar.prof', 'system/framework/wifi-service.jar',
    'system/framework/wifi-service.jar.prof', 'system/etc/init/wifi-events.rc',
    'system/framework/oat/arm64/services.odex', 'system/framework/oat/arm64/services.vdex',
    'system/framework/oat/arm64/services.art', 'system/framework/oat/arm/services.odex',
    'system/framework/oat/arm/services.vdex', 'system/framework/oat/arm/services.art',
    'system/framework/oat/arm64/wifi-service.odex', 'system/framework/oat/arm64/wifi-service.vdex',
    'system/framework/oat/arm64/wifi-service.art', 'system/framework/oat/arm/wifi-service.odex',
    'system/framework/oat/arm/wifi-service.vdex', 'system/framework/oat/arm/wifi-service.art',
    'system/bin/vold', 'system/etc/init/vold.rc', 'system/etc/init/wait_for_keymaster.rc',
    'system/bin/preinstall', 'system/etc/init/preinstall.rc',
    'system/etc/init/h700-preinstall.rc', 'system/bin/h700-preinstall.sh',
    'system/etc/init/rgsp-firstboot.rc', 'system/bin/rgsp-firstboot.sh',
    'system/etc/init/rgsp-navigation-defaults.rc', 'system/bin/rgsp-navigation-defaults.sh',
    'system/etc/init/rgsp-roms-handoff.rc', 'system/bin/rgsp-roms-handoff.sh',
]:
    item = staging / relative
    if not item.exists(): continue
    target = ROOT / 'retired-round1-staging' / attempt.stem / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    assert not target.exists()
    shutil.move(str(item), str(target))
    retired.append({'from': relative, 'preserved_at': str(target)})
(OUT / (attempt.stem + '-retired.json')).write_text(json.dumps(retired, indent=2)+'\n')
assert protected == {name: sha(NATIVE / name) for name in protected}, 'Protected native source changed'
# RenderScript's old host Clang needs the real ABI5 libraries. Never alias ABI6
# or put the entire old sysroot (including libc) on the host loader path.
compat = ROOT / 'host-compat/lib'
compat.mkdir(parents=True, exist_ok=True)
sysroot = NATIVE / 'prebuilts/gcc/linux-x86/host/x86_64-linux-glibc2.17-4.8/sysroot/usr/lib'
compat_pin = {
    'libncurses.so.5': '19494299d25cbb3dd6a19b7de3906b8b33881998801d423deeadc6e2259460f5',
    'libtinfo.so.5': '87ec5f63974b9a4646309fa6e0033ef45b2cdea6c98a319f98596ea613a91ddd',
}
for name, digest in compat_pin.items():
    original = sysroot / name
    assert sha(original) == digest
    payload = original.read_bytes()
    assert payload[:4] == b'\x7fELF' and payload[4] == 2 and struct.unpack_from('<H', payload, 18)[0] == 62
    target = compat / name
    if target.exists(): assert not target.is_symlink() and sha(target) == digest
    else: target.write_bytes(payload)
env = {**os.environ, 'LD_LIBRARY_PATH': str(compat) + ':' + os.environ.get('LD_LIBRARY_PATH', '')}
clang = NATIVE / 'prebuilts/clang/host/linux-x86/clang-3289846/bin/clang.real'
probe = ROOT / 'host-compat/probe.c'
probe.write_text('int roc_host_probe(int value) { return value + 1; }\n')
verification = subprocess.run([str(clang), '-target', 'renderscript64-linux-android',
    '-emit-llvm', '-c', str(probe), '-o', str(probe.with_suffix('.bc'))],
    env=env, capture_output=True, text=True)
(OUT / 'host-compat-probe.log').write_text(verification.stdout + verification.stderr)
assert verification.returncode == 0
assert probe.with_suffix('.bc').read_bytes()[:4] == b'BC\xc0\xde'
receipt = {
    'product': 'roc_os_source64-eng', 'out_dir': str(ROOT / 'out'),
    'native_root': str(NATIVE), 'has_repo_manifest': (NATIVE / '.repo/manifest.xml').exists(),
    'protected_native_sha256': protected,
    'freeze_deltas': {name: {'frozen': record['sha256'], 'current': protected[name]}
                      for name, record in frozen['files'].items() if record['sha256'] != protected[name]},
    'product_sha256': {p.relative_to(destination).as_posix(): sha(p)
                       for p in sorted(destination.rglob('*')) if p.is_file()},
    'prototype_gralloc_unchanged': all(sha(variant / n) == v for n, v in variant_pin.items()),
    'host_compat_library_sha256': compat_pin, 'old_clang_renderscript_bitcode_probe_passed': True,
    'whole_source_manifest_complete': False, 'full_build_passed': False,
    'current_GSI_or_card_modified': False, 'new_partition_layout': False,
    'round': 2, 'unified_storage_sources': True, 'whole_card_image_created': False,
    'round1_preservation': str(preserved),
    'boot_contract': boot,
}
name = 'prepare-v%d.json'
record = next(OUT / (name % n) for n in range(1, 100) if not (OUT / (name % n)).exists())
record.write_text(json.dumps(receipt, indent=2) + '\n')
(OUT / 'latest-prepare.json').write_text(json.dumps({'receipt': record.name, 'out_dir': receipt['out_dir']}) + '\n')
print('SOURCE64_PRODUCT_PREPARED', len(protected), 'protected inputs;', len(receipt['freeze_deltas']), 'historical deltas', flush=True)

"""Build the real framework and dependent ART closure in a private source view.

Called only by navigation_test6_namespace.sh inside a capped private namespace.
Retained BSP and Source64 files remain read-only; the user output cache becomes
the new source revision and is explicitly marked before compilation.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from package_h700_v6a import constrained
from release.package_002 import tree_inventory

NATIVE = Path('/home/lpf/h700-android10/android')
OUT = Path('/home/lpf/roc-os-user-20261104/out')
PRODUCT = OUT / 'target/product/roc_os_source64'
WORK = Path('/home/lpf/roc-os-navigation-test6-build-20261115-v1')
DELIVERY = ROOT / 'out/nav-test6-production-20261115'
MANIFEST_SHA = 'c48f7f5dd07c73916ad5b5b10b0c215ab87e254a81453749393a15575761d8b9'
FRAMEWORK = 'frameworks/base/core/java/android/view/ViewRootImpl.java'
FRAMEWORK_ORIGINAL = '0eadf38bc8ceb599dcf57eb2d6a8b9e818a19ecedca1143b3a361682c0e64639'
FRAMEWORK_PATCHED = 'e8110bc34ac032346b2da3fb625799420a72b278cc9e58e7d4b2aadf2b2044b3'
NAV_PREFIX = 'device/roc/roc_os_source64/Navigation/'
SPACE_SHA = '847b55c93f1c0a36983ada5a500d4311b18022ef86b2db2aa3dc5614f0f400d6'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def tree(path):
    return {p.relative_to(path).as_posix(): sha(p) for p in path.rglob('*') if p.is_file() and not p.is_symlink()}


def controls():
    names = ['tools/release/build_navigation_test6.py', 'tools/release/navigation_test6_namespace.sh',
             'tools/public_build/run-limited.sh', 'tools/package_h700_v6a.py',
             'tools/release/package_002.py', 'build-support/public/source-manifest.json',
             'build-support/public/validation-20261115.json', 'docs/SPACE_REVIEW_20261028.md',
             'out/roc-os-h700-manual-selector-test5-20261114/acceptance.json']
    assert sha(ROOT / 'build-support/public/source-manifest.json') == MANIFEST_SHA
    assert sha(ROOT / 'docs/SPACE_REVIEW_20261028.md') == SPACE_SHA
    assert sha(ROOT / 'out/roc-os-h700-manual-selector-test5-20261114/acceptance.json') == '6a8e11d8b3cdde4686777e251713720d96d0e6bf6f3c147320a1900f857dca5f'
    return {name: sha(ROOT / name) for name in names}


def prepare():
    constrained()
    WORK.mkdir(exist_ok=False)
    DELIVERY.mkdir(exist_ok=False)
    before = WORK / 'before'
    before.mkdir()
    locked = controls()
    assert sha(NATIVE / FRAMEWORK) == FRAMEWORK_ORIGINAL
    navigation = NATIVE / NAV_PREFIX
    original_nav = tree(navigation)
    source = WORK / 'source'
    source.mkdir()
    manifest = json.loads((ROOT / 'build-support/public/source-manifest.json').read_text())
    selected = [entry for entry in manifest['files'] if entry['path'].startswith(NAV_PREFIX)]
    assert len(selected) == 13
    for entry in selected:
        assert entry['input']['kind'] == 'repository'
        target = source / 'Navigation' / entry['path'][len(NAV_PREFIX):]
        target.parent.mkdir(parents=True, exist_ok=True)
        origin = ROOT / entry['input']['path']
        assert sha(origin) == entry['sha256'] and origin.stat().st_size == entry['bytes']
        shutil.copyfile(origin, target)
        assert sha(target) == entry['sha256']
    framework = ROOT / 'build-support/public/overlay' / FRAMEWORK
    assert sha(framework) == FRAMEWORK_PATCHED
    shutil.copyfile(framework, source / 'ViewRootImpl.java')
    print('PHASE=archive_current_product_system_and_cache_identity', flush=True)
    inventory = tree_inventory(PRODUCT / 'system')
    write(before / 'system-tree.json', inventory)
    shutil.copytree(PRODUCT / 'system', before / 'system', symlinks=True)
    assert tree_inventory(before / 'system') == inventory
    cached = [PRODUCT / 'system.img', PRODUCT / 'obj/PACKAGING/systemimage_intermediates/system.img',
              PRODUCT / 'installed-files.txt', PRODUCT / 'installed-files.json',
              OUT / 'soong/.intermediates/build/make/target/product/roc_os_source64/system.img']
    # Preserve all actual system image locations rather than assuming one path.
    cached += list((OUT / 'soong/.intermediates').glob('**/system.img'))
    seen = set()
    archives = []
    for path in cached:
        if path in seen or not path.is_file() or path.is_symlink():
            continue
        seen.add(path)
        relative = path.relative_to(OUT)
        target = before / 'cache' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['cp', '--sparse=always', '--reflink=auto', str(path), str(target)], check=True)
        assert sha(path) == sha(target)
        archives.append({'relative': str(relative), 'sha256': sha(target), 'bytes': target.stat().st_size})
    assert any(row['relative'].endswith('/system.img') for row in archives)
    assert {str(PRODUCT.relative_to(OUT) / name) for name in ('system.img', 'obj/PACKAGING/systemimage_intermediates/system.img')} <= {row['relative'] for row in archives}
    for path in (PRODUCT / 'dexpreopt.config', OUT / 'soong/soong.variables', OUT / 'build_number.txt'):
        if path.is_file():
            target = before / path.name
            shutil.copyfile(path, target)
    config = json.loads((PRODUCT / 'dexpreopt.config').read_text())
    assert config['DisablePreopt'] is False and config['OnlyPreoptBootImageAndSystemServer'] is False
    assert set(config['CpuVariant']) == {'arm', 'arm64'} and config['NeverAllowStripping'] is True
    props = dict(line.split('=', 1) for line in (PRODUCT / 'system/build.prop').read_text().splitlines() if '=' in line and not line.startswith('#'))
    lock = {'passed': True, 'controls': locked, 'Native_Navigation_before': original_nav,
            'Native_framework_original_sha256': FRAMEWORK_ORIGINAL,
            'source_framework_sha256': FRAMEWORK_PATCHED, 'Navigation13': tree(source / 'Navigation'),
            'before_inventory_sha256': sha(before / 'system-tree.json'), 'archived_outputs': archives,
            'build_number': props['ro.build.version.incremental'], 'build_datetime': props['ro.build.date.utc'],
            'source_manifest_sha256': MANIFEST_SHA, 'source_read_only_namespace': True}
    write(WORK / 'input-lock.json', lock)
    write(DELIVERY / 'input-lock.json', lock)
    # This is deliberately outside retained source and marks the shared cache.
    write(OUT / 'ROC_NAVIGATION_TEST6_CACHE_PROVENANCE.json', {
        'state': 'incremental build pending', 'previous_source_receipts_historical': True,
        'source_manifest_sha256': MANIFEST_SHA, 'framework_source_sha256': FRAMEWORK_PATCHED,
        'snapshot': str(before), 'work': str(WORK), 'input_lock_sha256': sha(WORK / 'input-lock.json')})
    # Force image regeneration only after its old contents are safely archived.
    for row in archives:
        (OUT / row['relative']).unlink()
    assert controls() == locked
    print('PREPARED_READONLY_NAMESPACE_INPUTS', flush=True)


def build():
    constrained()
    started = time.monotonic()
    lock = json.loads((WORK / 'input-lock.json').read_text())
    assert controls() == lock['controls']
    assert os.getuid() != 0
    assert sha(NATIVE / FRAMEWORK) == FRAMEWORK_PATCHED
    assert tree(NATIVE / NAV_PREFIX) == lock['Navigation13']
    mountinfo = Path('/proc/self/mountinfo').read_text()
    (DELIVERY / 'mountinfo.txt').write_text(mountinfo)
    for target in (str(NATIVE), str(NATIVE / FRAMEWORK), str(NATIVE / NAV_PREFIX).rstrip('/')):
        matches = [line for line in mountinfo.splitlines() if line.split()[4] == target]
        assert matches and 'ro' in matches[-1].split()[5].split(','), target
    script = WORK / 'compile.sh'
    script.write_text('''#!/bin/bash
set -eo pipefail
export OUT_DIR=/home/lpf/roc-os-user-20261104/out
export ROC_RELEASE_KEYS_DIR=/home/lpf/.roc-os/keys/production-v1
export LD_LIBRARY_PATH=/home/lpf/roc-os-source64-20261103/host-compat/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 GOMAXPROCS=1 GOGC=10
export JAVA_TOOL_OPTIONS=-Xmx2048m NINJA_ARGS=-j1 MAKEFLAGS=-j1
export BUILD_NUMBER=''' + lock['build_number'] + '''
export BUILD_DATETIME=''' + lock['build_datetime'] + '''
cd /home/lpf/h700-android10/android
source build/envsetup.sh
lunch roc_os_release_candidate-user
test "$(get_build_var TARGET_BUILD_VARIANT)" = user
test "$(get_build_var BOARD_PLAT_PRIVATE_SEPOLICY_DIR)" = 'device/softwinner/common/sepolicy/private device/roc/roc_os_release_candidate/sepolicy/private'
test -z "$(get_build_var PRODUCT_PRIVATE_SEPOLICY_DIRS)$(get_build_var PRODUCT_PUBLIC_SEPOLICY_DIRS)"
m -j1 systemimage
echo PRODUCTION_FRAMEWORK_SYSTEMIMAGE_BUILD_COMPLETE
''', encoding='utf-8')
    report = {'passed': False, 'framework_production_built': False, 'boot_images_built': False,
              'source_manifest_sha256': MANIFEST_SHA, 'framework_source_sha256': FRAMEWORK_PATCHED,
              'Native_source_written': False, 'retained_source_read_only': True,
              'shared_cache_revision_changed': True, 'device_accessed': False,
              'work': str(WORK), 'OUT_DIR': str(OUT), 'architectures': ['arm', 'arm64'],
              'compile_script_sha256': sha(script), 'input_lock_sha256': sha(WORK / 'input-lock.json')}
    try:
        print('PHASE=production_framework_boot_ART_and_dependent_preopt', flush=True)
        with (DELIVERY / 'compile.log').open('w') as log:
            process = subprocess.run(['/bin/bash', str(script)], stdout=log, stderr=subprocess.STDOUT)
        report['compile_exit_status'] = process.returncode
        assert process.returncode == 0, 'Production systemimage build failed; preserve compile.log'
        assert 'PRODUCTION_FRAMEWORK_SYSTEMIMAGE_BUILD_COMPLETE' in (DELIVERY / 'compile.log').read_text()
        assert controls() == lock['controls']
        assert sha(NATIVE / FRAMEWORK) == FRAMEWORK_PATCHED
        assert tree(NATIVE / NAV_PREFIX) == lock['Navigation13']
        print('PHASE=freeze_same_graph_product_system', flush=True)
        after = WORK / 'after'
        after.mkdir()
        inventory = tree_inventory(PRODUCT / 'system')
        write(after / 'system-tree.json', inventory)
        shutil.copytree(PRODUCT / 'system', after / 'system', symlinks=True)
        assert tree_inventory(after / 'system') == inventory
        subprocess.run(['cp', '--sparse=always', '--reflink=auto', str(PRODUCT / 'system.img'), str(after / 'system.img')], check=True)
        assert sha(PRODUCT / 'system.img') == sha(after / 'system.img')
        for name in ('dexpreopt.config', 'installed-files.txt', 'installed-files.json'):
            path = PRODUCT / name
            if path.is_file(): shutil.copyfile(path, after / name)
        before = json.loads((WORK / 'before/system-tree.json').read_text())
        delta = {'added': sorted(inventory.keys() - before.keys()),
                 'removed': sorted(before.keys() - inventory.keys()),
                 'changed': sorted(name for name in before.keys() & inventory.keys() if before[name] != inventory[name])}
        write(after / 'filesystem-delta.json', delta)
        report.update(passed=True, system_image=str(after / 'system.img'), system_image_sha256=sha(after / 'system.img'),
                      system_tree=str(after / 'system'), system_inventory_sha256=sha(after / 'system-tree.json'),
                      filesystem_delta=delta, compile_log_sha256=sha(DELIVERY / 'compile.log'),
                      artifact_verification_pending=True, elapsed_seconds=time.monotonic() - started)
    except BaseException as error:
        report['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        write(DELIVERY / 'build-result.json', report)
        write(OUT / 'ROC_NAVIGATION_TEST6_CACHE_PROVENANCE.json', report)
    print('PRODUCTION_SYSTEM_BUILD_FINISHED_ARTIFACT_AUDIT_PENDING', flush=True)


if __name__ == '__main__':
    assert len(sys.argv) == 2 and sys.argv[1] in ('prepare', 'build')
    {'prepare': prepare, 'build': build}[sys.argv[1]]()

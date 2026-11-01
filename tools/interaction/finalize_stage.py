"""Recover verified stage inputs into a new candidate; regular files only."""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
import package_h700_v6a as base
base.constrained()
ROOT = Path('/home/lpf/h700-dualabi-parity-20261101')
PRIOR = ROOT / ('system-stage-v3' if (REPO / 'out/dualabi-parity-20261101/system-stage-v3.json').exists() else 'system-stage-v2')
WORK = ROOT / 'final-stage-v2'
WORK.mkdir(exist_ok=False)
OUT = REPO / 'out/dualabi-parity-20261101'
native = Path('/home/lpf/h700-android10/android')
sdk = native / 'prebuilts/sdk/tools/linux'
java = native / 'prebuilts/jdk/jdk9/linux-x86/bin/java'
os.environ['LD_LIBRARY_PATH'] = str(sdk / 'lib64')

def run(*args):
    p = subprocess.run(list(map(str, args)), capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stdout.decode(errors='replace')[-2000:] + p.stderr.decode(errors='replace')[-2000:])
    return p.stdout.decode(errors='replace') + p.stderr.decode(errors='replace')

def recover_mapping(name):
    mapping = {}
    for line in (PRIOR / (name + '.candidate.debugfs.commands')).read_text().splitlines():
        a = shlex.split(line)
        if a[0] == 'write':
            mapping[a[2]] = {'source': Path(a[1])}
        elif a[0] == 'set_inode_field' and a[2] == 'mode':
            mapping[a[1]]['mode'] = a[3]
        elif a[0] == 'ea_set':
            value = Path(a[2]).read_bytes()
            assert value.endswith(b'\0')
            mapping[a[3]]['selinux'] = value[:-1].decode()
    for record in mapping.values():
        assert set(record) == {'source', 'mode', 'selinux'}
        base.regular(record['source'])
        record['sha256'] = base.sha(record['source'])
    if name == 'system' and PRIOR.name == 'system-stage-v2':
        # Stage2's legacy modifier reused label-0/1 for vendor after its
        # successful system readback. Their system labels are explicitly
        # system_file in prepare_stage.py; never infer these from reused files.
        for inside in list(mapping)[:2]:
            assert inside in ('/system/app/BasicDreams/BasicDreams.apk', '/system/app/Bluetooth/Bluetooth.apk'), inside
            mapping[inside]['selinux'] = 'u:object_r:system_file:s0'
    return mapping

def verify_files(image, mapping):
    for number, (inside, r) in enumerate(mapping.items()):
        sample = base.dump(image, inside, WORK / 'readback.tmp')
        assert base.sha(sample) == r['sha256'], inside
        context = WORK / 'readback.context'
        if context.exists(): context.unlink()
        base.debug(image, 'ea_get -f ' + base.q(context) + ' ' + base.q(inside) + ' security.selinux')
        assert context.read_bytes() == r['selinux'].encode() + b'\0', inside
        info = base.debug(image, 'stat ' + base.q(inside))
        mode = int(r['mode'], 8) & 0o7777
        assert re.search(r'Mode:\s+0*' + format(mode, 'o') + r'\b', info), inside
        assert re.search(r'User:\s+0\s+Group:\s+0\b', info), inside
        if number % 500 == 0: print('FINAL_READBACK', image.name, number, len(mapping), flush=True)

def write_files(image, mapping):
    commands = []
    dirs = set()
    for inside in mapping:
        p = Path(inside).parent
        while str(p) != '/': dirs.add(str(p)); p = p.parent
    for directory in sorted(dirs, key=lambda p: (p.count('/'), p)):
        info = base.debug(image, 'stat ' + base.q(directory))
        if 'Type: directory' not in info:
            assert 'Inode:' not in info, directory
            commands.append('mkdir ' + base.q(directory))
    for i, (inside, r) in enumerate(mapping.items()):
        label = WORK / (image.stem + '-label-' + str(i))
        label.write_bytes(r['selinux'].encode() + b'\0')
        commands += ['rm ' + base.q(inside), 'write ' + base.q(r['source']) + ' ' + base.q(inside),
                     'set_inode_field ' + base.q(inside) + ' mode ' + r['mode'],
                     'set_inode_field ' + base.q(inside) + ' uid 0', 'set_inode_field ' + base.q(inside) + ' gid 0',
                     'ea_set -f ' + base.q(label) + ' ' + base.q(inside) + ' security.selinux']
    script = WORK / (image.stem + '.commands')
    script.write_text('\n'.join(commands) + '\n')
    (WORK / (image.stem + '.debugfs.log')).write_text(run('debugfs', '-w', '-f', script, image))
    verify_files(image, mapping)

def fsck(image):
    result = run('e2fsck', '-f', '-n', image)
    (WORK / (image.stem + '.fsck.log')).write_text(result)

parent = json.loads((REPO / 'docs/baselines/rg34xxsp-arm64-test1-20261031/image-lock.json').read_text())
system_parent = PRIOR / 'system.candidate.raw'
base.regular(system_parent)
fsck(system_parent)
system_map = recover_mapping('system')
vendor_map = recover_mapping('vendor')
prior_system_sha = base.sha(system_parent)
run('cp', '--sparse=always', system_parent, WORK / 'system.candidate.raw')
system = WORK / 'system.candidate.raw'
vendor_parent = Path('/home/lpf/h700-dualabi-handoff-p1b-20261031/vendor.candidate.raw')
expected_vendor = next(r for r in parent['ranges'] if r['name'] == 'vendor')
assert base.sha(vendor_parent) == expected_vendor['sha256'] and vendor_parent.stat().st_size == expected_vendor['bytes']
run('cp', '--sparse=always', vendor_parent, WORK / 'vendor.candidate.raw')
vendor = WORK / 'vendor.candidate.raw'
nav = REPO / 'out/dualabi-interaction-20261101/native-parity/RGSPNavigation64Interaction.apk'
nav_lock = json.loads((nav.parent / 'apps-build.json').read_text())[nav.name]
assert base.sha(nav) == nav_lock['sha256']
delta = {'/system/app/RGSPNavigation/RGSPNavigation.apk': {'source': nav, 'sha256': nav_lock['sha256'],
         'mode': '0100644', 'selinux': 'u:object_r:system_file:s0'}}
marker = WORK / 'systemui-native'
marker.write_text('GSI SystemUI native power focus and physical A unlock; Navigation12 delegates.\n')
delta['/system/etc/h700-parity/systemui-native'] = {'source': marker, 'sha256': base.sha(marker),
        'mode': '0100644', 'selinux': 'u:object_r:system_file:s0'}
write_files(system, delta)
system_map.update(delta)
verify_files(system, system_map)
write_files(vendor, vendor_map)
fsck(system)
fsck(vendor)
removed = [shlex.split(line)[1] for line in (PRIOR / 'remove-owned-test1-and-stale-preopt.commands').read_text().splitlines()]
for path in removed: assert 'Type: regular' not in base.debug(system, 'stat ' + base.q(path)), path
critical = ['/system/framework/framework.jar', '/system/bin/app_process64', '/system/bin/app_process32',
            '/system/bin/surfaceflinger', '/system/lib64/libandroid_runtime.so', '/system/lib/libandroid_runtime.so',
            '/system/apex/com.android.runtime.release/lib64/libart.so', '/system/apex/com.android.runtime.release/lib/libart.so',
            '/system/bin/h700-bootstrap/init', '/system/etc/h700-prototype/boot-entry-revision']
source = Path('/home/lpf/h700-dualabi-test1-20261031/system.candidate.raw')
assert base.sha(source) == next(r for r in parent['ranges'] if r['name'] == 'system')['sha256']
unchanged = {}
for path in critical:
    before = base.sha(base.dump(source, path, WORK / 'critical.before'))
    assert base.sha(base.dump(system, path, WORK / 'critical.after')) == before, path
    unchanged[path] = before
for path, target in [('/init', '/system/bin/h700-bootstrap/init'), ('/system/bin/init', 'h700-bootstrap/init')]:
    assert 'Fast link dest: "' + target + '"' in base.debug(system, 'stat ' + base.q(path))
records, shared_users = [], {}
paths = set(json.loads((PRIOR / 'apk-catalog.json').read_text())) | {p for p in system_map if p.endswith('.apk')}
for i, path in enumerate(sorted(paths - set(removed))):
    apk = base.dump(system, path, WORK / 'audit.apk')
    sig = run(java, '-Xmx256m', '-jar', sdk / 'lib/apksigner.jar', 'verify', '--min-sdk-version', '29', '--max-sdk-version', '29', '--print-certs', apk)
    cert = re.search(r'certificate SHA-256 digest: (\w+)', sig)[1]
    manifest = run(sdk / 'bin/aapt', 'dump', 'xmltree', apk, 'AndroidManifest.xml')
    package = re.search(r'A: package="([^"]+)"', manifest)[1]
    shared = re.search(r'android:sharedUserId[^=]*="([^"]+)"', manifest)
    shared = shared[1] if shared else None
    if shared: shared_users.setdefault(shared, set()).add(cert)
    records.append({'path': path, 'package': package, 'shared_user': shared, 'certificate_sha256': cert, 'sha256': base.sha(apk)})
    if i % 30 == 0: print('FINAL_APK_SIGNING_AUDIT', i, len(paths), flush=True)
assert all(len(certs) == 1 for certs in shared_users.values())
prop = base.dump(system, '/system/etc/prop.default', WORK / 'prop.default').read_text()
assert 'ro.h700.prototype.image=dualabi-parity-test2-20261101' in prop
assert 'ro.zygote=zygote64_32' in prop
for name in ('h700-prototype-setup.sh', 'h700-preinstall.sh'):
    file = base.dump(system, '/system/bin/' + name, WORK / name)
    assert b'\r' not in file.read_bytes()
    run('bash', '-n', file)
for mapping in (system_map, vendor_map):
    for record in mapping.values(): record.pop('source')
result = {'system': {'bytes': system.stat().st_size, 'sha256': base.sha(system)},
          'vendor': {'bytes': vendor.stat().st_size, 'sha256': base.sha(vendor)},
          'modified_files': {'system': system_map, 'vendor': vendor_map}, 'removed_paths': removed,
          'apk_signing_set': records, 'shared_user_signatures_unified': True,
          'critical_gsi_runtime_unchanged': unchanged, 'prior_system_sha256': prior_system_sha,
          'vendor_recreated_from_clean_pinned_parent': True, 'e2fsck_both_exit_0': True,
          'native_systemui_navigation_marker': True, 'navigation_version': 12,
          'fresh_first_boot': False, 'whole_framework_rebuild': False, 'game_rom_bios_accounts_saves': False}
(OUT / 'final-stage-v2.json').write_text(json.dumps(result, indent=2) + '\n')
print('FINAL_PARITY_STAGE_ALL_CHECKS_PASS', flush=True)

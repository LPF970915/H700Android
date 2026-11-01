"""Create separate Test2 system/vendor regular files; never opens a device."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
import package_h700_v6a as base
import package_h700_dualabi_prototype as proto
from omx_manifest import patch as omx_patch
base.constrained()
ROOT = Path('/home/lpf/h700-dualabi-parity-20261101')
WORK = ROOT / 'system-stage-v3'
WORK.mkdir(exist_ok=False)
OUT = REPO / 'out/dualabi-parity-20261101'
native = Path('/home/lpf/h700-android10/android')
sdk = native / 'prebuilts/sdk/tools/linux'
java = native / 'prebuilts/jdk/jdk9/linux-x86/bin/java'
os.environ['LD_LIBRARY_PATH'] = str(sdk / 'lib64')
parent = json.loads((REPO / 'docs/baselines/rg34xxsp-arm64-test1-20261031/image-lock.json').read_text())
comparison = json.loads((OUT / 'component-comparison.json').read_text())['components']
payload_lock = json.loads((OUT / 'payload64-v1.json').read_text())
api = json.loads((OUT / 'api-audit-v3.json').read_text())
assert not re.search(r'UNRESOLVED=[1-9]', api['output'])
vold_lock = json.loads((OUT / 'vold-audit-v1.json').read_text())
assert vold_lock['offline_checks_passed'] and not any(v['source'].startswith('new_missing') for v in vold_lock['libraries'].values())

def run(*args):
    p = subprocess.run(list(map(str, args)), capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stdout.decode(errors='replace')[-3000:] + p.stderr.decode(errors='replace')[-3000:])
    return p.stdout.decode(errors='replace') + p.stderr.decode(errors='replace')

sources = {'system': Path('/home/lpf/h700-dualabi-test1-20261031/system.candidate.raw'),
           'vendor': Path('/home/lpf/h700-dualabi-handoff-p1b-20261031/vendor.candidate.raw')}
for name, source in sources.items():
    entry = next(e for e in parent['ranges'] if e['name'] == name)
    base.regular(source)
    print('VERIFY_PARENT', name, flush=True)
    assert source.stat().st_size == entry['bytes'] and base.sha(source) == entry['sha256']
    run('cp', '--sparse=always', source, WORK / (name + '.candidate.raw'))
system = WORK / 'system.candidate.raw'
vendor = WORK / 'vendor.candidate.raw'
maps, vmaps = {}, {}

def add(inside, file, mode='0100644', label='u:object_r:system_file:s0'):
    maps[inside] = (Path(file), mode, label)

def signed_properties(file):
    verify = run(java, '-Xmx256m', '-jar', sdk / 'lib/apksigner.jar', 'verify',
                 '--min-sdk-version', '29', '--max-sdk-version', '29', '--print-certs', file)
    cert = re.search(r'certificate SHA-256 digest: (\w+)', verify)[1]
    manifest = run(sdk / 'bin/aapt', 'dump', 'xmltree', file, 'AndroidManifest.xml')
    package = re.search(r'A: package="([^"]+)"', manifest)[1]
    shared = re.search(r'android:sharedUserId[^=]*="([^"]+)"', manifest)
    return cert, package, shared[1] if shared else None

def signing_entry(name):
    upper = name.upper()
    leaf = upper.rsplit('/', 1)[-1]
    return upper.startswith('META-INF/') and (leaf == 'MANIFEST.MF' or leaf.startswith('SIG-') or leaf.endswith(('.SF', '.RSA', '.DSA', '.EC')))

def same_unsigned_content(before, after):
    with zipfile.ZipFile(before) as a, zipfile.ZipFile(after) as b:
        aa = {n for n in a.namelist() if not signing_entry(n)}
        bb = {n for n in b.namelist() if not signing_entry(n)}
        assert aa == bb
        for name in aa:
            assert a.read(name) == b.read(name), name

role_refs = {'platform': 'framework-res', 'testkey': 'SettingsIntelligence', 'shared': 'LatinIME', 'media': 'MediaProvider'}
roles = {}
for role, name in role_refs.items():
    old = re.search(r'certificate SHA-256 digest: (\w+)', comparison[name]['gsi']['signature'])[1]
    desired = re.search(r'certificate SHA-256 digest: (\w+)', comparison[name]['arm32']['signature'])[1]
    roles[old] = (role, desired)
substitutions = {}
for name in ('DocumentsUI', 'LatinIME', 'PermissionController', 'PackageInstaller', 'SettingsIntelligence',
             'Calendar', 'Contacts', 'Traceur', 'MediaProvider'):
    substitutions[comparison[name]['gsi']['path']] = ROOT / 'rebased-apps-v2' / (name + '.apk')
substitutions[comparison['Settings']['gsi']['path']] = ROOT / 'settings-api-v1/Settings.apk'
substitutions[comparison['SystemUI']['gsi']['path']] = ROOT / 'systemui-v6/SystemUI.apk'

def list_dir(image, directory):
    result = []
    for line in base.debug(image, 'ls -p ' + base.q(directory)).splitlines():
        parts = line.split('/')
        if len(parts) >= 7 and parts[1].isdigit() and parts[5] not in ('.', '..', ''):
            result.append((parts[5], int(parts[2], 8)))
    return result

apk_paths = {'/system/framework/framework-res.apk'}
visited = set()
queue = ['/system/app', '/system/priv-app', '/system/product/app', '/system/product/priv-app',
         '/system/overlay', '/system/product/overlay', '/system/apex']
while queue:
    directory = queue.pop()
    if directory in visited:
        continue
    visited.add(directory)
    for name, mode in list_dir(system, directory):
        inside = directory + '/' + name
        if mode & 0o170000 == 0o040000:
            queue.append(inside)
        elif mode & 0o170000 == 0o100000 and name.endswith('.apk'):
            assert not inside.startswith('/system/apex/'), 'Review embedded APEX APK signing before migration'
            apk_paths.add(inside)
assert set(substitutions) <= apk_paths, set(substitutions) - apk_paths
apk_records = []
shared_users = {}
omitted_tests = []
apk_work = WORK / 'apks'
apk_work.mkdir()
(WORK / 'apk-catalog.json').write_text(json.dumps(sorted(apk_paths), indent=2) + '\n')
for index, inside in enumerate(sorted(apk_paths)):
    original = base.dump(system, inside, apk_work / (str(index) + '.original.apk'))
    identity = run(sdk / 'bin/aapt', 'dump', 'badging', original)
    source_package = re.search(r"package: name='([^']+)'", identity)[1]
    if source_package in ('com.android.cts.ctsshim', 'com.android.cts.priv.ctsshim'):
        # These GSI-only CTS fixtures are not runtime services or selected apps.
        # The inspected private shim lacks a complete APK signature block.
        # Omit both fixtures rather than weakening APK verification.
        omitted_tests.append(inside)
        print('OMIT_GSI_CTS_FIXTURE', source_package, flush=True)
        continue
    old_cert, old_package, old_shared = signed_properties(original)
    candidate = substitutions.get(inside, original)
    if candidate != original:
        cert, package, shared = signed_properties(candidate)
        assert package == old_package and shared == old_shared, inside
    else:
        cert, package, shared = old_cert, old_package, old_shared
    if old_cert in roles:
        role, desired = roles[old_cert]
        if cert != desired:
            assert candidate == original, 'Unexpected candidate signing role'
            signed = apk_work / (str(index) + '.signed.apk')
            run(java, '-Xmx256m', '-jar', sdk / 'lib/apksigner.jar', 'sign',
                '--key', native / f'build/make/target/product/security/{role}.pk8',
                '--cert', native / f'build/make/target/product/security/{role}.x509.pem',
                '--min-sdk-version', '29', '--out', signed, candidate)
            same_unsigned_content(candidate, signed)
            candidate = signed
            cert, package, shared = signed_properties(candidate)
        assert cert == desired, inside
    if candidate != original:
        add(inside, candidate)
    if shared:
        shared_users.setdefault(shared, set()).add(cert)
    apk_records.append({'path': inside, 'package': package, 'shared_user': shared,
        'certificate_sha256': cert, 'sha256': base.sha(candidate), 'changed': candidate != original})
    print('APK_SIGNING_SET', index + 1, len(apk_paths), package, flush=True)
assert all(len(certs) == 1 for certs in shared_users.values()), shared_users

helpers = {
    '/system/priv-app/AT4K/AT4K.apk': (REPO / base.PIN['system:/system/priv-app/AT4K/AT4K.apk'][0], base.PIN['system:/system/priv-app/AT4K/AT4K.apk'][1]),
    '/system/app/RGSPNavigation/RGSPNavigation.apk': (OUT.parent / 'dualabi-interaction-20261101/power-safe/RGSPNavigation64Interaction.apk', 'a886e2edec521241becd498fa5ff8426099cecc97207ef663390dcf90c26cd3c'),
    '/system/priv-app/H700Lid/H700Lid.apk': (REPO / base.PIN['system:/system/priv-app/H700Lid/H700Lid.apk'][0], base.PIN['system:/system/priv-app/H700Lid/H700Lid.apk'][1]),
    '/system/priv-app/H700Rotation/H700Rotation.apk': (REPO / base.PIN['system:/system/priv-app/H700Rotation/H700Rotation.apk'][0], base.PIN['system:/system/priv-app/H700Rotation/H700Rotation.apk'][1]),
    '/system/app/LeanbackIME/LeanbackIME.apk': (ROOT / 'inputs-arm32/LeanbackIME.apk', comparison['LeanbackIME']['arm32']['sha256']),
}
for inside, (file, digest) in helpers.items():
    assert base.sha(file) == digest
    add(inside, file)
    cert, package, shared = signed_properties(file)
    if shared:
        shared_users.setdefault(shared, set()).add(cert)
    record = next((r for r in apk_records if r['path'] == inside), None)
    update = {'path': inside, 'package': package, 'shared_user': shared,
              'certificate_sha256': cert, 'sha256': digest, 'changed': True}
    if record is None:
        apk_records.append(update)
    else:
        record.update(update)
assert all(len(certs) == 1 for certs in shared_users.values()), shared_users
overlay = ROOT / 'framework-overlay-v3/H700FrameworkOverlay.apk'
assert base.sha(overlay) == json.loads((OUT / 'framework-overlay-v3.json').read_text())['sha256']
add('/system/overlay/H700FrameworkOverlay/H700FrameworkOverlay.apk', overlay)
services = ROOT / 'services-v3/services.parity.jar'
assert base.sha(services) == json.loads((OUT / 'services-v3.json').read_text())['sha256']
add('/system/framework/services.jar', services)
vold = ROOT / 'vold-audit-v1/vold'
assert base.sha(vold) == vold_lock['vold_sha256']
add('/system/bin/vold', vold, '0100755', 'u:object_r:vold_exec:s0')

gsi_mac = base.dump(system, '/system/etc/selinux/plat_mac_permissions.xml', WORK / 'mac.gsi.xml').read_bytes()
bsp_mac = base.dump(Path('/home/lpf/h700-release-v6b-20261030/system.candidate.raw'),
                    '/system/etc/selinux/plat_mac_permissions.xml', WORK / 'mac.bsp.xml').read_bytes()
root = ET.fromstring(gsi_mac)
signatures = {n.attrib['signature'] for n in root.findall('signer')}
extra = []
for block in re.findall(rb'<signer\b.*?</signer>', bsp_mac, re.S):
    signer = ET.fromstring(block)
    if signer.attrib['signature'] not in signatures:
        extra.append(block)
        signatures.add(signer.attrib['signature'])
closing = ('</' + root.tag + '>').encode()
assert gsi_mac.count(closing) == 1
merged = gsi_mac.replace(closing, b'\n<!-- Pinned H700 development signing aliases; original GSI mappings retained. -->\n' + b'\n'.join(extra) + b'\n' + closing)
ET.fromstring(merged)
mac = WORK / 'plat_mac_permissions.xml'
mac.write_bytes(merged)
add('/system/etc/selinux/plat_mac_permissions.xml', mac)

product = REPO / 'android/h700-android10/device/roc/rgsp'
for stem in ('rgsp-roms-handoff', 'rgsp-wallpapers'):
    add('/system/bin/' + stem + '.sh', product / (stem + '.sh'), '0100755', 'u:object_r:shell_exec:s0')
    add('/system/etc/init/' + stem + '.rc', product / (stem + '.rc'))
add('/system/bin/h700-prototype-setup.sh', REPO / 'tools/interaction/test2_setup.sh', '0100755', 'u:object_r:shell_exec:s0')
add('/system/bin/h700-preinstall.sh', ROOT / 'payload64-v1/h700-preinstall.sh', '0100755', 'u:object_r:shell_exec:s0')
for name, digest in payload_lock['files'].items():
    file = ROOT / 'payload64-v1/payload' / name
    assert base.sha(file) == digest, name
    add('/system/etc/h700-preinstall/' + name, file)
feature = WORK / 'h700-framework-features.xml'
feature.write_text('<permissions>\n    <feature name="android.software.app_widgets" />\n</permissions>\n')
add('/system/etc/permissions/h700-framework-features.xml', feature)

prop = base.dump(system, '/system/etc/prop.default', WORK / 'prop.default.before').read_text()
for name, value in {'ro.h700.prototype.image': 'dualabi-parity-test2-20261101',
                    'ro.h700.release': 'arm64-parity-test2-20261101',
                    'persist.sys.locale': 'zh-CN'}.items():
    prop = re.sub(r'^' + re.escape(name) + r'=.*\n', '', prop, flags=re.M)
    prop += name + '=' + value + '\n'
propfile = WORK / 'prop.default'
propfile.write_text(prop, encoding='utf-8', newline='\n')
add('/system/etc/prop.default', propfile)
revision = WORK / 'image-revision'
revision.write_text('dualabi-parity-test2-20261101\n')
add('/system/etc/h700-prototype/image-revision', revision)

manifest = base.dump(vendor, '/etc/vintf/manifest.xml', WORK / 'vendor-manifest.before.xml').read_bytes()
assert hashlib.sha256(manifest).hexdigest() == 'e6c225cf18457c8c32502d287c7aa3107f4e6bb40924f253a5f54fcf4c31903b'
manifest_file = WORK / 'vendor-manifest.xml'
manifest_file.write_bytes(omx_patch(manifest))
assert base.sha(manifest_file) == '4daf1c9d027f302b3c1558807eeae8964277d1583c4d227ae1fe3ad08ca2262c'
vmaps['/etc/vintf/manifest.xml'] = (manifest_file, '0100644', 'u:object_r:vendor_configs_file:s0')
fstab = base.dump(vendor, '/etc/fstab.sun50iw9p1', WORK / 'fstab.before').read_text()
source_fstab = base.dump(Path('/home/lpf/h700-release-v6a-20261030/vendor.candidate.raw'),
                         '/etc/fstab.sun50iw9p1', WORK / 'fstab.arm32').read_text()
assert 'voldmanaged=' not in fstab
vold_lines = [line for line in source_fstab.splitlines() if 'voldmanaged=' in line]
assert vold_lines
fstab_file = WORK / 'fstab.sun50iw9p1'
fstab_file.write_text(fstab.rstrip() + '\n' + '\n'.join(vold_lines) + '\n', newline='\n')
vmaps['/etc/fstab.sun50iw9p1'] = (fstab_file, '0100644', 'u:object_r:vendor_configs_file:s0')

removed = [f'/system/etc/h700-prototype/apks/{name}.apk' for name in
           ('H700AbiProbe64', 'MTManager', 'RetroArch', 'PPSSPP')]
removed += ['/system/etc/h700-prototype/apps.list', '/system/etc/h700-prototype/retroarch-test.cfg',
            '/system/etc/h700-prototype/H700_ANBERNIC_keys.cfg']
removed += omitted_tests
for inside in substitutions:
    parentdir, filename = inside.rsplit('/', 1)
    stem = filename[:-4]
    for arch in ('arm', 'arm64'):
        for suffix in ('odex', 'vdex', 'art'):
            path = f'{parentdir}/oat/{arch}/{stem}.{suffix}'
            if 'Type: regular' in base.debug(system, 'stat ' + base.q(path)):
                removed.append(path)
for arch in ('arm', 'arm64'):
    for directory in ('/system/framework/oat/' + arch, '/system/framework/' + arch):
        for suffix in ('odex', 'vdex', 'art'):
            path = directory + '/services.' + suffix
            if 'Type: regular' in base.debug(system, 'stat ' + base.q(path)):
                removed.append(path)
commands = WORK / 'remove-owned-test1-and-stale-preopt.commands'
commands.write_text(''.join('rm ' + base.q(path) + '\n' for path in sorted(set(removed))))
run('debugfs', '-w', '-f', commands, system)
proto.WORK = WORK
print('STAGE_WRITE_READBACK_SYSTEM', len(maps), flush=True)
system_record = proto.modify(system, maps, 'u:object_r:system_file:s0')
print('STAGE_WRITE_READBACK_VENDOR', len(vmaps), flush=True)
vendor_record = proto.modify(vendor, vmaps, 'u:object_r:vendor_file:s0')
for path in removed:
    assert 'Type: regular' not in base.debug(system, 'stat ' + base.q(path)), path
# Verify critical unchanged GSI/ART/graphics/bootstrap bytes against the source.
critical = ['/system/framework/framework.jar', '/system/bin/app_process64', '/system/bin/app_process32',
            '/system/bin/surfaceflinger', '/system/lib64/libandroid_runtime.so', '/system/lib/libandroid_runtime.so',
            '/system/apex/com.android.runtime.release/lib64/libart.so', '/system/apex/com.android.runtime.release/lib/libart.so',
            '/system/bin/h700-bootstrap/init', '/system/etc/h700-prototype/boot-entry-revision']
unchanged = {}
for inside in critical:
    before = base.dump(sources['system'], inside, WORK / 'critical.before')
    digest = base.sha(before)
    after = base.dump(system, inside, WORK / 'critical.after')
    assert base.sha(after) == digest, inside
    unchanged[inside] = digest
for path, target in [('/init', '/system/bin/h700-bootstrap/init'), ('/system/bin/init', 'h700-bootstrap/init')]:
    assert 'Fast link dest: "' + target + '"' in base.debug(system, 'stat ' + base.q(path))
result = {'system': {'bytes': system.stat().st_size, 'sha256': base.sha(system)},
          'vendor': {'bytes': vendor.stat().st_size, 'sha256': base.sha(vendor)},
          'modified_files': {'system': system_record, 'vendor': vendor_record}, 'removed_paths': removed,
          'apk_signing_set': apk_records, 'shared_user_signatures_unified': True,
          'original_gsi_mac_mappings_retained': True, 'new_bsp_signing_aliases': len(extra),
          'critical_gsi_runtime_unchanged': unchanged, 'fresh_first_boot': False,
          'appwidgets_feature_added_for_known_null_widget_manager': True,
          'whole_framework_rebuild': False, 'game_rom_bios_accounts_saves': False}
(OUT / 'system-stage-v3.json').write_text(json.dumps(result, indent=2) + '\n')
print('INDEPENDENT_ARM64_PARITY_STAGE_COMPLETE', flush=True)

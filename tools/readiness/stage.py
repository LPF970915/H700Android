"""Create an offline child of Test2a. Never opens a block device or calls ADB."""
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
import package_h700_v6a as base
import package_h700_dualabi_prototype as proto
base.constrained()
import audit_power
audit_power.main()
OUT = REPO / 'out/rg34xxsp-readiness-20261102'
audit = json.loads((OUT / 'light-candidate.json').read_text())
assert audit['offline_passed'] and not audit['device_installed']
parentfile = REPO / 'docs/baselines/rg34xxsp-arm64-defaults-test2a-20261101/components-lock.json'
assert base.sha(parentfile) == audit['parent_components_sha256']
parent = json.loads(parentfile.read_text())
root = Path('/home/lpf/h700-readiness-20261102')
WORK = next(root / ('stage-v%d' % n) for n in range(1, 100) if not (root / ('stage-v%d' % n)).exists())
WORK.mkdir()
sources = {
    'system': Path('/home/lpf/h700-dualabi-parity-20261101/defaults-stage-v1/system.candidate.raw'),
    'vendor': Path('/home/lpf/h700-dualabi-parity-20261101/final-stage-v2/vendor.candidate.raw'),
}
for name, source in sources.items():
    base.regular(source)
    assert source.stat().st_size == parent[name]['bytes'] and base.sha(source) == parent[name]['sha256']
    subprocess.run(['cp', '--sparse=always', source, WORK / (name + '.candidate.raw')], check=True)
system, vendor = WORK / 'system.candidate.raw', WORK / 'vendor.candidate.raw'
maps, vmaps = {}, {}

def text(partition, inside, name):
    return base.dump(partition, inside, WORK / name).read_text()

def changed(inside, content, name, mode='0100644', label='u:object_r:system_file:s0'):
    file = WORK / name
    file.write_text(content, newline='\n')
    maps[inside] = (file, mode, label)
    return file

oldmarker = 'dualabi-parity-test2a-20261101'
marker = 'dualabi-readiness-r1-20261102'
props = text(system, '/system/etc/prop.default', 'prop.default.before')
assert props.count('ro.h700.prototype.image=' + oldmarker) == 1
props = props.replace('ro.h700.prototype.image=' + oldmarker, 'ro.h700.prototype.image=' + marker)
props = re.sub(r'^ro.h700.release=.*$', 'ro.h700.release=arm64-readiness-r1-20261102', props, flags=re.M)
changed('/system/etc/prop.default', props, 'prop.default')
changed('/system/etc/h700-prototype/image-revision', marker + '\n', 'image-revision')
for name in ('h700-prototype-setup.sh', 'h700-preinstall.sh'):
    content = text(system, '/system/bin/' + name, name + '.before')
    # Setup checks the image marker; preinstall independently checks release.
    # Both must advance together or the first-boot installer will refuse to run.
    content = content.replace(oldmarker, marker)
    content = content.replace('arm64-parity-test2a-20261101', 'arm64-readiness-r1-20261102')
    content = content.replace('ARM64_PARITY_TEST2A_DEFAULTS', 'ARM64_READINESS_R1_DEFAULTS')
    if name == 'h700-prototype-setup.sh':
        assert '[ "$(getprop ro.h700.prototype.image)" = ' + marker + ' ]' in content
    else:
        assert '[ "$(getprop ro.h700.release)" = arm64-readiness-r1-20261102 ]' in content
    file = changed('/system/bin/' + name, content, name, '0100755', 'u:object_r:shell_exec:s0')
    subprocess.run(['bash', '-n', file], check=True)
rc = REPO / 'tools/arm64_probe/prototype_setup.rc'
assert b'\r' not in rc.read_bytes()
assert re.search(r'^    priority 19$', rc.read_text(), re.M)
assert re.search(r'^    ioprio idle 0$', rc.read_text(), re.M)
maps['/system/etc/init/h700-prototype-setup.rc'] = (rc, '0100644', 'u:object_r:system_file:s0')

light = REPO / 'android/h700-android10/device/roc/rgsp/H700Light'
binary = Path(audit['binary'])
assert base.sha(binary) == audit['binary_sha256']
vmaps['/bin/hw/android.hardware.light@2.0-service.h700'] = (binary, '0100755', 'u:object_r:hal_light_default_exec:s0')
vmaps['/etc/init/h700-light.rc'] = (light / 'h700-light.rc', '0100644', 'u:object_r:vendor_configs_file:s0')
for inside, item in audit['added_libraries'].items():
    file = Path(item['path'])
    assert base.sha(file) == item['sha256']
    vmaps[inside] = (file, '0100644', 'u:object_r:vendor_file:s0')
manifest = text(vendor, '/etc/vintf/manifest.xml', 'manifest.xml.before')
tree = ET.fromstring(manifest)
old_hals = [ET.tostring(h) for h in tree.findall('hal')]
assert not any(h.findtext('name') == 'android.hardware.light' for h in tree.findall('hal'))
hal = ET.fromstring((light / 'h700-light.xml').read_bytes()).find('hal')
assert hal is not None
block = ET.tostring(hal, encoding='unicode')
assert manifest.count('</manifest>') == 1
manifest = manifest.replace('</manifest>', '    ' + block + '\n</manifest>')
after = ET.fromstring(manifest)
assert [ET.tostring(h) for h in after.findall('hal')[:-1]] == old_hals
file = WORK / 'manifest.xml'
file.write_text(manifest, newline='\n')
assembler = Path('/home/lpf/h700-dualabi-prototype-20261030/out/host/linux-x86/bin/assemble_vintf')
validation = subprocess.run([str(assembler), '-i', str(file), '-o', str(WORK / 'manifest.parser-check.xml')],
    env={**os.environ, 'BOARD_SEPOLICY_VERS': '29.0'}, capture_output=True, text=True)
(WORK / 'manifest.parser-check.log').write_text(validation.stdout + validation.stderr)
assert validation.returncode == 0, validation.stderr
vmaps['/etc/vintf/manifest.xml'] = (file, '0100644', 'u:object_r:vendor_configs_file:s0')
contexts = text(vendor, '/etc/selinux/vendor_file_contexts', 'vendor_file_contexts.before')
entry = (light / 'file_contexts').read_text().strip()
assert 'service\\.h700' not in contexts
file = WORK / 'vendor_file_contexts'
file.write_text(contexts.rstrip() + '\n' + entry + '\n', newline='\n')
vmaps['/etc/selinux/vendor_file_contexts'] = (file, '0100644', 'u:object_r:vendor_configs_file:s0')

proto.WORK = WORK
modified = {'system': proto.modify(system, maps, 'u:object_r:system_file:s0'),
            'vendor': proto.modify(vendor, vmaps, 'u:object_r:vendor_file:s0')}
# Re-read every existing locked overlay, not only the new delta.
record = copy.deepcopy(parent)
for partition, mapping in modified.items():
    record['modified_files'][partition].update(mapping)
    image = system if partition == 'system' else vendor
    for inside, item in record['modified_files'][partition].items():
        sample = base.dump(image, inside, WORK / 'locked-readback.tmp')
        assert base.sha(sample) == item['sha256'], inside
    record[partition]['sha256'] = base.sha(image)
for inside, digest in parent['critical_gsi_runtime_unchanged'].items():
    assert base.sha(base.dump(system, inside, WORK / 'critical-readback.tmp')) == digest, inside
for name, source in sources.items():
    assert base.sha(source) == parent[name]['sha256'], 'Frozen parent changed'
record.update({'parent_components_sha256': base.sha(parentfile), 'work': str(WORK),
    'new_image_marker': marker, 'changed_from_test2a': modified,
    'light_audit_sha256': base.sha(OUT / 'light-candidate.json'),
    'power_audit_sha256': base.sha(OUT / 'power-audit.json'),
    'setup_priority': 19, 'setup_ioprio': 'idle 0',
    'merged_vintf_android_parser_passed': True,
    'e2fsck_both_exit_0': True, 'device_installed': False,
    'fresh_first_boot': False, 'physical_brightness_accepted': False,
    'full_image_packaged': False, 'selinux_enforcing_accepted': False,
    'power_wakelocks_changed': False, 'third_party_apps_changed': False})
(OUT / ('candidate-' + WORK.name + '.json')).write_text(json.dumps(record, indent=2) + '\n')
print('READINESS_OFFLINE_STAGE_PASS', WORK.name, len(modified['system']), len(modified['vendor']), flush=True)

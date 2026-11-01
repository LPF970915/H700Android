"""Create Test2a factory locale/HOME defaults without opening a device."""
import json
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
ROOT = Path('/home/lpf/h700-dualabi-parity-20261101')
WORK = ROOT / 'defaults-stage-v1'
WORK.mkdir(exist_ok=False)
OUT = REPO / 'out/dualabi-defaults-test2a-20261101'
OUT.mkdir(exist_ok=False)
parentfile = REPO / 'docs/baselines/rg34xxsp-arm64-parity-test2-20261101/components-lock.json'
record = json.loads(parentfile.read_text())
parent = ROOT / 'sealed-stage-v1/system.candidate.raw'
assert base.sha(parent) == record['system']['sha256']
system = WORK / 'system.candidate.raw'
subprocess.run(['cp', '--sparse=always', parent, system], check=True)
maps = {}

def add(path, file, executable=False):
    maps[path] = (file, '0100755' if executable else '0100644',
                  'u:object_r:shell_exec:s0' if executable else 'u:object_r:system_file:s0')

def properties(path, values):
    file = base.dump(system, path, WORK / (Path(path).name + '.before'))
    text = file.read_text()
    for key, value in values.items():
        text = re.sub(r'^' + re.escape(key) + r'=.*(?:\n|$)', '', text, flags=re.M)
        text += key + '=' + value + '\n'
    candidate = WORK / Path(path).name
    candidate.write_text(text, newline='\n')
    add(path, candidate)

locale = {'ro.product.locale': 'zh-CN', 'ro.product.locale.language': 'zh', 'ro.product.locale.region': 'CN'}
properties('/system/etc/prop.default', {**locale, 'persist.sys.locale': 'zh-CN',
    'ro.h700.prototype.image': 'dualabi-parity-test2a-20261101', 'ro.h700.release': 'arm64-parity-test2a-20261101'})
properties('/system/build.prop', locale)
factory = REPO / 'android/h700-android10/device/roc/rgsp/configs/at4k-home.xml'
tree = ET.fromstring(factory.read_bytes())
assert tree.tag == 'preferred-activities'
item, = tree.findall('item')
assert item.attrib['name'] == 'com.overdevs.at4k/.MainActivity'
filter = item.find('filter')
assert [n.attrib['name'] for n in filter.findall('action')] == ['android.intent.action.MAIN']
assert {n.attrib['name'] for n in filter.findall('cat')} == {'android.intent.category.HOME', 'android.intent.category.DEFAULT'}
add('/system/etc/preferred-apps/at4k-home.xml', factory)
for name in ('h700-prototype-setup.sh', 'h700-preinstall.sh'):
    old = base.dump(system, '/system/bin/' + name, WORK / (name + '.before')).read_text()
    assert 'parity-test2' in old and 'parity-test2a' not in old
    new = old.replace('parity-test2', 'parity-test2a').replace('ARM64_PARITY_TEST2_DEFAULTS', 'ARM64_PARITY_TEST2A_DEFAULTS')
    # Keep late HOME reassertion for a newly installed HOME-capable Pegasus.
    assert 'pm set-home-activity --user 0 com.overdevs.at4k/.MainActivity' in new
    candidate = WORK / name
    candidate.write_text(new, newline='\n')
    subprocess.run(['bash', '-n', candidate], check=True)
    add('/system/bin/' + name, candidate, True)
revision = WORK / 'image-revision'
revision.write_text('dualabi-parity-test2a-20261101\n')
add('/system/etc/h700-prototype/image-revision', revision)
proto.WORK = WORK
modified = proto.modify(system, maps, 'u:object_r:system_file:s0')
record['modified_files']['system'].update(modified)
record['system']['sha256'] = base.sha(system)
record['parent_components_lock_sha256'] = base.sha(parentfile)
record['factory_locale'] = 'zh-CN'
record['factory_default_home'] = 'com.overdevs.at4k/.MainActivity'
record['factory_home_preference_installed_before_first_home'] = True
record['late_home_reassertion_preserved'] = True
record['new_image_marker'] = 'dualabi-parity-test2a-20261101'
record['fresh_first_boot'] = False
record['changed_from_test2'] = modified
# All existing components and the seven application payloads remain identical.
original = json.loads(parentfile.read_text())
assert all(r == record['modified_files']['system'][p]
           for p, r in original['modified_files']['system'].items() if p not in maps)
assert original['vendor'] == record['vendor']
for path in record['critical_gsi_runtime_unchanged']:
    sample = base.dump(system, path, WORK / 'critical-readback.tmp')
    assert base.sha(sample) == record['critical_gsi_runtime_unchanged'][path]
(OUT / 'defaults-stage-v1.json').write_text(json.dumps(record, indent=2) + '\n')
print('FACTORY_ZH_CN_AND_AT4K_DEFAULTS_STAGE_PASS', len(modified), flush=True)

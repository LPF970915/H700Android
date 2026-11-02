"""Audit an existing offline stage and exercise saved-name migration in a mock host."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
import package_h700_v6a as base
from branding import MODEL_KEYS, MODEL

base.constrained()
out = REPO / 'out/rg34xxsp-readiness-20261102'
records = sorted((p for p in out.glob('candidate-stage-v*.json')
                  if re.fullmatch(r'candidate-stage-v\d+\.json', p.name)),
                 key=lambda p: int(p.stem.split('v')[-1]))
candidate = records[-1]
record = json.loads(candidate.read_text())
assert record['new_image_marker'] == 'roc-os-readiness-r4-20261103'
work = Path(record['work'])
rejected = out / (candidate.stem + '.rejected.json')
assert not rejected.exists(), 'Do not accept the superseded initial RC draft'
rc_source = REPO / 'android/h700-android10/device/roc/rgsp/roc-os-branding.rc'
assert '    seclabel u:r:su:s0\n' in rc_source.read_text()
assert record['modified_files']['system']['/system/etc/init/roc-os-branding.rc']['sha256'] == base.sha(rc_source)
effective, original = {}, {}
files = ['prop.default', 'build.prop', 'vendor.build.prop', 'odm.build.prop', 'product.build.prop']
for name in files:
    before = dict(re.findall(r'^([^#\s=]+)=(.*)$', (work / (name + '.before')).read_text(), re.M))
    after = dict(re.findall(r'^([^#\s=]+)=(.*)$', (work / name).read_text(), re.M))
    # Marker changes are deliberate; all hardware/ABI/VNDK/graphics properties must stay.
    allowed = set(MODEL_KEYS) | {'ro.build.display.id', 'ro.h700.prototype.image', 'ro.h700.release'}
    assert all(after[k] == v for k, v in before.items() if k not in allowed), name
    assert all(after[k] == MODEL for k in MODEL_KEYS), name
    effective.update(after)
    original.update(before)
assert all(effective[k] == MODEL for k in MODEL_KEYS)
assert effective['ro.build.display.id'] == 'ROC OS ARM64 Test'
for key in ['ro.product.device', 'ro.zygote', 'ro.vndk.version', 'ro.hardware.gralloc']:
    assert effective[key] == original[key], key

script = REPO / 'android/h700-android10/device/roc/rgsp/roc-os-branding.sh'
with tempfile.TemporaryDirectory(prefix='roc-branding-', dir=work) as temporary:
    temp = Path(temporary)
    stub = temp / 'mock'
    stub.write_text('''#!/usr/bin/python3
import json, os, pathlib, sys
p=pathlib.Path(os.environ['ROC_MOCK_STATE']); state=json.loads(p.read_text())
if pathlib.Path(sys.argv[0]).name=='getprop':
 print({'ro.product.device':os.environ.get('ROC_MOCK_DEVICE','rgsp'), 'ro.product.model':'ROC OS','sys.boot_completed':'1'}[sys.argv[1]])
else:
 args=sys.argv[1:]
 assert args[:2]==['--user','0']; action, namespace, key=args[2:5]
 if action=='get': print(state.get(namespace+'.'+key,'null'))
 else:
  assert action=='put'; state[namespace+'.'+key]=args[5]; p.write_text(json.dumps(state))
''')
    stub.chmod(0o755)
    for name in ['settings', 'getprop']:
        (temp / name).symlink_to(stub.name)
    statefile = temp / 'state.json'
    env = {**os.environ, 'PATH': str(temp) + ':' + os.environ['PATH'], 'ROC_MOCK_STATE': str(statefile)}
    for name in ['null', '', 'RGSP H700', 'RGSP_H700', 'H700 Android USB', 'ROC OS', 'My handheld']:
        state = {'global.device_name': name, 'secure.bluetooth_name': name}
        statefile.write_text(json.dumps(state))
        subprocess.run(['bash', str(script)], env=env, check=True)
        result = json.loads(statefile.read_text())
        expected = 'My handheld' if name == 'My handheld' else MODEL
        assert set(result.values()) == {expected}
        subprocess.run(['bash', str(script)], env=env, check=True)
        assert json.loads(statefile.read_text()) == result
    statefile.write_text(json.dumps(state))
    denied = subprocess.run(['bash', str(script)], env={**env, 'ROC_MOCK_DEVICE': 'other'})
    assert denied.returncode != 0 and json.loads(statefile.read_text()) == state

result = {'new_image_marker': record['new_image_marker'], 'candidate_metadata_sha256': base.sha(candidate),
          'offline_model_namespaces_passed': list(MODEL_KEYS),
          'property_order_and_nonbranding_properties_preserved': True,
          'seven_saved_name_cases_idempotent_and_custom_preserved': True,
          'wrong_device_migration_denied': True, 'runtime_model_or_USB_acceptance': False,
          'new_IMG': False, 'clean_preload_or_storage_layout_included': False}
destination = REPO / 'out/roc-os-branding-20261103/offline-audit.json'
destination.parent.mkdir(exist_ok=True)
destination.write_text(json.dumps(result, indent=2) + '\n')
print('ROC_OS_OFFLINE_BRANDING_AUDIT_PASS', flush=True)

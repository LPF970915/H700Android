"""Require the protected ROMS filter in the actual independent ARM64 vold build."""
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained
constrained()
native = Path('/home/lpf/h700-android10/android')
lock = json.loads((REPO / 'docs/baselines/h700-v5i-usb-network-20261028/source-lock.json').read_text())
checked = {}
for name, record in lock['files'].items():
    if not name.startswith('system/vold/'):
        continue
    digest = hashlib.sha256((native / name).read_bytes()).hexdigest()
    assert digest == record['sha256'], name
    checked[name] = digest
assert 'system/vold/model/Disk.cpp' in checked
text = (native / 'system/vold/model/Disk.cpp').read_text()
for marker in ('hasRgspRomsGeometry', 'boot card whole-device fallback is forbidden',
               'boot card repartition denied', 'table != Table::kGpt || i != 8'):
    assert marker in text, marker
destination = REPO / 'out/dualabi-parity-20261101/vold-build-source-lock.json'
destination.write_text(json.dumps(checked, indent=2) + '\n')
print('PINNED_PROTECTED_VOLD_SOURCE_VERIFIED', len(checked), flush=True)

"""Prepare only the new light module; preserve existing native product inputs."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained

constrained()
native = Path('/home/lpf/h700-android10/android')
source = REPO / 'android/h700-android10/device/roc/rgsp/H700Light'
destination = native / 'device/roc/rgsp/H700Light'
out = REPO / 'out/rg34xxsp-readiness-20261102'
out.mkdir(exist_ok=True)
workroot = Path('/home/lpf/h700-readiness-20261102')
workroot.mkdir(exist_ok=True)
work = next(workroot / ('build-v%d' % n) for n in range(1, 100)
            if not (workroot / ('build-v%d' % n)).exists())
work.mkdir()

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

protected = [native / rel for rel in (
    'device/roc/rgsp/h700_rgsp.mk', 'device/roc/rgsp64proto/h700_rgsp64proto.mk',
    'hardware/aw/lights/de/lights.c', 'hardware/interfaces/light/2.0/default/Light.cpp')]
before = {str(p.relative_to(native)): sha(p) for p in protected}
for p in source.iterdir():
    assert p.is_file() and not p.is_symlink()
    assert b'\r' not in p.read_bytes(), p
    target = destination / p.name
    if target.exists() and target.read_bytes() != p.read_bytes():
        backup = work / ('before-' + p.name)
        shutil.copy2(target, backup)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or target.read_bytes() != p.read_bytes():
        shutil.copy2(p, target)
subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-pthread',
    '-I' + str(source), str(source / 'Backlight.cpp'),
    str(REPO / 'tools/readiness/backlight_test.cpp'), '-o', str(work / 'backlight_test')], check=True)
tests = subprocess.check_output([str(work / 'backlight_test')], text=True)
assert before == {str(p.relative_to(native)): sha(p) for p in protected}
record = {'native_protected_unchanged': before, 'work': str(work),
          'host_tests': tests.strip(), 'source': {p.name: sha(p) for p in source.iterdir()}}
(out / ('prepare-' + work.name + '.json')).write_text(json.dumps(record, indent=2) + '\n')
(out / 'latest-build.json').write_text(json.dumps(record, indent=2) + '\n')
print(tests.strip(), flush=True)

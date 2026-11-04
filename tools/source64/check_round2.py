"""Bounded host checks of the actual private storage code; no block devices."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import zlib

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained
constrained()
sys.path.insert(0, str(REPO / 'tools/source64/storage'))
import layout

OUT = REPO / 'out/roc-os-source64-round2-20261103'
ROOT = Path('/home/lpf/roc-os-source64-20261103')
WORK = next(ROOT / ('round2-test-v%d' % n) for n in range(1, 100) if not (ROOT / ('round2-test-v%d' % n)).exists())
WORK.mkdir()
PRODUCT = Path('/home/lpf/h700-android10/android/device/roc/roc_os_source64')
passed = []


def run(args, expected=(0,)):
    p = subprocess.run(list(map(str, args)), capture_output=True, text=True)
    with (WORK / 'commands.log').open('a') as f:
        f.write(json.dumps(list(map(str, args))) + '\n' + p.stdout + p.stderr + '\n')
    assert p.returncode in expected, (args, p.returncode, p.stdout, p.stderr)
    return p


helper = WORK / 'grow-gpt'
run(['gcc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-I', PRODUCT / 'Storage',
     PRODUCT / 'Storage/grow_gpt.c', '-o', helper])
prefix = Path('/home/lpf/h700-dualabi-image-20261031/prefix.candidate.raw')
with prefix.open('rb') as f:
    primary, backup = layout.derive(f.read(2048))
assert primary[1920:2048] == b'\0' * 128


def fixture(name, size, head=primary, tail=backup):
    p = WORK / (name + '.gpt-fixture')
    with p.open('xb') as f:
        f.truncate(size)
        f.seek(0); f.write(head)
        f.seek(8192); f.write(b'BOOT0-UNCHANGED')
        f.seek(layout.SEED_BYTES - 1536); f.write(tail)
    return p


def metadata(p):
    with p.open('rb') as f:
        head = f.read(2048)
        f.seek(-1536, os.SEEK_END); tail = f.read(1536)
        f.seek(8192); boot0 = f.read(15)
    return head, tail, boot0


for size in [layout.SEED_BYTES, 63864569856, 128 * 1024**3]:
    p = fixture(str(size), size)
    run([helper, '--check', p, '--image-test'], (0,) if size == layout.SEED_BYTES else (4,))
    run([helper, '--apply', p, '--image-test'])
    h, b, sentinel = metadata(p)
    expected_h, expected_b = layout.grow(primary, size)
    assert (h, b) == (expected_h, expected_b) and sentinel == b'BOOT0-UNCHANGED'
    assert h[1024:1792] == primary[1024:1792]  # All six protected entries.
    run([helper, '--check', p, '--image-test'])
    run([helper, '--apply', p, '--image-test'])
    assert metadata(p) == (h, b, sentinel)
    # Interrupt after backup durability but before the primary becomes valid.
    with p.open('r+b') as f:
        f.seek(512); f.write(b'TORN-GPT')
    run([helper, '--check', p, '--image-test'], (4,))
    run([helper, '--apply', p, '--image-test'])
    assert metadata(p) == (h, b, sentinel)
    passed.append('capacity/idempotence/backup-recovery:' + str(size))


def recalc(head):
    h = bytearray(head)
    struct.pack_into('<I', h, 600, zlib.crc32(h[1024:2048]))
    struct.pack_into('<I', h, 528, 0)
    struct.pack_into('<I', h, 528, zlib.crc32(h[512:604]))
    return bytes(h)


for name, offset in [('wrong-disk', 568), ('p8-used', 1920), ('system-start', 1568), ('userdata-guid', 1808)]:
    h = bytearray(primary); h[offset] ^= 1; h = recalc(h)
    p = fixture(name, layout.SEED_BYTES, h)
    before = metadata(p)
    run([helper, '--apply', p, '--image-test'], (1,))
    assert metadata(p) == before
    passed.append('reject-without-write:' + name)
p = fixture('corrupt-both', layout.SEED_BYTES)
with p.open('r+b') as f:
    f.seek(512); f.write(b'BAD-GPT!')
    f.seek(-512, os.SEEK_END); f.write(b'BAD-GPT!')
before = metadata(p)
run([helper, '--apply', p, '--image-test'], (1,))
assert metadata(p) == before
run([helper, '--apply', p], (1,))  # Regular files never accepted in device mode.
link = WORK / 'symlink-fixture'; link.symlink_to(p)
run([helper, '--apply', link, '--image-test'], (1,))
passed += ['reject-corrupt-both', 'reject-regular-without-test-flag', 'reject-symlink']

# Real offline ext4 growth, with a sentinel file preserved and no loop mount.
fs = WORK / 'userdata.ext4-fixture'
with fs.open('xb') as f: f.truncate(64 * 1024**2)
run(['mke2fs', '-q', '-F', '-t', 'ext4', '-U', layout.DATA_FS_UUID,
     '-O', '^metadata_csum,^64bit', '-E', 'lazy_itable_init=0,lazy_journal_init=0', fs])
sentinel = WORK / 'save-sentinel'; sentinel.write_bytes(b'user-save-must-survive\n')
run(['debugfs', '-w', '-R', 'write ' + str(sentinel) + ' /save-sentinel', fs])
run([helper, '--check-volume', fs, '--image-test'])
with fs.open('r+b') as f: f.truncate(128 * 1024**2)
run([helper, '--check-volume', fs, '--image-test'], (4,))
run(['e2fsck', '-f', '-p', fs], (0, 1))
run(['resize2fs', fs])
run([helper, '--check-volume', fs, '--image-test'])
run(['e2fsck', '-f', '-n', fs])
readback = run(['debugfs', '-R', 'cat /save-sentinel', fs]).stdout
assert readback == sentinel.read_text()
with fs.open('r+b') as f:
    f.seek(1024+104); f.write(b'\0' * 16)
run([helper, '--check-volume', fs, '--image-test'], (1,))
passed += ['real-ext4-growth-save-retention', 'reject-wrong-filesystem-UUID']

test = WORK / 'policy.cpp'
test.write_text('''#include "RocStoragePolicy.h"
#include <cassert>
int main() {
 for (const char* name : {"mmcblk0", "mmcblk1", "mmcblk7", "mmcblk12"}) {
  assert(rocTf2Path(std::string("/sys/devices/platform/soc/sdc2/mmc_host/mmc7/mmc7:1234/block/")+name));
  assert(!rocTf2Path(std::string("/sys/devices/platform/soc/sdc0/mmc_host/mmc7/mmc7:1234/block/")+name));
 }
 assert(!rocTf2Path("/sys/devices/platform/soc/sdc20/mmc_host/mmc1/block/mmcblk1"));
 assert(!rocTf2Path("/sys/devices/platform/soc/sdc2/mmc_host/../block/mmcblk1"));
 assert(!rocTf2Path(""));
}
''')
run(['g++', '-std=c++11', '-Wall', '-Wextra', '-Werror', '-I', PRODUCT / 'Vold', test, '-o', WORK / 'policy-test'])
run([WORK / 'policy-test'])
passed.append('TF2-controller-policy-independent-of-MMC-number')

# Private product endpoint compatibility, tested over every logical level.
run(['g++', '-std=c++11', '-Wall', '-Wextra', '-Werror', '-I', PRODUCT / 'Light',
     REPO / 'tools/source64/backlight_endpoint_test.cpp', PRODUCT / 'Light/Backlight.cpp', '-o', WORK / 'backlight-test'])
run([WORK / 'backlight-test'])
passed.append('selected-Light-256-logical-levels-monotonic-254-endpoint-ABI-errors')
for file in [PRODUCT / 'configs/roc-factory.sh', PRODUCT / 'configs/roc-os-branding.sh', REPO / 'tools/source64/storage/grow_userdata.sh']:
    run(['bash', '-n', file])
contract = json.loads((OUT / 'boot-contract.json').read_text())
run(['sh', '-n', Path(contract['work']) / 'init'])
passed.append('boot-and-provisioning-shell-syntax')
from test_factory import checks
passed.extend(checks(PRODUCT, WORK))
classes = WORK / 'select-fallback-classes'
classes.mkdir()
jdk = Path('/home/lpf/h700-android10/android/prebuilts/jdk/jdk9/linux-x86/bin')
run([jdk / 'javac', '-d', classes,
     PRODUCT / 'Navigation/src/com/roc/rgsp/navtrial/MouseHotkey.java',
     REPO / 'tools/source64/SelectFallbackTest.java'])
run([jdk / 'java', '-Xmx256m', '-cp', classes, 'com.roc.rgsp.navtrial.SelectFallbackTest'])
passed.append('Select-fallback-without-flag-and-chord-preservation')

# Thermal model tests use regular temporary files, never thermal emulation nodes.
run(['g++', '-std=c++14', '-Wall', '-Wextra', '-Werror', '-I', PRODUCT / 'Thermal',
     REPO / 'tools/source64/thermal_model_test.cpp', '-o', WORK / 'thermal-model-test'])
run([WORK / 'thermal-model-test', WORK / 'thermal-fixture'])
passed.append('Thermal-real-unit-trip-boundaries-missing-invalid-and-cooling')

result = {'passed': True, 'work': str(WORK), 'cases': passed, 'case_count': len(passed),
          'devices_accessed': False, 'synthetic_fixtures_not_flashable': True, 'whole_card_image_created': False}
(OUT / (WORK.name + '.json')).write_text(json.dumps(result, indent=2)+'\n')
print('SOURCE64_ROUND2_HOST_CHECKS_PASS', len(passed), flush=True)

#!/usr/bin/env python3
"""Persist the tested P1c properties on the exact running P1b spare card.

Plan-only by default. Uses an atomic normal filesystem replacement, never raw
blocks. Retains the original property file and a guarded rollback script locally
and on the spare. Does not reboot or change the release card/image.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out/dualabi-runtime-p1c-20261031'
REMOTE = '/data/local/tmp/h700-p1c-properties-20261031'
TARGET = '/system/etc/prop.default'
REVISION = 'p1c-vndk29-heap-20261031'
OVERRIDES = {'ro.vndk.version': '29', 'dalvik.vm.heapgrowthlimit': '128m',
             'dalvik.vm.heapsize': '256m', 'ro.h700.prototype.runtime': REVISION,
             'persist.vendor.hwc.software_vsync': 'true'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def patched(data, include_vsync=True):
    overrides = dict(OVERRIDES)
    if not include_vsync:
        del overrides['persist.vendor.hwc.software_vsync']
    text = data.decode('utf-8')
    if '\r' in text:
        raise ValueError('Unexpected property line endings')
    for key in overrides:
        if any(line.startswith(key + '=') for line in text.splitlines()):
            raise ValueError('Parent already declares a prototype override')
    return (text.rstrip('\n') + '\n\n# P1c: explicit Android 10 VNDK and retained BSP heap limits.\n' +
            ''.join(k + '=' + v + '\n' for k, v in overrides.items())).encode('utf-8')


def main():
    global OUT, REMOTE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--complete-vsync', action='store_true',
                        help='Only complete the retained, exact four-property intermediate P1c')
    args = parser.parse_args()
    if not args.execute:
        print('PLAN: exact P1b USB/card/root mount guards; pinned original prop.default; '
              'preserve original and rollback; atomic five-property replacement; '
              'restore read-only root; no reboot or raw/card-layout writes.')
        return
    original_out = OUT
    if args.complete_vsync:
        OUT = OUT / 'vsync'
        REMOTE += '-vsync'
    OUT.mkdir(exist_ok=True)
    if (OUT / 'properties-attempt.private.json').exists():
        raise ValueError('Previous attempt retained; inspect, do not replay')
    serial = json.loads((ROOT / 'LOCAL_PRESERVE_H700_BASELINE_20261028/device-session.private.json').read_text(encoding='utf-8'))['serial']
    cid = json.loads((ROOT / 'out/dualabi-prototype-image-20261031/card-before.private.json').read_text(encoding='utf-8'))['cid']
    adb = str(Path(os.environ['LOCALAPPDATA']) / 'Android/Sdk/platform-tools/adb.exe')

    def call(*arguments, timeout=25):
        try:
            result = subprocess.run([adb, '-s', serial, *arguments], capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            receipt = {'rc': 'timeout', 'stdout': (error.stdout or b'').decode(errors='replace'),
                       'stderr': (error.stderr or b'').decode(errors='replace')}
            (OUT / 'properties-failure.private.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
            raise RuntimeError('Prototype command timed out; inspect private receipt before any retry') from None
        receipt = {'rc': result.returncode, 'stdout': result.stdout.decode(errors='replace').replace('\r', ''),
                   'stderr': result.stderr.decode(errors='replace')}
        if result.returncode:
            (OUT / 'properties-failure.private.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
            raise RuntimeError('Prototype command failed; private receipt retained')
        return receipt['stdout'].strip()

    if subprocess.check_output([adb, '-d', 'get-serialno'], timeout=10).decode().strip() != serial:
        raise ValueError('Wrong USB device')
    expected = [serial, cid, 'rgsp', 'rg34xxsp', 'rg34xxsp-dualabi-gsi10-p1-20261031',
                'p1b-ramdisk-handoff-20261031', '0', '29', '1']
    actual = call('shell', 'getprop ro.serialno; cat /sys/block/mmcblk0/device/cid; '
                  'getprop ro.product.device; getprop persist.vendor.rgsp.input_profile; '
                  'getprop ro.h700.prototype; cat /system/etc/h700-prototype/boot-entry-revision; '
                  'id -u; getprop ro.build.version.sdk; getprop sys.boot_completed')
    if actual.splitlines() != expected:
        raise ValueError('Wrong card, build, profile or boot state')
    guard = f'''[ "$(getprop ro.serialno)" = {shlex.quote(serial)} ]
[ "$(cat /sys/block/mmcblk0/device/cid)" = {shlex.quote(cid)} ]
[ "$(getprop ro.h700.prototype)" = rg34xxsp-dualabi-gsi10-p1-20261031 ]
[ "$(cat /system/etc/h700-prototype/boot-entry-revision)" = p1b-ramdisk-handoff-20261031 ]
[ "$(id -u)" = 0 ]
dev=$(cat /sys/block/mmcblk0/mmcblk0p5/dev)
awk -v dev="$dev" '$3==dev && $5=="/" && $6 ~ /^ro(,|$)/ {{found=1}} END {{exit !found}}' /proc/self/mountinfo
'''
    call('shell', 'set -eu\n' + guard)
    overlay = json.loads((ROOT / 'docs/baselines/rg34xxsp-dualabi-spare-p1-20261031/overlay-lock.json').read_text(encoding='utf-8'))
    old_sha = overlay['system'][TARGET]['sha256']
    base_data = None
    if args.complete_vsync:
        base_data = (original_out / 'prop.default.before').read_bytes()
        if digest(base_data) != old_sha:
            raise ValueError('Original P1b property backup changed')
        old_sha = digest(patched(base_data, include_vsync=False))
    if call('shell', 'sha256sum ' + TARGET).split()[0] != old_sha:
        raise ValueError('Pinned parent property file changed')
    original = OUT / 'prop.default.before'
    call('pull', TARGET, str(original))
    if digest(original.read_bytes()) != old_sha:
        raise ValueError('Backup mismatch')
    candidate = OUT / 'prop.default.p1c'
    candidate.write_bytes(patched(base_data if base_data is not None else original.read_bytes()))
    new_sha = digest(candidate.read_bytes())
    if call('shell', f'if [ -e {REMOTE} ]; then echo EXISTS; else echo NEW; fi') != 'NEW':
        raise ValueError('Remote preservation directory exists')
    call('shell', f'mkdir {REMOTE}; chmod 0700 {REMOTE}')
    call('push', str(original), REMOTE + '/prop.default.before')
    call('push', str(candidate), REMOTE + '/prop.default.p1c')

    def replacement(source, before_sha, after_sha):
        return 'set -eu\n' + guard + f'''[ "$(sha256sum {TARGET} | cut -d ' ' -f 1)" = {before_sha} ]
[ "$(sha256sum {source} | cut -d ' ' -f 1)" = {after_sha} ]
trap 'mount -o remount,ro /dev/mmcblk0p5 /' EXIT
mount -o remount,rw /dev/mmcblk0p5 /
cp {source} /system/etc/.prop.default.h700-p1c.tmp
chown 0:0 /system/etc/.prop.default.h700-p1c.tmp
chmod 0644 /system/etc/.prop.default.h700-p1c.tmp
chcon u:object_r:system_file:s0 /system/etc/.prop.default.h700-p1c.tmp
[ "$(sha256sum /system/etc/.prop.default.h700-p1c.tmp | cut -d ' ' -f 1)" = {after_sha} ]
mv /system/etc/.prop.default.h700-p1c.tmp {TARGET}
sync
mount -o remount,ro /dev/mmcblk0p5 /
awk -v dev="$dev" '$3==dev && $5=="/" && $6 ~ /^ro(,|$)/ {{found=1}} END {{exit !found}}' /proc/self/mountinfo
[ "$(sha256sum {TARGET} | cut -d ' ' -f 1)" = {after_sha} ]
echo PROPERTY_REPLACEMENT_VERIFIED_ROOT_RO
'''

    for name, content in [('apply', replacement(REMOTE + '/prop.default.p1c', old_sha, new_sha)),
                          ('rollback', replacement(REMOTE + '/prop.default.before', new_sha, old_sha))]:
        file = OUT / ('properties-' + name + '.private.sh')
        file.write_text(content, encoding='utf-8', newline='\n')
        call('push', str(file), REMOTE + '/' + name + '.sh')
        call('shell', 'sh -n ' + REMOTE + '/' + name + '.sh')
    boot_id = call('shell', 'cat /proc/sys/kernel/random/boot_id')
    receipt = {'old_sha256': old_sha, 'new_sha256': new_sha, 'boot_id': boot_id, 'attempt_started': True}
    (OUT / 'properties-attempt.private.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    result = call('shell', 'sh ' + REMOTE + '/apply.sh', timeout=45)
    if call('shell', 'cat /proc/sys/kernel/random/boot_id') != boot_id:
        raise ValueError('Unexpected reboot')
    (OUT / 'properties-result.private.json').write_text(json.dumps({'result': result, **receipt}, indent=2), encoding='utf-8')
    print(result)


if __name__ == '__main__':
    main()

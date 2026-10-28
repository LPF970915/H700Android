"""Apply or roll back one checksum-pinned Navigation APK on an identified eng H700.

This updates the existing package through PackageManager. No data clearing,
system remount, reboot, boot/card writes, signing keys or network ADB discovery.
The package manifest and both APKs must be supplied from the same local bundle.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

PACKAGE = 'com.roc.rgsp.navtrial'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', required=True)
    parser.add_argument('--session', required=True, type=Path)
    parser.add_argument('--bundle', required=True, type=Path)
    parser.add_argument('--rollback', action='store_true')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    serial = json.loads(args.session.read_text(encoding='utf-8'))['serial']
    assert re.fullmatch(r'[A-Za-z0-9]+', serial), 'Use the saved USB serial'
    def adb(*parts):
        return subprocess.check_output([args.adb, '-s', serial, *map(str, parts)],
            timeout=90).decode('utf-8', 'replace').replace('\r', '')
    def shell(command): return adb('shell', command)
    assert shell('getprop ro.serialno').strip() == serial, 'Serial mismatch'
    assert shell('getprop ro.product.device').strip() == 'rgsp'
    assert shell('getprop ro.product.model').strip() in ('RGSP H700', 'RGSP_H700')
    assert shell('getprop persist.vendor.rgsp.input_profile').strip() == 'rg34xxsp'
    assert shell('getprop ro.debuggable').strip() == '1', 'Development build required'
    assert shell('id -u').strip() == '0', 'Development root session required'
    manifest = json.loads((args.bundle / 'navigation-update.json').read_text(encoding='utf-8'))
    assert manifest['package'] == PACKAGE
    records = manifest['artifacts']
    for name in ('before', 'after'):
        item = records[name]
        assert re.fullmatch(r'[A-Za-z0-9_.-]+\.apk', item['file'])
        local = args.bundle / item['file']
        assert local.stat().st_size == item['bytes']
        assert hashlib.sha256(local.read_bytes()).hexdigest() == item['sha256'], 'APK hash mismatch'
    def installed_sha():
        paths = shell('pm path ' + PACKAGE).strip().splitlines()
        assert len(paths) == 1 and paths[0].startswith('package:/'), 'Unexpected split/path'
        path = paths[0][8:]
        assert re.fullmatch(r'/[A-Za-z0-9_./=+-]+\.apk', path), 'Unsafe package path'
        digest = shell("sha256sum '" + path + "'").split()[0]
        assert re.fullmatch(r'[0-9a-f]{64}', digest)
        return digest
    current = installed_sha()
    assert current in {records['before']['sha256'], records['after']['sha256']}, 'Unrecognized installed APK'
    chosen = records['before' if args.rollback else 'after']
    plan = {'operation': 'rollback' if args.rollback else 'upgrade', 'current_sha256': current,
            'target_sha256': chosen['sha256'], 'data_clear': False, 'reboot': False}
    print(json.dumps(plan, indent=2), flush=True)
    if not args.execute:
        print('PLAN_ONLY: pass --execute to install'); return
    if current != chosen['sha256']:
        flags = ['-r', '-d'] if args.rollback else ['-r']
        result = adb('install', *flags, args.bundle / chosen['file'])
        assert 'Success' in result, result
    assert installed_sha() == chosen['sha256'], 'Installed readback mismatch'
    print('INSTALLED_APK_SHA256_VERIFIED')


if __name__ == '__main__':
    main()

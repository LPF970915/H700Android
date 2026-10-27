"""Build a reversible local system-partition delta; never open a physical disk.

Run with WSL Python. The delivered v5i stage and full IMG remain unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


SYSTEM_SHA = '5377190d2b8955c168e100a1e444aedbd1716c57ce7ccd7c545e645c8eaf2af1'
HELPER_SHA = '60ea97958d6ada337a8f908496781fe1c956095d16a05fafb3393610b1891d74'
STAGE = 'out/h700-v5i-dpad-20261027-native35-notouch-stage'
RC_PATH = '/system/etc/init/h700-wifi-adb-recovery.rc'
SH_PATH = '/system/bin/h700-wifi-adb-recovery.sh'

RC = '''# Temporary development-card recovery. Remove this file to undo autostart.
on property:sys.boot_completed=1
    start h700-wifi-adb-recovery

service h700-wifi-adb-recovery /system/bin/sh /system/bin/h700-wifi-adb-recovery.sh
    class late_start
    user root
    group root shell log
    seclabel u:r:su:s0
    disabled
    oneshot
'''

SH = '''#!/system/bin/sh
# Temporary recovery; keep the existing source-restricted debug helper intact.
set -eu
export PATH=/system/bin:/vendor/bin
[ "$(id -u)" = 0 ]
[ "$(getprop ro.product.device)" = rgsp ]
[ "$(getprop sys.boot_completed)" = 1 ]
# The owner's USB debugging choice also gates this recovery session.
[ "$(settings get global adb_enabled)" = 1 ] || exit 0
umask 077
exec >>/data/local/tmp/h700-wifi-adb-recovery.log 2>&1
helper=/system/bin/rgsp-wifi-adb-session.sh
expected=60ea97958d6ada337a8f908496781fe1c956095d16a05fafb3393610b1891d74
[ "$(sha256sum "$helper" | cut -d ' ' -f 1)" = "$expected" ]
echo "H700_RECOVERY_START $(date)"
sh "$helper"
echo H700_RECOVERY_COMPLETE
'''


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(args, receipt=None):
    result = subprocess.run([str(x) for x in args], capture_output=True, text=True)
    if receipt:
        receipt.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f'{args[0]} failed ({result.returncode}): {result.stdout}{result.stderr}')
    return result.stdout + result.stderr


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--target-ip', default='', help='Optional private receipt metadata')
    parser.add_argument('--target-mac', default='', help='Optional private receipt metadata')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if output.exists() or not output.is_relative_to(root / 'out'):
        raise ValueError('A new directory inside workspace out is required')
    stage = root / STAGE
    source = stage / 'system.raw.img'
    if source.stat().st_size != 8589934592 or sha(source) != SYSTEM_SHA:
        raise ValueError('Pinned v5i system image mismatch')
    output.mkdir()
    (output / 'h700-wifi-adb-recovery.rc').write_text(RC)
    (output / 'h700-wifi-adb-recovery.sh').write_text(SH)
    run(['bash', '-n', output / 'h700-wifi-adb-recovery.sh'])
    verifier = Path('/home/lpf/h700-android10/android/out/host/linux-x86/bin/host_init_verifier')
    run([verifier, output / 'h700-wifi-adb-recovery.rc'], output / 'init-verifier.txt')
    context = output / 'system-file.context'
    context.write_bytes(b'u:object_r:system_file:s0\0')
    patched = output / 'system.recovery.raw.img'
    print('COPY_LOCAL_SYSTEM_IMAGE', flush=True)
    run(['cp', '--sparse=always', '--reflink=auto', source, patched])
    commands = []
    for local, target, mode in [
        ('h700-wifi-adb-recovery.rc', RC_PATH, '0100644'),
        ('h700-wifi-adb-recovery.sh', SH_PATH, '0100755'),
    ]:
        commands.extend([
            f'write {output / local} {target}',
            f'set_inode_field {target} mode {mode}',
            f'set_inode_field {target} uid 0',
            f'set_inode_field {target} gid 0',
            f'ea_set -f {context} {target} security.selinux',
        ])
    command_file = output / 'debugfs.commands'
    command_file.write_text('\n'.join(commands) + '\n')
    run(['debugfs', '-w', '-f', command_file, patched], output / 'debugfs-write.txt')
    run(['e2fsck', '-f', '-n', patched], output / 'system.fsck.txt')
    # debugfs may report command errors with exit code zero: extract every file.
    extracted = output / 'extracted'
    extracted.mkdir()
    components = json.loads((stage / 'components.json').read_text())
    verified = {}
    for key, digest in components.items():
        if not key.startswith('system:'):
            continue
        target = key.split(':', 1)[1]
        local = extracted / target.removeprefix('/')
        local.parent.mkdir(parents=True, exist_ok=True)
        run(['debugfs', '-R', f'dump {target} {local}', patched])
        if sha(local) != digest:
            raise ValueError('Existing component changed: ' + key)
        verified[key] = digest
    for local_name, target, content in [
        ('h700-wifi-adb-recovery.rc', RC_PATH, RC),
        ('h700-wifi-adb-recovery.sh', SH_PATH, SH),
    ]:
        local = extracted / local_name
        run(['debugfs', '-R', f'dump {target} {local}', patched])
        if local.read_bytes() != content.encode():
            raise ValueError('New recovery file mismatch: ' + target)
        attrs = run(['debugfs', '-R', f'ea_list {target}', patched])
        if 'u:object_r:system_file:s0' not in attrs:
            raise ValueError('SELinux file context missing: ' + target)
    print('COMPARE_BLOCKS_AND_VERIFY_REVERSE_DELTA', flush=True)
    before_file = output / 'before.bin'
    after_file = output / 'after.bin'
    changes = []
    reverse = hashlib.sha256()
    final = hashlib.sha256()
    with source.open('rb') as original, patched.open('rb') as modified, \
            before_file.open('xb') as before, after_file.open('xb') as after:
        offset = 0
        payload_offset = 0
        while True:
            old = original.read(4 * 1024 * 1024)
            new = modified.read(4 * 1024 * 1024)
            if not old:
                if new:
                    raise ValueError('Patched image grew')
                break
            if len(old) != len(new):
                raise ValueError('Image length mismatch')
            final.update(new)
            restored = bytearray(new)
            if old != new:
                for at in range(0, len(old), 4096):
                    left, right = old[at:at + 4096], new[at:at + 4096]
                    if left == right:
                        continue
                    changes.append({
                        'partition_offset': offset + at,
                        'payload_offset': payload_offset,
                        'bytes': len(left),
                        'before_sha256': hashlib.sha256(left).hexdigest(),
                        'after_sha256': hashlib.sha256(right).hexdigest(),
                    })
                    before.write(left)
                    after.write(right)
                    restored[at:at + len(left)] = left
                    payload_offset += len(left)
            reverse.update(restored)
            offset += len(old)
    if reverse.hexdigest() != SYSTEM_SHA or not changes or payload_offset > 4 * 1024 * 1024:
        raise ValueError('Reverse-delta verification or size bound failed')
    manifest = {
        'status': 'OFFLINE_PREPARED_FSCK_COMPONENTS_AND_REVERSE_DELTA_VERIFIED_NOT_DEVICE_TESTED',
        'source_stage': STAGE,
        'system_offset': 222298112,
        'system_bytes': 8589934592,
        'before_system_sha256': SYSTEM_SHA,
        'after_system_sha256': final.hexdigest(),
        'before_payload_sha256': sha(before_file),
        'after_payload_sha256': sha(after_file),
        'changed_bytes': payload_offset,
        'blocks': changes,
        'new_files': [RC_PATH, SH_PATH],
        'unchanged_system_components': verified,
        'allowed_client_ipv4': '192.168.31.211',
        'ipv6_tcp5555': 'DROP',
        'requires_adb_enabled': True,
        'observed_target_ip': args.target_ip,
        'owner_reported_wlan_mac': args.target_mac,
        'writes_to_physical_device': False,
        'reverse_delta_matches_original': True,
    }
    (output / 'recovery-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({k: v for k, v in manifest.items() if k not in ('blocks', 'unchanged_system_components')}, indent=2), flush=True)


if __name__ == '__main__':
    main()

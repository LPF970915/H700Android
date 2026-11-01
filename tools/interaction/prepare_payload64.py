"""Create a ROM-free ARM64 payload using only pinned factory assets and official APKs."""
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
import package_h700_v6a as base
base.constrained()
ROOT = Path('/home/lpf/h700-dualabi-parity-20261101')
WORK = ROOT / 'payload64-v1'
WORK.mkdir(exist_ok=False)
OUT = REPO / 'out/dualabi-parity-20261101'
payload = WORK / 'payload'
payload.mkdir()
source = Path('/home/lpf/h700-release-v6b-20261030/system.candidate.raw')
parent = json.loads((REPO / 'docs/baselines/rg34xxsp-v6b-mt-20261030/image-lock.json').read_text())
system_range = next(r for r in parent['ranges'] if r['name'] == 'system')
assert source.stat().st_size == system_range['bytes'] and base.sha(source) == system_range['sha256']
apps = json.loads((OUT / 'preinstall64-audit-v1.json').read_text())['apps']
assert len(apps) == 7 and all(a['install_abi'] == 'arm64-v8a' for a in apps)

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

for directory in ('media', 'themes', 'collections'):
    subprocess.run(['debugfs', '-R', f'rdump /system/etc/h700-preinstall/{directory} {payload}', str(source)],
                   check=True, capture_output=True)
    assert (payload / directory).is_dir(), directory
media_count = 0
for file in sorted((payload / 'media').rglob('*')):
    if file.is_file():
        assert file.suffix.lower() in base.MEDIA
        media_count += 1
for file in sorted((payload / 'themes').rglob('*')):
    if file.is_file():
        assert file.suffix.lower() in base.THEME and file.suffix.lower() not in base.ROM
for file in sorted((payload / 'collections').rglob('metadata.pegasus.txt')):
    text = file.read_text()
    assert 'com.retroarch.ra32' in text and '@H700_ROMS_ROOT@' in text
    file.write_text(text.replace('com.retroarch.ra32', 'com.retroarch.aarch64'), encoding='utf-8', newline='\n')
game_count = sum(len(re.findall(r'^game:', p.read_text(), re.M))
                 for p in (payload / 'collections').rglob('metadata.pegasus.txt'))
assert game_count == 604
lines = []
for app in apps:
    file = REPO / app['file']
    assert base.sha(file) == app['sha256'] and file.stat().st_size == app['bytes']
    target = payload / 'apks' / (app['id'] + '.apk')
    target.parent.mkdir(exist_ok=True)
    shutil.copyfile(file, target)
    lines.append(' '.join((app['package'], target.name, app['sha256'], 'arm64-v8a')))
write(payload / 'apps.list', ('\n'.join(lines) + '\n').encode())

old_external = base.dump(source, '/system/etc/h700-preinstall/external.tar', WORK / 'external.arm32.tar')
with tarfile.open(old_external) as incoming, tarfile.open(payload / 'external.tar', 'w', format=tarfile.PAX_FORMAT) as target:
    for member in incoming.getmembers():
        assert member.isfile() and not member.issym() and not member.islnk()
        base.relative(member.name)
        name = member.name.replace('com.retroarch.ra32', 'com.retroarch.aarch64')
        data = incoming.extractfile(member).read()
        if name.endswith(('.txt', '.cfg', '.glslp', '.lua', '.ini', '.opt', '.cht', '.json')):
            data = data.replace(b'com.retroarch.ra32', b'com.retroarch.aarch64')
        base.tar_add(target, name, data, member.mode)
nova = base.dump(source, '/system/etc/h700-preinstall/nova-private.tar', WORK / 'nova-private.tar')
shutil.copyfile(nova, payload / 'nova-private.tar')
ra = next(a for a in apps if a['id'] == 'RetroArch')
core_locks = []
with tarfile.open(payload / 'retroarch-private.tar', 'w', format=tarfile.PAX_FORMAT) as target, zipfile.ZipFile(REPO / ra['file']) as apk:
    for name in sorted(apk.namelist()):
        if not name.startswith('assets/') or name.endswith('/'):
            continue
        relative = name[len('assets/'):]
        base.relative(relative)
        data = apk.read(name)
        if data.startswith(b'\x7fELF'):
            assert data[:5] == b'\x7fELF\x02' and int.from_bytes(data[18:20], 'little') == 183, name
        base.tar_add(target, relative, data)
    base.tar_add(target, 'autoconfig/android/H700_ANBERNIC_keys.cfg',
                 (REPO / 'config/retroarch/android/H700_ANBERNIC_keys.cfg').read_bytes())
    for name in ('mgba', 'gpsp', 'vbam'):
        lock = json.loads((OUT / 'arm64-cores' / (name + '.json')).read_text())
        file = OUT / 'arm64-cores' / (name + '_libretro_android.so')
        data = file.read_bytes()
        assert base.sha(file) == lock['so_sha256'] and data[:5] == b'\x7fELF\x02'
        assert int.from_bytes(data[18:20], 'little') == 183
        base.tar_add(target, 'cores/' + file.name, data, 0o700)
        core_locks.append(lock)

installer = (REPO / 'android/h700-android10/device/roc/rgsp/h700-preinstall-v6b.sh').read_text()
assert installer.count('pm install -g --user 0 "$src/apks/$apk"') == 1
installer = installer.replace('v6b-rg34xxsp-20261030', 'arm64-parity-test2-20261101')
installer = installer.replace('/data/local/h700-preinstall-v6b', '/data/local/h700-preinstall-arm64-test2')
installer = installer.replace('[ ! -f "$state/complete" ] || exit 0',
    '[ ! -f "$state/complete" ] || { setprop sys.h700.preinstall complete; exit 0; }')
installer = installer.replace('while read -r pkg apk digest; do', 'while read -r pkg apk digest abi; do\n    [ "$abi" = arm64-v8a ]')
installer = installer.replace('pm install -g --user 0 "$src/apks/$apk"', 'pm install -g --user 0 --abi "$abi" "$src/apks/$apk"')
needle='    [ "$(sha256sum "$installed" | cut -d \' \' -f 1)" = "$digest" ]'
assert installer.count(needle) == 1
installer = installer.replace(needle, needle + '\n    dumpsys package "$pkg" | grep -Fq "primaryCpuAbi=arm64-v8a"')
installer = installer.replace('com.retroarch.ra32', 'com.retroarch.aarch64')
installer = installer.replace('Eight selected applications', 'Seven ARM64 selected applications')
write(WORK / 'h700-preinstall.sh', installer.encode())
subprocess.run(['bash', '-n', str(WORK / 'h700-preinstall.sh')], check=True)
subprocess.run(['bash', '-n', str(REPO / 'tools/interaction/test2_setup.sh')], check=True)
write(payload / 'README.txt', b'RG34XXSP 2GB ARM64 Parity Test2. Seven ARM64 apps; QQ Music TV omitted because official TV APK is ARM32. No ROM/BIOS/accounts/saves. Copy your own games to ROMS/PegasusGBA/Roms. Fresh boot and hardware acceptance required.\n')
files = {p.relative_to(payload).as_posix(): base.sha(p) for p in sorted(payload.rglob('*')) if p.is_file()}
write(payload / 'SHA256SUMS', ''.join(digest + '  ' + name + '\n' for name, digest in files.items()).encode())
files['SHA256SUMS'] = base.sha(payload / 'SHA256SUMS')
record = {'apps': apps, 'files': files, 'media_files': media_count, 'game_entries': game_count,
          'rom_files': 0, 'bios_files': 0, 'accounts_saves': False, 'cores': core_locks,
          'bytes': sum(p.stat().st_size for p in payload.rglob('*') if p.is_file()),
          'installer_sha256': base.sha(WORK / 'h700-preinstall.sh')}
(OUT / 'payload64-v1.json').write_text(json.dumps(record, indent=2) + '\n')
print('ROM_FREE_ARM64_PAYLOAD_COMPLETE', len(files), 'files', record['bytes'], flush=True)

#!/usr/bin/env python3
"""Build the ROM-free RG34XXSP candidate, only inside the low-pressure wrapper.

No block devices, mounts, device commands, private userdata or signing keys.
The immutable v5i gzip is verified while splitting its sparse factory ranges.
"""
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out/h700-v6a-preinstall-20261030'
WORK = Path('/home/lpf/h700-release-v6a-20261030')
PRODUCT = ROOT / 'android/h700-android10/device/roc/rgsp'
STAGE = ROOT / 'out/pegasus-gba-20261030/stage'
PAYLOAD = '/system/etc/h700-preinstall'
SIZE = 32434554368
BASE = '3fd34fef4d5a2275f14023dba5dc488330ab0669a50889e8b748e30c9f3e68cd'
RANGES = [('prefix', 0, 222298112), ('system', 222298112, 8589934592),
          ('vendor', 8812232704, 2147483648), ('factory_tail', 10959716352, 21474838016)]
PIN = {
    'system:/system/priv-app/AT4K/AT4K.apk': ('out/rg34xxsp-dev-20261028/AT4K-rg34xxsp.apk', '93041269d215dd450f4b559cb4fe57337267753d6ff7444ca142e17d07d997cf'),
    'system:/system/app/RGSPNavigation/RGSPNavigation.apk': ('out/force-landscape-20261029/nav.after.apk', 'c83a009d65e6786814a0763a6233d8557c3e5813b9dd6eda8e4aca6bca7b8014'),
    'system:/system/priv-app/H700Lid/H700Lid.apk': ('out/rg34xxsp-lid-20261029/H700Lid.apk', '44b12e15027132eb65171adb3058fa99b0f23056f39a4367a2ec6e5d98948c8d'),
    'system:/system/priv-app/H700Rotation/H700Rotation.apk': ('out/force-landscape-20261029/H700Rotation.apk', 'fd932f8ec9563d2fb4bca2d037e0c475c9698e48f18b612d4b13e606c643aabc'),
    'system:/system/framework/services.jar': ('out/force-landscape-20261029/services.force-landscape.jar', 'd291bfeadf578ae923c4dc11577a78724df78e7b54503ebf2e3f80da0d916c11'),
    'vendor:/modules/h700_stick_axes.ko': ('android/h700-android10/device/roc/rgsp/input/prebuilt/h700_stick_axes.ko', '9c8eacf887cd9d00f5416c05b24118ce625e4deef73003f79ea1805c6a31faf5'),
}
MEDIA = {'.png', '.jpg', '.jpeg', '.mp4', '.webm'}
THEME = MEDIA | {'.qml', '.js', '.svg', '.ttf', '.otf', '.mp3', '.txt', '.cfg', '.md', ''}
ROM = {'.gba', '.gb', '.gbc', '.nes', '.sfc', '.smc', '.nds', '.iso', '.cso', '.chd', '.bin', '.bios', '.sav', '.srm', '.state', '.7z', '.zip'}


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def regular(p):
    p = Path(p)
    if not stat.S_ISREG(p.lstat().st_mode) or p.is_symlink():
        raise ValueError('Regular, non-symlink input required: ' + str(p))
    return p


def relative(name):
    p = PurePosixPath(name)
    if p.is_absolute() or not p.parts or any(x in ('..', '.') for x in p.parts) or any(c in name for c in '\n\r\x00\\'):
        raise ValueError('Unsafe relative path: ' + name)
    return p


def write(p, content):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding='utf8', newline='\n')
    return p


def jsonwrite(p, content):
    write(p, json.dumps(content, ensure_ascii=False, indent=2) + '\n')


def constrained():
    if os.name != 'posix' or os.sched_getaffinity(0) != {0, 1} or os.getpriority(os.PRIO_PROCESS, 0) != 19:
        raise RuntimeError('Use tools/build_h700_low_pressure.ps1 -Targets H700ReleaseImage -Execute')
    cg = next(x.split(':', 2)[2] for x in Path('/proc/self/cgroup').read_text().splitlines() if x.startswith('0::'))
    c = Path('/sys/fs/cgroup') / cg.lstrip('/')
    quota, period = (c / 'cpu.max').read_text().split()
    if quota == 'max' or int(quota) > int(period) or int((c / 'memory.max').read_text()) > 6 * 1024**3:
        raise RuntimeError('CPU or RAM cap missing')
    if int((c / 'memory.swap.max').read_text()) > 512 * 1024**2:
        raise RuntimeError('Swap cap missing')


def sparse_write(f, block):
    if block.count(0) == len(block):
        f.seek(len(block), 1)
    else:
        f.write(block)


def split_seed():
    marker = WORK / 'seed-verified.json'
    if marker.exists():
        record = json.loads(marker.read_text())
        for name, _, length in RANGES:
            p = WORK / (name + '.raw')
            if p.stat().st_size != length or sha(p) != record[name]:
                raise ValueError('Existing seed stage changed: ' + name)
        return record
    source = regular(ROOT / 'out/H700_Android_SingleCard_v5i_ChineseDpadWifiGfx.img.gz')
    locked = json.loads((ROOT / 'docs/baselines/h700-v5i-usb-network-20261028/image-manifest.json').read_text())
    if locked['sha256'] != BASE:
        raise ValueError('Unknown seed manifest')
    expected = {r['name']: r['sha256'] for r in locked['ranges']}
    full = hashlib.sha256()
    record = {}
    with gzip.open(source, 'rb') as src:
        for name, _, length in RANGES:
            print('SEED_SPLIT ' + name, flush=True)
            p = WORK / (name + '.raw')
            if p.exists():
                raise ValueError('Incomplete seed stage retained; select a new work path or inspect it: ' + str(p))
            h = hashlib.sha256()
            with p.open('xb') as dst:
                left = length
                while left:
                    b = src.read(min(left, 8 * 1024**2))
                    if not b:
                        raise ValueError('Short seed')
                    full.update(b); h.update(b); sparse_write(dst, b); left -= len(b)
                dst.truncate(length)
            expected_key = 'factory_data_roms_gpt' if name == 'factory_tail' else name
            if h.hexdigest() != expected[expected_key]:
                raise ValueError('Seed range mismatch: ' + name)
            record[name] = h.hexdigest()
        if src.read(1) or full.hexdigest() != BASE:
            raise ValueError('Full v5i seed mismatch')
    jsonwrite(marker, record)
    return record


def tar_add(t, name, content, mode=0o644):
    relative(name)
    info = tarfile.TarInfo(name)
    info.size = len(content); info.mode = mode; info.mtime = 0
    t.addfile(info, io.BytesIO(content))


def gba_config():
    text = (ROOT / 'config/pegasus/retroarch-gba.cfg').read_text()
    # Use the actual RetroArch key, not an input_* approximation.
    text = re.sub(r'^input_joypad_autoconfig_dir\s*=.*\n', '', text, flags=re.M)
    text += 'user_language = "12"\n'
    text += 'bundle_assets_extract_last_version = "1763607285"\nbundle_assets_extract_version_current = "1763607285"\n'
    return text


def exact_path(parent, name):
    """Resolve the actual on-disk case before baking paths into case-sensitive ext4."""
    current = parent
    for part in relative(name).parts:
        if not current.is_dir():
            return None
        matches = [p for p in current.iterdir() if p.name.casefold() == part.casefold()]
        if len(matches) != 1:
            return None
        current = matches[0]
    return current


def adapt_metadata(collection, text, source):
    text = text.replace('\r', '')
    text = text.replace('com.retroarch.aarch64', 'com.retroarch.ra32').replace('gpsp_rumble_libretro_android.so', 'gpsp_libretro_android.so')
    chunks = re.split(r'(?=^game: )', text, flags=re.M)
    result = [chunks[0]]
    count = 0
    for chunk in chunks[1:]:
        title = chunk.splitlines()[0][6:].strip()
        # Make files absolute: config and readonly assets live outside the ROM folder.
        lines = chunk.splitlines()
        in_files = False
        transformed = []
        first_rom = None
        for line in lines:
            m = re.match(r'^(file|files):\s*(.*)$', line)
            if m:
                in_files = True
                value = m[2]
                if value:
                    relative(value); first_rom = first_rom or value
                    line = m[1] + ': @H700_ROMS_ROOT@/' + collection + '/' + value
            elif in_files and line.startswith((' ', '\t')) and line.strip():
                value = line.strip(); relative(value); first_rom = first_rom or value
                line = '  @H700_ROMS_ROOT@/' + collection + '/' + value
            else:
                in_files = False
            transformed.append(line)
        if not first_rom:
            raise ValueError('Missing ROM reference for ' + title)
        chunk = '\n'.join(transformed)
        explicit = dict(re.findall(r'^assets\.(box_front|logo|video):\s*(.+)$', chunk, re.M))
        fallback = source / 'media' / title
        if not fallback.is_dir():
            fallback = source / 'media' / Path(first_rom).stem
        for kind, stem in [('box_front', 'boxfront'), ('logo', 'logo'), ('video', 'video')]:
            path = None
            if kind in explicit:
                asset = explicit[kind]; relative(asset)
                path = exact_path(source, asset)
            if path is None:
                choices = [f for f in fallback.glob('*') if f.stem.lower() == stem and f.suffix.lower() in MEDIA]
                if len(choices) != 1:
                    raise ValueError('Ambiguous/missing media: ' + collection + '/' + title + '/' + kind)
                path = choices[0]
            regular(path)
            asset = path.relative_to(source).as_posix()
            new = 'assets.' + kind + ': ' + PAYLOAD + '/media/' + collection + '/' + asset
            pattern = r'^assets\.' + kind + r':.*$'
            if re.search(pattern, chunk, re.M):
                chunk = re.sub(pattern, lambda _: new, chunk, flags=re.M)
            else:
                chunk += '\n' + new
        result.append(chunk.strip() + '\n\n')
        count += 1
    return ''.join(result), count


def prepare_payload():
    payload = WORK / 'payload'
    ready = WORK / 'payload-verified.json'
    if ready.exists():
        record = json.loads(ready.read_text())
        for name, digest in record['files'].items():
            if sha(payload / name) != digest:
                raise ValueError('Payload modified: ' + name)
        return payload, record
    payload.mkdir(exist_ok=True)
    apps = json.loads((ROOT / 'config/pegasus/preinstall-apks.json').read_text())
    lines = []
    for app in apps:
        f = regular(ROOT / app['file'])
        if sha(f) != app['sha256'] or f.stat().st_size != app['bytes']:
            raise ValueError('APK pin mismatch: ' + app['id'])
        dest = payload / 'apks' / (app['id'] + '.apk')
        dest.parent.mkdir(exist_ok=True)
        shutil.copyfile(f, dest)
        lines.append(app['package'] + ' ' + dest.name + ' ' + app['sha256'])
    write(payload / 'apps.list', '\n'.join(lines) + '\n')
    # Only allowlisted assets from ROM collections. No ZIP, ROM, BIOS or save bytes.
    media_count = 0
    for collection in sorted((STAGE / 'Roms').iterdir()):
        for f in sorted((collection / 'media').rglob('*')):
            if not f.is_file():
                continue
            regular(f)
            if f.suffix.lower() not in MEDIA:
                raise ValueError('Non-media in media directory: ' + str(f))
            dest = payload / 'media' / collection.name / f.relative_to(collection)
            dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(f, dest)
            media_count += 1
    game_count = 0
    for collection in sorted((STAGE / 'Roms').iterdir()):
        text, count = adapt_metadata(collection.name, (collection / 'metadata.pegasus.txt').read_text(encoding='utf8'), collection)
        write(payload / 'collections' / collection.name / 'metadata.pegasus.txt', text)
        game_count += count
    if game_count != 604:
        raise ValueError('Unexpected collection entry count')
    # Preserve original theme notices. Exclude runtime indexes, history and settings.
    for f in sorted((STAGE / 'pegasus-frontend/themes').rglob('*')):
        if not f.is_file():
            continue
        regular(f)
        if f.suffix.lower() not in THEME or f.suffix.lower() in ROM:
            raise ValueError('Unexpected theme input: ' + str(f))
        dest = payload / 'themes' / f.relative_to(STAGE / 'pegasus-frontend/themes')
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(f, dest)
    # Core assets come from the exact already-tested APK, not live app data.
    ra = next(x for x in apps if x['id'] == 'RetroArch')
    with tarfile.open(payload / 'retroarch-private.tar', 'w', format=tarfile.PAX_FORMAT) as t, zipfile.ZipFile(ROOT / ra['file']) as z:
        for n in sorted(z.namelist()):
            if not n.startswith('assets/') or n.endswith('/'):
                continue
            dest = n[len('assets/'):]; relative(dest)
            tar_add(t, dest, z.read(n))
        tar_add(t, 'autoconfig/android/H700_ANBERNIC_keys.cfg', (ROOT / 'config/retroarch/android/H700_ANBERNIC_keys.cfg').read_bytes())
        locks = json.loads((ROOT / 'docs/baselines/rg34xxsp-pegasus-gba-20261030/component-lock.json').read_text())['cores']
        for core in locks:
            name = core['id'] + '_libretro_android.so'
            f = regular(ROOT / 'out/pegasus-gba-20261030/cores' / name)
            b = f.read_bytes()
            if sha(f) != core['so_sha256'] or b[:5] != b'\x7fELF\x01' or int.from_bytes(b[18:20], 'little') != 40:
                raise ValueError('Unpinned/non-ARM32 core: ' + name)
            tar_add(t, 'cores/' + name, b, 0o700)
    nova = b'<?xml version="1.0" encoding="utf-8"?>\n<map><string name="uimode_leanback">tablet</string><string name="uimode">1</string><boolean name="always_leanback_on_tv_key" value="false"/></map>\n'
    with tarfile.open(payload / 'nova-private.tar', 'w') as t:
        tar_add(t, 'shared_prefs/org.courville.nova_preferences.xml', nova)
    pgbase = 'Android/data/org.pegasus_frontend.android/files/pegasus-frontend/'
    settings = (STAGE / 'pegasus-frontend/settings.txt').read_text()
    settings = re.sub(r'^general.theme:.*$', 'general.theme: ' + PAYLOAD + '/themes/pegasusG-Grid/', settings, flags=re.M)
    dirs = ''.join('/storage/emulated/0/' + pgbase + 'collections/' + c + '\n' for c in ['GBA', 'GBA hack', 'GBA vib'])
    with tarfile.open(payload / 'external.tar', 'w', format=tarfile.PAX_FORMAT) as t:
        tar_add(t, pgbase + 'settings.txt', settings.encode())
        tar_add(t, pgbase + 'game_dirs.txt', dirs.encode())
        tar_add(t, pgbase + 'theme_settings/pegasusG-Grid.json', (ROOT / 'config/pegasus/theme-defaults.json').read_bytes())
        tar_add(t, 'RetroArch/.nomedia', b'')
        for f in sorted((STAGE / 'RetroArch').rglob('*')):
            if not f.is_file():
                continue
            rel = f.relative_to(STAGE / 'RetroArch')
            if rel.parts[0] not in ('cheats', 'config') or f.suffix.lower() not in ('.cht', '.opt', '.txt'):
                continue
            tar_add(t, 'RetroArch/' + rel.as_posix(), regular(f).read_bytes())
        cfg = gba_config().encode()
        tar_add(t, 'RetroArch/config/H700_GBA/retroarch-gba.cfg', cfg)
        tar_add(t, 'RetroArch/config/H700_GBA/global.glslp', (ROOT / 'config/pegasus/global.glslp').read_bytes())
        tar_add(t, 'Android/data/com.retroarch.ra32/files/retroarch.cfg', cfg)
        tar_add(t, 'koreader/patches/2-h700-dpad.lua', (ROOT / 'config/koreader/2-h700-dpad.lua').read_bytes())
        # Reuse only the static controller mapping, not PPSSPP histories or games.
        tar_add(t, 'PSP/SYSTEM/controls.ini', (ROOT / 'config/ppsspp/controls.ini').read_bytes())
        tar_add(t, 'PSP/SYSTEM/ppsspp.ini', b'[General]\nLanguage = zh_CN\nScreenRotation = 1\n[Graphics]\nGraphicsBackend = 0 (OPENGL)\nInternalResolution = 1\n[Control]\nShowTouchControls = False\n')
    write(payload / 'README.txt', 'RG34XXSP 2GB v6a. No game ROMs, BIOS, account data or saves.\nCopy your own game ZIPs into PegasusGBA/Roms/{GBA,GBA hack,GBA vib} on ROMS.\nMetadata and media are kept separately. Empty games are hidden until copied; restart Pegasus to rescan.\nFirst-boot integration and cold-flash physical acceptance remain pending.\n')
    files = {f.relative_to(payload).as_posix(): sha(f) for f in sorted(payload.rglob('*')) if f.is_file()}
    write(payload / 'SHA256SUMS', ''.join(h + '  ' + name + '\n' for name, h in files.items()))
    files['SHA256SUMS'] = sha(payload / 'SHA256SUMS')
    record = {'files': files, 'apps': apps, 'media_files': media_count, 'game_entries': game_count, 'rom_files': 0,
              'bytes': sum(f.stat().st_size for f in payload.rglob('*') if f.is_file())}
    jsonwrite(ready, record)
    return payload, record


def q(s):
    if any(c in str(s) for c in '\n\r\x00"\\'):
        raise ValueError('Unsupported debugfs path: ' + str(s))
    return '"' + str(s) + '"'


def debug(image, command):
    result = subprocess.run(['debugfs', '-R', command, str(image)], text=True, capture_output=True, check=True)
    return result.stdout


def dump(image, inside, output):
    output = Path(output)
    if output.exists():
        output.unlink()
    debug(image, 'dump ' + q(inside) + ' ' + q(output))
    return regular(output)


def context_for(partition, inside):
    label = 'system_file'
    if partition == 'vendor':
        label = 'vendor_configs_file' if inside == '/etc' or inside.startswith('/etc/') else 'vendor_file'
    return ('u:object_r:' + label + ':s0').encode() + b'\x00'


def preflight():
    for _, (source, digest) in PIN.items():
        if sha(regular(ROOT / source)) != digest:
            raise ValueError('Preflight component mismatch: ' + source)
    apps = json.loads((ROOT / 'config/pegasus/preinstall-apks.json').read_text())
    if len(apps) != 7 or {a['id'] for a in apps} != {'QQMusicTV', 'AnimekoTV', 'PPSSPP', 'RetroArch', 'NOVA', 'KOReader', 'Pegasus'}:
        raise ValueError('Only the seven explicitly selected applications are authorized')
    for app in apps:
        if sha(regular(ROOT / app['file'])) != app['sha256']:
            raise ValueError('Preflight APK mismatch: ' + app['id'])


def filesystem_smoke():
    marker = WORK / 'debugfs-smoke.json'
    if marker.exists():
        return
    image = WORK / 'debugfs-smoke.raw'
    if image.exists():
        raise ValueError('Incomplete filesystem smoke test retained')
    with image.open('xb') as f:
        f.truncate(16 * 1024**2)
    subprocess.run(['mke2fs', '-q', '-F', '-t', 'ext4', str(image)], check=True)
    sample = write(WORK / 'smoke.txt', 'owned UTF-8 fixture\n')
    context = WORK / 'smoke.context'
    context.write_bytes(context_for('vendor', '/etc/init/test.rc'))
    commands = write(WORK / 'smoke.commands', '\n'.join([
        'mkdir /test', 'write ' + q(sample) + ' ' + q('/test/中文 space.txt'),
        'ea_set -f ' + q(context) + ' ' + q('/test/中文 space.txt') + ' security.selinux']) + '\n')
    subprocess.run(['debugfs', '-w', '-f', str(commands), str(image)], check=True, capture_output=True)
    if sha(dump(image, '/test/中文 space.txt', WORK / 'smoke-readback.txt')) != sha(sample):
        raise ValueError('debugfs UTF-8 readback failed')
    attr = WORK / 'smoke-readback.context'
    debug(image, 'ea_get -f ' + q(attr) + ' ' + q('/test/中文 space.txt') + ' security.selinux')
    if attr.read_bytes() != context.read_bytes():
        raise ValueError('debugfs SELinux NUL roundtrip failed')
    subprocess.run(['e2fsck', '-f', '-n', str(image)], check=True, capture_output=True)
    jsonwrite(marker, {'utf8_paths': True, 'selinux_context_nul_roundtrip': True, 'e2fsck_exit': 0})


def factory_audit():
    data = debug(WORK / 'factory_tail.raw', 'ls -l /')
    # The pinned data filesystem must contain only its empty recovery directory.
    names = [line.split()[-1] for line in data.splitlines() if line.split()]
    if set(names) != {'.', '..', 'lost+found'}:
        raise ValueError('Factory userdata is not empty')
    fat = subprocess.run(['mdir', '-i', str(WORK / 'factory_tail.raw') + '@@17179869184', '::/'],
                         check=True, capture_output=True, text=True).stdout
    if 'No files' not in fat:
        raise ValueError('Factory ROMS is not empty')
    jsonwrite(WORK / 'factory-audit.json', {'userdata_root_entries': names, 'roms_file_count': 0,
                                          'current_device_userdata_copied': False})


def edit_images(payload, payload_record):
    complete = WORK / 'partitions-verified.json'
    if complete.exists():
        record = json.loads(complete.read_text())
        for name in ('system', 'vendor'):
            if sha(WORK / (name + '.candidate.raw')) != record[name]['sha256']:
                raise ValueError('Candidate partition changed')
        return record
    mappings = {}
    for key, (source, digest) in PIN.items():
        f = regular(ROOT / source)
        if sha(f) != digest:
            raise ValueError('Tested component pin mismatch: ' + key)
        mappings[key] = f
    for source, partition, target in re.findall(r'(device/roc/rgsp/[\w/.-]+):\$\(TARGET_COPY_OUT_(SYSTEM|VENDOR)\)/([\w/.-]+)', (PRODUCT / 'h700_rgsp.mk').read_text()):
        f = ROOT / 'android/h700-android10' / source
        if f.is_file() and '/prebuilts/' not in source and not source.endswith('rgsp-wifi-adb-session.sh'):
            mappings[partition.lower() + ':/' + ('system/' if partition == 'SYSTEM' else '') + target] = regular(f)
    for name in ['h700-preinstall.sh', 'h700-preinstall.rc']:
        inside = '/system/' + ('bin/' if name.endswith('.sh') else 'etc/init/') + name
        mappings['system:' + inside] = regular(PRODUCT / name)
    # Match the tested Android input capability files, independent of stale native out/.
    for name in ['ANBERNIC-keys.kl', 'Vendor_0001_Product_0001.kl', 'Vendor_0001_Product_0001_Version_0100.kl']:
        mappings['system:/system/usr/keylayout/' + name] = regular(PRODUCT / 'ANBERNIC-keys.kl')
    for f in (PRODUCT / 'wallpapers').glob('*.jpg'):
        mappings['system:/system/media/wallpapers/' + f.name] = regular(f)
    for f in payload.rglob('*'):
        if f.is_file():
            mappings['system:' + PAYLOAD + '/' + f.relative_to(payload).as_posix()] = regular(f)
    record = {}
    for name in ('system', 'vendor'):
        image = WORK / (name + '.candidate.raw')
        if image.exists():
            raise ValueError('Incomplete partition retained: ' + str(image))
        subprocess.run(['cp', '--sparse=always', str(WORK / (name + '.raw')), str(image)], check=True)
        propinside = '/system/build.prop' if name == 'system' else '/build.prop'
        prop = dump(image, propinside, WORK / (name + '.build.prop'))
        text = prop.read_text()
        changes = ({'ro.h700.release': 'v6a-rg34xxsp-20261030', 'ro.config.wallpaper': '/system/media/wallpapers/IMG_3111.jpg'}
                   if name == 'system' else {'persist.vendor.rgsp.input_profile': 'rg34xxsp'})
        for key, value in changes.items():
            text = re.sub(r'^' + re.escape(key) + r'=.*\n?', '', text, flags=re.M)
            text = text.rstrip() + '\n' + key + '=' + value + '\n'
        write(prop, text); mappings[name + ':' + propinside] = prop
        entries = {k.split(':', 1)[1]: v for k, v in mappings.items() if k.startswith(name + ':')}
        dirs = set()
        for inside in entries:
            dirs.update(str(p) for p in PurePosixPath(inside).parents if str(p) != '/')
        commands = []
        contexts = {}
        def context_file(inside):
            content = context_for(name, inside)
            if content not in contexts:
                p = WORK / ('context-' + hashlib.sha256(content).hexdigest()[:12])
                p.write_bytes(content); contexts[content] = p
            return contexts[content]
        for d in sorted(dirs, key=lambda s: (s.count('/'), s)):
            if 'Inode:' in debug(image, 'stat ' + q(d)):
                continue
            commands += ['mkdir ' + q(d), 'set_inode_field ' + q(d) + ' mode 040755',
                         'ea_set -f ' + q(context_file(d)) + ' ' + q(d) + ' security.selinux']
        for inside, f in entries.items():
            if inside.startswith('/system/bin/') or inside.startswith('/bin/'):
                mode = '0100755'
            else:
                mode = '0100644'
            commands += ['rm ' + q(inside), 'write ' + q(f) + ' ' + q(inside),
                         'set_inode_field ' + q(inside) + ' mode ' + mode,
                         'set_inode_field ' + q(inside) + ' uid 0', 'set_inode_field ' + q(inside) + ' gid 0',
                         'ea_set -f ' + q(context_file(inside)) + ' ' + q(inside) + ' security.selinux']
        # Oat files for replaced boot jars/APKs must not shadow the pinned DEX.
        if name == 'system':
            for inside in ['/system/framework/oat/arm/services.odex', '/system/framework/oat/arm/services.vdex']:
                commands.append('rm ' + q(inside))
            for directory, apk in [('priv-app/AT4K', 'AT4K'), ('app/RGSPNavigation', 'RGSPNavigation')]:
                for ext in ('.odex', '.vdex'):
                    commands.append('rm ' + q('/system/' + directory + '/oat/arm/' + apk + ext))
        cmdfile = write(WORK / (name + '.debugfs.commands'), '\n'.join(commands) + '\n')
        print('EDIT_PARTITION ' + name + ' files=' + str(len(entries)), flush=True)
        with (WORK / (name + '.debugfs.log')).open('w') as log:
            subprocess.run(['debugfs', '-w', '-f', str(cmdfile), str(image)], stdout=log, stderr=subprocess.STDOUT, check=True)
        with (WORK / (name + '.fsck.log')).open('w') as log:
            subprocess.run(['e2fsck', '-f', '-n', str(image)], stdout=log, stderr=subprocess.STDOUT, check=True)
        print('VERIFY_COMPONENTS ' + name, flush=True)
        checked = {}
        # Each edited file is read out of ext4 and rehashed, including every media file.
        for i, (inside, f) in enumerate(entries.items()):
            extracted = dump(image, inside, WORK / 'verify-component.tmp')
            digest = sha(f)
            if sha(extracted) != digest:
                raise ValueError('Readback mismatch: ' + inside)
            attr = WORK / 'verify-context.tmp'
            if attr.exists():
                attr.unlink()
            debug(image, 'ea_get -f ' + q(attr) + ' ' + q(inside) + ' security.selinux')
            if not attr.exists() or attr.read_bytes() != context_for(name, inside):
                raise ValueError('SELinux context readback mismatch: ' + inside)
            checked[inside] = digest
            if i and i % 500 == 0:
                print('READBACK ' + name + ' ' + str(i), flush=True)
        record[name] = {'sha256': sha(image), 'files': checked, 'e2fsck_exit': 0}
    # The original stage is immutable: untouched locked components must still match.
    old = json.loads((ROOT / 'out/h700-v5i-dpad-20261027-native35-notouch-stage/components.json').read_text())
    for key, digest in old.items():
        name, inside = key.split(':', 1)
        if key not in mappings:
            extracted = dump(WORK / (name + '.candidate.raw'), inside, WORK / 'verify-original.tmp')
            if sha(extracted) != digest:
                raise ValueError('Unexpected base component change: ' + key)
    jsonwrite(complete, record)
    return record


def assemble(seed, partitions, payload_record):
    raw = OUT / 'H700_RG34XXSP_2GB_v6a_20261030_NoROM.img'
    receipt = OUT / 'image-manifest.json'
    if raw.exists() or receipt.exists():
        raise ValueError('Final image names already exist; inspect prior output')
    partial = raw.with_suffix('.img.partial')
    if partial.exists():
        raise ValueError('Incomplete final image retained')
    hashes = {}
    print('ASSEMBLE_CANDIDATE', flush=True)
    with partial.open('xb') as dst:
        for name, offset, length in RANGES:
            source = WORK / (name + ('.candidate.raw' if name in ('system', 'vendor') else '.raw'))
            h = hashlib.sha256()
            dst.seek(offset)
            with source.open('rb') as src:
                left = length
                while left:
                    b = src.read(min(left, 8 * 1024**2))
                    if not b:
                        raise ValueError('Short partition input')
                    h.update(b); sparse_write(dst, b); left -= len(b)
            digest = partitions[name]['sha256'] if name in partitions else seed[name]
            if h.hexdigest() != digest:
                raise ValueError('Assembled range mismatch')
            hashes[name] = digest
        dst.truncate(SIZE)
    full = hashlib.sha256()
    with partial.open('rb') as src:
        for name, _, length in RANGES:
            h = hashlib.sha256(); left = length
            while left:
                b = src.read(min(left, 8 * 1024**2))
                if not b:
                    raise ValueError('Short final readback')
                h.update(b); full.update(b); left -= len(b)
            if h.hexdigest() != hashes[name]:
                raise ValueError('Final range readback mismatch')
    partial.rename(raw)
    record = {'release': raw.stem, 'bytes': SIZE, 'sha256': full.hexdigest(), 'base_sha256': BASE,
              'status': 'FILESYSTEM_COMPONENTS_AND_RANGES_VERIFIED_PENDING_COLD_FLASH_ACCEPTANCE',
              'ranges': [{'name': n, 'offset': o, 'bytes': l, 'sha256': hashes[n]} for n, o, l in RANGES],
              'preinstall_apps': payload_record['apps'], 'media_files': payload_record['media_files'],
              'collection_entries': payload_record['game_entries'], 'game_rom_files': 0,
              'factory_userdata_and_roms_preserved': True, 'full_aosp_rebuild': False,
              'physical_flash_performed': False, 'fresh_first_boot_verified': False,
              'cpu_quota': 'one aggregate CPU, affinity 0-1, nice 19', 'memory_max_gib': 6, 'swap_max_mib': 512,
              'hardware_voltage_telemetry_available': False,
              'partition_component_manifest_sha256': sha(WORK / 'partitions-verified.json'),
              'payload_manifest_sha256': sha(WORK / 'payload-verified.json')}
    jsonwrite(receipt, record)
    print('COMPRESS_CANDIDATE', flush=True)
    compressed = raw.with_suffix('.img.gz')
    with raw.open('rb') as src, compressed.open('xb') as fout:
        with gzip.GzipFile(filename='', fileobj=fout, mode='wb', compresslevel=6, mtime=0) as dst:
            shutil.copyfileobj(src, dst, 8 * 1024**2)
    print('VERIFY_GZIP_FULL_DECOMPRESSION', flush=True)
    with gzip.open(compressed, 'rb') as src:
        digest = hashlib.file_digest(src, 'sha256').hexdigest()
    if digest != record['sha256']:
        raise ValueError('Compressed image full verification failed')
    record['gzip'] = {'file': compressed.name, 'bytes': compressed.stat().st_size, 'sha256': sha(compressed), 'full_decompressed_sha256_verified': True}
    jsonwrite(receipt, record)
    jsonwrite(OUT / 'partition-components.json', partitions)
    jsonwrite(OUT / 'payload-manifest.json', payload_record)
    print('IMAGE_READY ' + str(compressed), flush=True)


def main():
    constrained()
    if shutil.disk_usage(ROOT).free < 60 * 1024**3 or shutil.disk_usage('/home/lpf').free < 60 * 1024**3:
        raise ValueError('Need 60 GiB free on each staging/output filesystem')
    OUT.mkdir(exist_ok=True); WORK.mkdir(exist_ok=True)
    subprocess.run(['bash', '-n', str(PRODUCT / 'h700-preinstall.sh')], check=True)
    preflight()
    filesystem_smoke()
    seed = split_seed()
    factory_audit()
    print('PREPARE_ROM_FREE_PAYLOAD', flush=True)
    payload, record = prepare_payload()
    print('PAYLOAD_BYTES ' + str(record['bytes']), flush=True)
    partitions = edit_images(payload, record)
    assemble(seed, partitions, record)


if __name__ == '__main__':
    main()

"""Read-only round2 partition audit. Never assembles boot/card images or uses ADB."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained
constrained()
OUT = REPO / 'out/roc-os-source64-round2-20261103'
ROOT = Path('/home/lpf/roc-os-source64-20261103')
NATIVE = Path('/home/lpf/h700-android10/android')
TARGET = ROOT / 'out/target/product/roc_os_source64'
HOST = ROOT / 'out/host/linux-x86/bin'
WORK = next(ROOT / ('round2-audit-v%d' % n) for n in range(1, 100)
            if not (ROOT / ('round2-audit-v%d' % n)).exists())
WORK.mkdir()
checks = []
metadata = {}


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(args, expected=(0,)):
    p = subprocess.run(list(map(str, args)), capture_output=True, text=True)
    with (WORK / 'commands.log').open('a') as stream:
        stream.write(json.dumps(list(map(str, args))) + '\n' + p.stdout + p.stderr + '\n')
    assert p.returncode in expected, (args, p.returncode, p.stdout[-1500:], p.stderr[-1500:])
    return p


def check(name, condition):
    assert condition, name
    checks.append(name)
    print('AUDIT_PASS', name, flush=True)


def inside(path):
    return ('vendor', path[7:]) if path.startswith('/vendor/') else ('system', path)


def stat(path):
    part, name = inside(path)
    return run(['/usr/sbin/debugfs', '-R', 'stat ' + name, WORK / (part + '.raw')]).stdout


def file(path, required=True):
    part, name = inside(path)
    dest = WORK / 'files' / part / name.lstrip('/')
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        run(['/usr/sbin/debugfs', '-R', 'dump ' + name + ' ' + str(dest), WORK / (part + '.raw')])
    exists = dest.is_file()
    metadata[path] = {'exists': exists}
    if exists:
        metadata[path].update(bytes=dest.stat().st_size, sha256=sha(dest))
        return dest
    assert not required, path
    return None


def text(path):
    return file(path).read_text()


def dex_strings(data):
    count, offset = struct.unpack_from('<II', data, 56)
    result = []
    for i in range(count):
        at = struct.unpack_from('<I', data, offset + 4*i)[0]
        while data[at] & 128:
            at += 1
        at += 1
        result.append(data[at:data.index(0, at)].decode('utf8', errors='replace'))
    return result


def dex(path):
    result = []
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if re.fullmatch(r'classes\d*\.dex', name):
                result.extend(dex_strings(archive.read(name)))
    return result


def apk(leaf):
    matches = list((TARGET / 'system').glob('**/' + leaf + '.apk'))
    assert len(matches) == 1, (leaf, matches)
    return file('/' + matches[0].relative_to(TARGET).as_posix())


def main():
    results = sorted(OUT.glob('images-result-v*.json'), key=lambda p: int(re.search(r'v(\d+)', p.name)[1]))
    built = json.loads(results[-1].read_text())
    check('latest build succeeded', built['passed'])
    prepared = json.loads((OUT / built['prepare_receipt']).read_text())
    check('371 original inputs unchanged', len(prepared['protected_native_sha256']) == 371 and all(
        sha(NATIVE / name) == digest for name, digest in prepared['protected_native_sha256'].items()))
    check('selected private product unchanged', all(sha(NATIVE / 'device/roc/roc_os_source64' / name) == digest
        for name, digest in prepared['product_sha256'].items()))
    core = NATIVE / 'device/roc/roc_os_source64/Services/Core/java'
    original_core = NATIVE / 'frameworks/base/services/core/java'
    core_deltas = [p.relative_to(core).as_posix() for p in sorted(core.rglob('*'))
                   if p.is_file() and sha(p) != sha(original_core / p.relative_to(core))]
    check('only storage framework Java changed', core_deltas == ['com/android/server/StorageManagerService.java'])
    preserved = json.loads((ROOT / 'round1-preserved/receipt.json').read_text())
    check('three round1 images preserved', all(sha(ROOT / 'round1-preserved' / name) == item['sha256']
        for name, item in preserved['images'].items()))
    check('round1 source archive preserved', sha(ROOT / 'round1-preserved/product-source.tar.gz') ==
          preserved['product_source_archive_sha256'])
    check('two real ABI5 host libraries unchanged', all(sha(ROOT / 'host-compat/lib' / name) == digest
          for name, digest in prepared['host_compat_library_sha256'].items()))
    for name, item in built['images'].items():
        check(name + ' result hash', sha(TARGET / name) == item['sha256'])
    for part in ['system', 'vendor']:
        run([HOST / 'simg2img', TARGET / (part + '.img'), WORK / (part + '.raw')])
        run(['/usr/sbin/e2fsck', '-f', '-n', WORK / (part + '.raw')])
        checks.append(part + ' read-only fsck')
    check('system init remains regular', 'Type: regular' in stat('/system/bin/init'))
    check('root init direct link', 'Fast link dest: "/system/bin/init"' in stat('/init'))
    check('bootstrap linker remains regular', 'Type: regular' in stat('/system/bin/bootstrap/linker64'))
    first = json.loads((REPO / 'docs/baselines/roc-os-source64-round1-20261103/completion.json').read_text())
    for name, item in first['ELF_artifacts'].items():
        f = file('/' + name)
        data = f.read_bytes()
        check('retained dual ABI ' + name, sha(f) == item['sha256'] and data[4] == item['ELF_class']
              and struct.unpack_from('<H', data, 18)[0] == item['e_machine'])
    nav = apk('ROCNavigation')
    check('Navigation14 manifest', "versionCode='14'" in run([HOST / 'aapt2', 'dump', 'badging', nav]).stdout)
    check('Navigation shade range marker', 'com.android.systemui:id/slider' in dex(nav))
    check('old Navigation APK absent', file('/system/app/RGSPNavigation/RGSPNavigation.apk', False) is None)
    environment = text('/init.environ.rc')
    server = re.search(r'^\s*export SYSTEMSERVERCLASSPATH (.+)$', environment, re.M)[1].strip().split(':')
    check('only private SystemServer jar selected', server == ['/system/framework/' + x + '.jar' for x in
          ['services.rocsource', 'ethernet-service', 'wifi-service.rocsource', 'com.android.location.provider']])
    for path in server:
        check('classpath jar exists ' + path, file(path).stat().st_size > 0)
    check('old services jar absent', file('/system/framework/services.jar', False) is None)
    check('old Wi-Fi jar absent', file('/system/framework/wifi-service.jar', False) is None)
    check('new Wi-Fi jar exists', file('/system/framework/wifi-service.rocsource.jar').stat().st_size > 0)
    check('Wi-Fi service class exists', 'Lcom/android/server/wifi/WifiService;' in
          dex(file('/system/framework/wifi-service.rocsource.jar')))
    check('Wi-Fi init retained exactly', sha(file('/system/etc/init/roc-wifi-events.rc')) ==
          sha(NATIVE / 'frameworks/opt/net/wifi/service/wifi-events.rc'))
    check('old Wi-Fi init absent', file('/system/etc/init/wifi-events.rc', False) is None)
    for name in ['services', 'wifi-service']:
        for path in ['/system/framework/' + name + '.jar.prof'] + [
                '/system/framework/oat/' + abi + '/' + name + '.' + ext
                for abi in ['arm', 'arm64'] for ext in ['odex', 'vdex', 'art']]:
            check('old preopt absent ' + path, file(path, False) is None)
    check('old third party payload absent', 'Type:' not in stat('/system/etc/h700-preinstall'))
    ss = dex(file('/system/framework/services.rocsource.jar'))
    check('compiled unified storage framework', 'ro.roc.storage.layout' in ss and 'unified-v1' in ss
          and '/sdc2/mmc_host/' in ss)
    fstab = text('/vendor/etc/fstab.sun50iw9p1')
    check('userdata internal and TF2 removable only', '/dev/block/by-name/userdata /data ' in fstab
          and fstab.count('voldmanaged=') == 1 and '/sdc2/mmc_host/' in fstab
          and 'ROMS' not in fstab and '/sdc0/' not in fstab)
    root_fstab = file('/fstab.sun50iw9p1', False)
    check('no legacy root fstab', root_fstab is None or sha(root_fstab) ==
          sha(file('/vendor/etc/fstab.sun50iw9p1')))
    rc = text('/system/etc/init/vold.rocsource.rc')
    check('private vold selected by init', 'service vold /system/bin/vold.rocsource' in rc)
    vold = file('/system/bin/vold.rocsource').read_bytes()
    check('compiled TF1/TF2 vold policy', all(marker in vold for marker in
          [b'ro.roc.storage.layout', b'unified-v1', b'/devices/platform/soc/sdc2/mmc_host/',
           b'ROC OS refuses boot-card/unknown MMC as external storage']))
    for path in ['/system/bin/vold', '/system/etc/init/vold.rc', '/system/etc/init/wait_for_keymaster.rc',
                 '/system/bin/preinstall', '/system/etc/init/preinstall.rc',
                 '/system/bin/h700-preinstall.sh', '/system/etc/init/h700-preinstall.rc',
                 '/system/bin/rgsp-roms-handoff.sh', '/system/etc/init/rgsp-roms-handoff.rc',
                 '/system/bin/rgsp-firstboot.sh', '/system/etc/init/rgsp-firstboot.rc',
                 '/system/bin/rgsp-navigation-defaults.sh', '/system/etc/init/rgsp-navigation-defaults.rc']:
        check('removed ' + path, file(path, False) is None)
    mixer = file('/vendor/etc/audio_mixer_paths.xml')
    check('accepted H700 mixer', mixer.stat().st_size == 888 and sha(mixer) ==
          sha(REPO / 'android/h700-android10/device/roc/roc_os_source64/configs/audio_mixer_paths.xml'))
    manifest_file = file('/vendor/etc/vintf/manifest.xml')
    run([HOST / 'assemble_vintf', '-i', manifest_file, '-o', WORK / 'manifest-parser.xml'])
    checks.append('merged VINTF Android parser')
    manifest = ET.fromstring(manifest_file.read_text())
    hals = manifest.findall('hal')
    def instances(name):
        result = []
        for h in hals:
            if h.findtext('name') != name:
                continue
            result += [x.text for x in h.findall('fqname')]
            for version in h.findall('version'):
                for interface in h.findall('interface'):
                    result += ['@' + version.text + '::' + interface.findtext('name') + '/' + x.text
                               for x in interface.findall('instance')]
        # assemble_vintf may emit interface+fqname for the same logical instance.
        return sorted(set(result))
    check('one backlight HAL', instances('android.hardware.light') == ['@2.0::ILight/default'])
    vintf = WORK / 'vintf-catalog'
    vintf.mkdir()
    run(['/usr/sbin/debugfs', '-R', 'rdump /etc/vintf ' + str(vintf), WORK / 'vendor.raw'])
    light_declarations = []
    for item in vintf.rglob('*.xml'):
        tree = ET.fromstring(item.read_text())
        if tree.tag == 'manifest':
            light_declarations.extend(str(item.relative_to(vintf)) for h in tree.findall('hal')
                                      if h.findtext('name') == 'android.hardware.light')
    check('no extra backlight VINTF fragment', len(light_declarations) == 1)
    check('OMX and OMXStore declared', set(instances('android.hardware.media.omx')) ==
          {'@1.0::IOmx/default', '@1.0::IOmxStore/default'})
    check('H700 light init', '/vendor/bin/hw/android.hardware.light@2.0-service.rocsource' in
          text('/vendor/etc/init/roc-light.rc'))
    for path, label in [('/vendor/bin/hw/android.hardware.light@2.0-service.rocsource', 'hal_light_default_exec'),
                        ('/system/bin/vold.rocsource', 'vold_exec')]:
        part, name = inside(path)
        attrs = run(['/usr/sbin/debugfs', '-R', 'ea_list ' + name, WORK / (part + '.raw')]).stdout
        check('actual label ' + path, 'u:object_r:' + label + ':s0' in attrs)
    check('ROC USB branding', 'ROC OS' in text('/system/etc/init/h700-usb-configfs.rc'))
    for leaf in ['roc-os-branding', 'roc-factory']:
        for ext, folder in [('sh', 'bin'), ('rc', 'etc/init')]:
            check(leaf + '.' + ext + ' exact', sha(file('/system/' + folder + '/' + leaf + '.' + ext)) ==
                  sha(REPO / 'android/h700-android10/device/roc/roc_os_source64/configs' / (leaf + '.' + ext)))
        service = text('/system/etc/init/' + leaf + '.rc')
        check(leaf + ' low priority', 'priority 19' in service and 'ioprio idle 0' in service)
    # Follow this BSP's property_load_boot_defaults fallback and late-file order,
    # then property_initialize_ro_product_props partition-source derivation.
    default = next((p for name in ['/system/etc/prop.default', '/prop.default', '/default.prop']
                    if (p := file(name, False)) is not None), None)
    assert default is not None
    properties = {}
    loaded = []
    def load_props(path):
        if path is None:
            return
        loaded.append(str(path.relative_to(WORK / 'files')))
        for line in path.read_text().splitlines():
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            assert not line.startswith('import '), 'Unresolved property import: ' + line
            if '=' in line:
                key, value = line.split('=', 1)
                properties[key.strip()] = value.strip()
    load_props(default)
    for name in ['/system/build.prop', '/vendor/default.prop', '/vendor/build.prop']:
        load_props(file(name, False))
    odm_paths = ['/vendor/odm/etc/build.prop'] if int(properties['ro.vendor.build.version.sdk']) >= 29 else [
        '/vendor/odm/default.prop', '/vendor/odm/build.prop']
    for name in odm_paths + ['/system/product/build.prop', '/system/product_services/build.prop', '/factory/factory.prop']:
        load_props(file(name, False))
    default_order = 'product,product_services,odm,vendor,system'.split(',')
    order = properties.get('ro.product.property_source_order', '').split(',')
    if not order or any(x not in default_order for x in order):
        order = default_order
    for suffix in ['brand', 'device', 'manufacturer', 'model', 'name']:
        key = 'ro.product.' + suffix
        if not properties.get(key):
            properties[key] = next((properties['ro.product.' + source + '.' + suffix] for source in order
                                    if properties.get('ro.product.' + source + '.' + suffix)), '')
    (WORK / 'effective-properties.json').write_text(json.dumps({'loaded': loaded, 'source_order': order,
        'effective': properties}, indent=2) + '\n')
    check('ARM64 primary with ARM32 secondary', properties.get('ro.zygote') == 'zygote64_32' and
          properties.get('ro.product.cpu.abilist') == 'arm64-v8a,armeabi-v7a,armeabi')
    check('effective locale and model', properties.get('ro.product.locale') == 'zh-CN' and
          properties.get('ro.product.model') == 'ROC OS')
    check('new layout and factory profile', properties.get('ro.roc.storage.layout') == 'unified-v1' and
          properties.get('ro.roc.source64.round') == '2' and properties.get('ro.product.device') == 'rgsp' and
          properties.get('persist.vendor.rgsp.input_profile') == 'rg34xxsp')
    check('factory HOME XML', 'com.overdevs.at4k/.MainActivity' in text('/system/etc/preferred-apps/at4k-home.xml'))
    check('Leanback hash for factory defaults', sha(apk('LeanbackIME')) ==
          text('/system/etc/rgsp/leanback.sha256').strip().split()[0])
    original = REPO / 'out/roc-os-source64-audit-20261103/files.json'
    prior = json.loads(original.read_text())
    for path in ['/system/media/wallpapers/IMG_3111.jpg', '/system/usr/keylayout/ANBERNIC-keys.kl',
                 '/vendor/modules/h700_stick_axes.ko', '/vendor/modules/8821cs.ko',
                 '/vendor/lib/egl/libGLES_mali.so', '/vendor/lib64/egl/libGLES_mali.so']:
        part, name = inside(path)
        old = prior['new-' + part + ':' + name]
        check('retained hardware ' + path, sha(file(path)) == old['sha256'])
    signers = {}
    for leaf in ['AT4K', 'ROCNavigation', 'H700Lid', 'H700Rotation', 'SystemUI', 'Settings', 'LeanbackIME']:
        f = apk(leaf)
        verification = run([NATIVE / 'prebuilts/jdk/jdk9/linux-x86/bin/java', '-Xmx256m', '-jar',
            NATIVE / 'prebuilts/sdk/tools/linux/lib/apksigner.jar', 'verify', '--min-sdk-version', '29',
            '--max-sdk-version', '29', '--print-certs', f])
        signers[leaf] = re.findall(r'certificate SHA-256 digest: (\w+)', verification.stdout)
        if leaf != 'ROCNavigation':
            old = next(v for k, v in prior.items() if k.startswith('new-system:') and
                       k.endswith('/' + leaf + '/' + leaf + '.apk'))
            check('retained APK ' + leaf, sha(f) == old['sha256'])
    check('Navigation SystemUI platform signer', signers['ROCNavigation'] == signers['SystemUI'])
    # The complete installed APK catalog, not merely seven selected names.
    packages = {}
    installed_apks = sorted(f for partition in ['system', 'vendor']
                            for f in (TARGET / partition).glob('**/*.apk'))
    for f in installed_apks:
        image = file('/' + f.relative_to(TARGET).as_posix())
        badging = run([HOST / 'aapt2', 'dump', 'badging', image]).stdout
        packages[str(f.relative_to(TARGET))] = re.search(r"package: name='([^']+)'", badging)[1]
    blocked = ['com.retroarch', 'org.ppsspp', 'org.pegasus_frontend', 'org.koreader', 'bin.mt.plus',
               'com.animeko', 'me.him188.ani', 'org.courville.nova', 'com.tencent.qqmusic', 'com.tencent.qqmusictv']
    check('no historical third party preloads', not any(p.startswith(tuple(blocked)) for p in packages.values()))
    (WORK / 'apk-catalog.json').write_text(json.dumps(packages, indent=2) + '\n')
    boot = json.loads((OUT / 'boot-contract.json').read_text())
    tools = {}
    dest = WORK / 'loose-boot-tools'
    dest.mkdir()
    for name in boot['static_ramdisk_tools_required']:
        f = file('/system/bin/' + name)
        data = f.read_bytes()
        info = run(['readelf', '-l', '-d', f]).stdout
        check(name + ' static ARM64', data[:5] == b'\x7fELF\x02' and struct.unpack_from('<H', data, 18)[0] == 183
              and 'INTERP' not in info and '(NEEDED)' not in info)
        shutil.copyfile(f, dest / name)
        (dest / name).chmod(0o755)
        tools[name] = {'sha256': sha(f), 'bytes': len(data), 'required_future_ramdisk_mode': '0100755'}
    # Execute the actual Android ARM64 products under existing user-mode QEMU.
    # All writable paths are newly owned regular fixtures, never block devices.
    emulator = shutil.which('qemu-aarch64')
    assert emulator, 'Existing ARM64 user emulator required for boot-tool acceptance'
    sys.path.insert(0, str(REPO / 'tools/source64/storage'))
    import layout
    primary = (Path(boot['work']) / 'primary-gpt.template').read_bytes()
    backup = (Path(boot['work']) / 'backup-gpt.template').read_bytes()
    gpt = WORK / 'android-arm64.gpt-fixture'
    capacity = 63864569856
    with gpt.open('xb') as stream:
        stream.truncate(capacity)
        stream.seek(0); stream.write(primary)
        stream.seek(8192); stream.write(b'BOOT0-UNCHANGED')
        stream.seek(layout.SEED_BYTES - len(backup)); stream.write(backup)
    helper = dest / 'roc-grow-userdata-gpt'
    run([emulator, helper, '--check', gpt, '--image-test'], (4,))
    run([emulator, helper, '--apply', gpt, '--image-test'])
    run([emulator, helper, '--check', gpt, '--image-test'])
    with gpt.open('rb') as stream:
        head = stream.read(2048)
        stream.seek(-1536, 2); tail = stream.read(1536)
        stream.seek(8192); sentinel = stream.read(15)
    check('actual ARM64 GPT expansion', (head, tail) == layout.grow(primary, capacity)
          and sentinel == b'BOOT0-UNCHANGED')
    fixture = WORK / 'android-arm64.ext4-fixture'
    with fixture.open('xb') as stream:
        stream.truncate(64 * 1024**2)
    # Compatibility profile for this fixture only; future factory FS remains unbuilt.
    run(['/usr/sbin/mke2fs', '-q', '-F', '-t', 'ext4', '-b', '4096', '-U', boot['userdata_fs_uuid'],
         '-O', '^orphan_file,^metadata_csum_seed,^metadata_csum,^64bit', fixture])
    sentinel_file = WORK / 'fixture-sentinel.txt'
    sentinel_file.write_text('ROC actual Android ARM64 filesystem retention\n')
    run(['/usr/sbin/debugfs', '-w', '-R', 'write ' + str(sentinel_file) + ' /roc-sentinel', fixture])
    run([emulator, helper, '--check-volume', fixture, '--image-test'])
    with fixture.open('r+b') as stream:
        stream.truncate(128 * 1024**2)
    run([emulator, helper, '--check-volume', fixture, '--image-test'], (4,))
    run([emulator, dest / 'e2fsck_static', '-f', '-p', fixture], (0, 1))
    run([emulator, dest / 'roc-resize2fs-static', fixture])
    run([emulator, helper, '--check-volume', fixture, '--image-test'])
    run(['/usr/sbin/e2fsck', '-f', '-n', fixture])
    retained = WORK / 'fixture-sentinel.after.txt'
    run(['/usr/sbin/debugfs', '-R', 'dump /roc-sentinel ' + str(retained), fixture])
    check('actual ARM64 fsck resize and file retention', sha(retained) == sha(sentinel_file))
    boot_init = Path(boot['work']) / 'init'
    check('loose init hash', sha(boot_init) == boot['init_sha256'])
    boot_text = boot_init.read_text()
    check('loose boot uses unified data before mounts', 'p8' not in boot_text and
          boot_text.index('/bin/sh /grow/grow-userdata.sh') < boot_text.index('mount -t ext4') and
          'switch_root /android-root /init selinux_setup' in boot_text)
    from audit_linkage import audit
    linkage = audit(WORK, run, file)
    (WORK / 'linkage.json').write_text(json.dumps(linkage, indent=2) + '\n')
    check('namespace and pre-APEX closure', not linkage['errors'] and not linkage['pre_apex_bootstrap_errors'])
    services = []
    for f in (WORK / 'init-catalog').rglob('*.rc'):
        services.extend(re.findall(r'^service\s+(\S+)\s+(.*)$', f.read_text(), re.M))
    for name in ['vold', 'vendor.h700-light', 'roc-factory', 'roc-os-branding']:
        check('single init service ' + name, sum(x[0] == name for x in services) == 1)
    (WORK / 'init-services.json').write_text(json.dumps(services, indent=2) + '\n')
    result = {'passed': True, 'build_receipt': results[-1].name, 'work': str(WORK), 'checks': checks,
              'images': built['images'], 'loose_static_tools': tools, 'signers': signers,
              'linkage_summary': {k: v for k, v in linkage.items() if k not in ['objects', 'graph', 'roots']},
              'whole_card_image_created': False, 'boot_image_created': False, 'current_card_modified': False,
              'device_boot_accepted': False, 'limits': ['Offline parity only; no boot, power, physical or release acceptance.',
                  'Loose new boot contract still requires user-approved packaging and new factory userdata.',
                  'DT_NEEDED checks do not establish all dlopen symbols or kernel compatibility.']}
    return result


try:
    result = main()
except Exception as error:
    result = {'passed': False, 'work': str(WORK), 'checks': checks, 'error': repr(error)}
    raise
finally:
    (WORK / 'files.json').write_text(json.dumps(metadata, indent=2) + '\n')
    (WORK / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    (OUT / (WORK.name + '.json')).write_text(json.dumps(result, indent=2) + '\n')

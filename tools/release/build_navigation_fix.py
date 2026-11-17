"""Build only the production-signed Navigation17 APK in the existing capped scope.

No prepare/lunch, Native source edits, Android output writes, device operations,
or key copies. Candidate inputs are snapshotted and hashed before compilation.
"""
from pathlib import Path, PurePosixPath
import datetime
import hashlib
import json
import os
import re
import shutil
import ssl
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained

NATIVE = Path('/home/lpf/h700-android10/android')
KEYS = Path('/home/lpf/.roc-os/keys/production-v1')
OVERLAY = REPO / 'build-support/public/overlay/device/roc/roc_os_source64/Navigation'
RECIPE = REPO / 'build-support/public/source-manifest.json'
PREFIX = 'device/roc/roc_os_source64/Navigation/'
PACKAGE = 'com.roc.rgsp.navtrial'
PLATFORM_CERT = 'fc30e834b3c2914a0646d0b46c4faaa045aa8d46189950012555a5f2c36745c9'
SERVICE = 'src/com/roc/rgsp/navtrial/NavigationService.java'
AXIS = 'src/com/roc/rgsp/navtrial/AxisNavigation.java'
ANDROID_NS = '{http://schemas.android.com/apk/res/android}'
TOOL_PINS = {
    'prebuilts/jdk/jdk9/linux-x86/bin/java': '0fc49ba9e906db74a7d3cb0b4a44b9e0916e1e487b45431c0cb7ed281cd7ef65',
    'prebuilts/jdk/jdk9/linux-x86/bin/javac': '8d6dd6678e9bd29f07ab988d7eae4fd58f995997cff8c7202e9e23113e90be1d',
    'prebuilts/sdk/tools/linux/bin/aapt': 'ad71b6a5dc04977ceb84697f45ef2e2c7e8e29f33c8a62f39205f0525fd52835',
    'prebuilts/sdk/tools/linux/bin/zipalign': '7c4efc4f8b3c7454f42473f653b758200a68dac4ed79df37c1d4b8661c83887f',
    'prebuilts/sdk/tools/linux/bin/dexdump': 'c3f5a4a183404e486cbe59a08a8cedf090fec4dbde134c6df4b11f92b3b300be',
    'prebuilts/sdk/tools/linux/lib/d8.jar': '9b6750442852f290e07998e20b09c07d56071dc6190405cad73ecebf64cff396',
    'prebuilts/sdk/tools/linux/lib/apksigner.jar': 'b9b61b17a11523da8e10e454f35ef1093397014e22b67323576816456e64537c',
    'prebuilts/sdk/29/public/android.jar': '17ec5ec253c45463160c5a37e9bae5f41b35184010cbdd9240749c7d30e1afd7',
    'prebuilts/sdk/tools/linux/bin/core-lambda-stubs.jar': 'b370525f81bd8da7a6f9bb37958963ad469f1517813a20632eaf51c6f0cdee93',
}


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def regular(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Regular non-symlink input required: ' + str(path))
    return path


def safe_relative(name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or not p.parts or '\\' in name:
        raise ValueError('Unsafe source path: ' + name)
    return Path(*p.parts)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n',
                          encoding='utf-8', newline='\n')


def overlay_files():
    return {p.relative_to(OVERLAY).as_posix(): regular(p)
            for p in OVERLAY.rglob('*') if p.is_file()}


def tree_hashes(root):
    return {p.relative_to(root).as_posix(): sha(regular(p))
            for p in sorted(root.rglob('*')) if p.is_file()}


def source_inputs():
    """Use the actual Source64 overlay plus exact shared-helper copy recipes."""
    selected = {}
    recipe = json.loads(regular(RECIPE).read_text())
    for entry in recipe['files']:
        if not entry['path'].startswith(PREFIX):
            continue
        relative = entry['path'][len(PREFIX):]
        safe_relative(relative)
        candidate = OVERLAY / relative
        if candidate.is_file():
            source, origin = regular(candidate), 'candidate_overlay'
        else:
            # Never fall back to the ordinary RGSP NavigationService.
            if relative in (SERVICE, 'AndroidManifest.xml'):
                raise ValueError('Source64 candidate input missing: ' + relative)
            item = entry['input']
            source = REPO / safe_relative(item['path']) if item['kind'] == 'repository' else NATIVE / safe_relative(entry['path'])
            source = regular(source)
            if sha(source) != entry['sha256']:
                raise ValueError('Shared helper differs from retained recipe: ' + str(source))
            origin = 'sha256_checked_copy_recipe'
        selected[relative] = (source, origin)
    for relative, source in overlay_files().items():
        if relative not in ('AndroidManifest.xml', 'Android.bp') and not relative.startswith(('src/', 'res/')):
            raise ValueError('Unexpected candidate file: ' + relative)
        selected[relative] = (source, 'candidate_overlay')
    for needed in (SERVICE, AXIS, 'AndroidManifest.xml', 'res/xml/navigation_service.xml'):
        if needed not in selected:
            raise ValueError('Required Navigation17 source missing: ' + needed)
    return selected


def validate_manifest(path):
    root = ET.parse(path).getroot()
    attr = lambda node, key: node.get(ANDROID_NS + key)
    assert root.get('package') == PACKAGE
    assert attr(root, 'versionCode') == '17'
    assert not attr(root, 'sharedUserId')
    sdk = root.find('uses-sdk')
    assert sdk is not None and attr(sdk, 'minSdkVersion') == attr(sdk, 'targetSdkVersion') == '29'
    permissions = [attr(p, 'name') for p in root.findall('uses-permission')]
    assert permissions == ['android.permission.EXPAND_STATUS_BAR'], permissions
    assert len(root.findall('application')) == 1
    app = root.find('application')
    assert attr(app, 'allowBackup') == 'false' and attr(app, 'debuggable') in (None, 'false')
    assert not any(app.findall(kind) for kind in ('activity', 'activity-alias', 'receiver', 'provider'))
    services = app.findall('service')
    assert len(services) == 1
    service = services[0]
    assert attr(service, 'name') == '.NavigationService'
    assert attr(service, 'permission') == 'android.permission.BIND_ACCESSIBILITY_SERVICE'
    assert attr(service, 'exported') == 'true'
    assert [attr(p, 'name') for p in service.findall('./intent-filter/action')] == ['android.accessibilityservice.AccessibilityService']
    return {'package': PACKAGE, 'versionCode': 17, 'versionName': attr(root, 'versionName'),
            'minSdkVersion': 29, 'targetSdkVersion': 29, 'permissions': permissions}


def normalize_pinned_d8_header(dex, delivery):
    """Correct only the proven SHA-1 header bug in the pinned D8 1.0.35.

    Its FileWriter hashes bytes from offset 32 using length EOF-84, leaving
    the last 52 bytes out. Preserve that exact raw output, require its known
    signature and complete Adler32 to match, then write the standard header
    before APK packaging/signing. No code or other DEX bytes may change.
    """
    d8_relative = 'prebuilts/sdk/tools/linux/lib/d8.jar'
    assert sha(regular(NATIVE / d8_relative)) == TOOL_PINS[d8_relative]
    raw = regular(dex).read_bytes()
    raw_path = delivery / 'classes.d8-raw.dex'
    with raw_path.open('xb') as handle:
        handle.write(raw)
    assert regular(raw_path).read_bytes() == raw, 'Raw D8 preservation failed'
    assert len(raw) >= 112 + 52, 'DEX too short for the pinned D8 format'
    assert raw[:8] == b'dex\n038\x00', 'Unexpected pinned D8 DEX magic/version'
    assert struct.unpack_from('<I', raw, 32)[0] == len(raw), 'DEX file_size mismatch'
    assert struct.unpack_from('<I', raw, 36)[0] == 112, 'DEX header_size mismatch'
    assert struct.unpack_from('<I', raw, 40)[0] == 0x12345678, 'DEX endian_tag mismatch'
    required = (b'Lcom/roc/rgsp/navtrial/NavigationService;',
                b'Lcom/roc/rgsp/navtrial/AxisNavigation;')
    for descriptor in required:
        assert descriptor in raw[112:], descriptor
    expected_raw_signature = hashlib.sha1(raw[32:-52]).digest()
    assert raw[12:32] == expected_raw_signature, 'Raw signature differs from pinned D8 EOF-84 bug'
    raw_adler = struct.unpack_from('<I', raw, 8)[0]
    assert raw_adler == zlib.adler32(raw[12:]) & 0xffffffff, 'Raw DEX Adler32 mismatch'

    normalized = bytearray(raw)
    normalized[12:32] = hashlib.sha1(raw[32:]).digest()
    struct.pack_into('<I', normalized, 8, zlib.adler32(normalized[12:]) & 0xffffffff)
    normalized = bytes(normalized)
    assert len(normalized) == len(raw)
    assert normalized[:8] == raw[:8], 'DEX magic/version changed'
    assert normalized[32:] == raw[32:], 'DEX body changed during header repair'
    changed_offsets = [i for i, (before, after) in enumerate(zip(raw, normalized))
                       if before != after]
    assert changed_offsets and all(8 <= i < 32 for i in changed_offsets)
    assert normalized[12:32] == hashlib.sha1(normalized[32:]).digest()
    assert struct.unpack_from('<I', normalized, 8)[0] == zlib.adler32(normalized[12:]) & 0xffffffff
    dex.write_bytes(normalized)
    assert regular(dex).read_bytes() == normalized, 'Normalized DEX readback mismatch'
    body_sha256 = hashlib.sha256(raw[32:]).hexdigest()
    receipt = {
        'schema': 1, 'pinned_d8_sha256': TOOL_PINS[d8_relative],
        'raw_path': str(raw_path), 'normalized_path': str(dex),
        'raw_bytes': len(raw), 'normalized_bytes': len(normalized),
        'raw_sha256': hashlib.sha256(raw).hexdigest(),
        'normalized_sha256': hashlib.sha256(normalized).hexdigest(),
        'raw_body_offset32_sha256': body_sha256,
        'normalized_body_offset32_sha256': hashlib.sha256(normalized[32:]).hexdigest(),
        'header_offsets8_to31_before_hex': raw[8:32].hex(),
        'header_offsets8_to31_after_hex': normalized[8:32].hex(),
        'raw_signature_pattern': 'SHA1(data[32:-52]); D8 update(data,32,EOF-84)',
        'raw_signature_matches_pinned_pattern': True,
        'raw_adler32_valid': True, 'raw_adler32': raw_adler,
        'raw_standard_signature_matches': raw[12:32] == hashlib.sha1(raw[32:]).digest(),
        'magic_version_file_size_header_size_endian_verified': True,
        'required_descriptors_verified': [value.decode('ascii') for value in required],
        'changed_byte_offsets': changed_offsets,
        'diff_subset_offsets8_to31': True,
        'first8_and_body_offset32_exactly_unchanged': True,
        'standard_after': True,
        'performed_before_APK_packaging_and_signing': True,
    }
    receipt_path = delivery / 'dex-header-normalization.json'
    write_json(receipt_path, receipt)
    return {'receipt': str(receipt_path), 'receipt_sha256': sha(receipt_path),
            'raw_path': str(raw_path), 'raw_sha256': receipt['raw_sha256'],
            'body_sha256': body_sha256, 'only_offsets8_to31_changed': True,
            'standard_after': True}


def main():
    constrained()
    # No flags permit alternate keys, Native trees, or output locations.
    if len(sys.argv) != 1:
        raise ValueError('Use H700NavigationFix through the low-pressure wrapper; no arguments')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    work = Path('/home/lpf/roc-os-navigation-fix-20261114-' + stamp)
    work.mkdir()
    base = REPO / 'out/nav-fix-20261114'
    delivery = base / 'builds' / stamp
    delivery.mkdir(parents=True)
    report = {'schema': 1, 'passed': False, 'work': str(work), 'output': str(delivery),
              'Android_images_built': False, 'Native_source_written': False,
              'device_accessed': False, 'APK_installed': False, 'private_key_copied': False}
    try:
        build(work, delivery, report)
        report['passed'] = True
    except BaseException as error:
        report['failure'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        write_json(delivery / 'build-result.json', report)
        # Each attempt is preserved; this file is only the latest-attempt pointer.
        write_json(base / 'build-result.json', report)
    print('NAVIGATION17_PRODUCTION_BUILD_VERIFIED; NOT_INSTALLED', flush=True)


def build(work, delivery, report):
    sdk = NATIVE / 'prebuilts/sdk/tools/linux'
    java = NATIVE / 'prebuilts/jdk/jdk9/linux-x86/bin/java'
    javac = java.with_name('javac')
    android = NATIVE / 'prebuilts/sdk/29/public/android.jar'
    for relative, digest in TOOL_PINS.items():
        assert sha(regular(NATIVE / relative)) == digest, relative
    identity = regular(KEYS / 'generation-complete.public.json')
    assert json.loads(identity.read_text())['roles']['platform']['certificate_sha256'] == PLATFORM_CERT
    cert = regular(KEYS / 'platform.x509.pem')
    der = ssl.PEM_cert_to_DER_cert(cert.read_text())
    assert hashlib.sha256(der).hexdigest() == PLATFORM_CERT
    key = regular(KEYS / 'platform.pk8')
    key_stat = (key.stat().st_ino, key.stat().st_size, key.stat().st_mtime_ns, key.stat().st_mode)
    # Only the signing subprocess reads key bytes. Lock public identity and sources.
    originals = source_inputs()
    overlay_set = set(overlay_files())
    native_guard = tree_hashes(NATIVE / 'device/roc/roc_os_source64/Navigation')
    assert native_guard[SERVICE] == '26010678339217441cae7f0a610c2c7a1f2704db6b0c7ca78da9d6b84cb05464'
    old_apk = regular(Path('/home/lpf/roc-os-user-20261104/out/target/product/roc_os_source64/system/app/ROCNavigation/ROCNavigation.apk'))
    assert sha(old_apk) == 'a5460ba1ad4956ca759797df561b19250110bc7626a351478c30d56492f0f5a6'
    space_review = regular(REPO / 'docs/SPACE_REVIEW_20261028.md')
    assert sha(space_review) == '847b55c93f1c0a36983ada5a500d4311b18022ef86b2db2aa3dc5614f0f400d6'
    service_test = regular(REPO / 'tools/navigation_tests/test_navigation_service_fix.py')
    controls = [RECIPE, Path(__file__), REPO / 'tools/build_h700_low_pressure.ps1',
                REPO / 'tools/build_h700_low_pressure.sh', identity, cert, old_apk,
                space_review, service_test]
    controls_sha = {str(p): sha(regular(p)) for p in controls}
    inputs = {relative: {'path': str(source), 'origin': origin, 'sha256': sha(source),
                         'bytes': source.stat().st_size}
              for relative, (source, origin) in sorted(originals.items())}
    candidate = work / 'candidate'
    candidate.mkdir()
    for relative, item in inputs.items():
        source = Path(item['path'])
        assert sha(source) == item['sha256'], 'Input changed during snapshot: ' + relative
        target = candidate / safe_relative(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        assert sha(target) == item['sha256']
    manifest = validate_manifest(candidate / 'AndroidManifest.xml')
    assert sha(candidate / 'res/xml/navigation_service.xml') == 'ed7a7a6eb292b261d9e7f23a80b13836b69b5517980429d0645df471cc92d3dd'
    lock = {'inputs': inputs, 'control_sha256': controls_sha, 'tool_sha256': TOOL_PINS,
            'Native_Navigation_before': native_guard, 'manifest': manifest,
            'platform_certificate_sha256': PLATFORM_CERT}
    write_json(delivery / 'input-lock.json', lock)
    report.update({'input_lock': str(delivery / 'input-lock.json'),
                   'input_lock_sha256': sha(delivery / 'input-lock.json'),
                   'manifest': manifest, 'platform_certificate_sha256': PLATFORM_CERT,
                   'shared_helpers': [r for r, item in inputs.items() if item['origin'] == 'sha256_checked_copy_recipe']})
    env = os.environ.copy()
    env['LD_LIBRARY_PATH'] = str(sdk / 'lib64')

    def run(args, name):
        args = [str(a) for a in args]
        result = subprocess.run(args, cwd=work, env=env, text=True, capture_output=True)
        with (delivery / 'commands.log').open('a', encoding='utf-8') as log:
            log.write(json.dumps(args) + '\n' + result.stdout + result.stderr + '\n')
        (delivery / (name + '.txt')).write_text(result.stdout + result.stderr, encoding='utf-8')
        if result.returncode:
            raise RuntimeError(name + ' failed; see ' + str(delivery / (name + '.txt')))
        return result.stdout

    old_verification = run([java, '-Xmx256m', '-jar', sdk / 'lib/apksigner.jar', 'verify',
                            '--min-sdk-version', '29', '--max-sdk-version', '29', '--verbose',
                            '--print-certs', old_apk], 'old-signature-verification')
    assert re.findall(r'certificate SHA-256 digest: (\w+)', old_verification) == [PLATFORM_CERT]
    report['old_system_APK_Android10_signature_verified'] = True
    # New controller cases must pass before packaging. Existing helper cases also run.
    test_root = REPO / 'tools/navigation_tests/com/roc/rgsp/navtrial'
    test_names = ['AxisNavigation', 'Direction', 'FocusIdentity', 'MenuHotkey', 'MouseHotkey', 'PointerPosition', 'StickVector']
    test_classes = {name: name + 'Test' for name in test_names}
    # Source64 intentionally normalizes scan310 without FLAG_FALLBACK. The
    # ordinary RGSP test retains its different contract and remains untouched.
    test_classes['MouseHotkey'] = 'Source64MouseHotkeyTest'
    test_sources = []
    for name in test_names:
        source = regular(candidate / ('src/com/roc/rgsp/navtrial/' + name + '.java'))
        test = regular(test_root / (test_classes[name] + '.java'))
        controls_sha[str(test)] = sha(test)
        test_sources += [source, test]
    # Persist every test input before any compiler runs, including failed attempts.
    write_json(delivery / 'input-lock.json', lock)
    report['input_lock_sha256'] = sha(delivery / 'input-lock.json')
    host_classes = work / 'host-classes'
    host_classes.mkdir()
    run([javac, '-J-Xmx512m', '-source', '8', '-target', '8', '-d', host_classes, *test_sources], 'host-javac')
    for name in test_names:
        run([java, '-Xmx128m', '-cp', host_classes, 'com.roc.rgsp.navtrial.' + test_classes[name]], 'host-' + name)
    report['host_test_classes'] = [test_classes[name] for name in test_names]
    service_result = delivery / 'service-fragments-result.json'
    run([sys.executable, '-B', service_test, '--source', candidate / SERVICE,
         '--axis', candidate / AXIS, '--javac', javac, '--java', java,
         '--work', work / 'service-fragment-tests', '--result', service_result], 'host-service-fragments')
    service_receipt = json.loads(service_result.read_text())
    assert service_receipt['passed'] is True
    assert service_receipt['source_sha256'] == inputs[SERVICE]['sha256']
    assert service_receipt['axis_sha256'] == inputs[AXIS]['sha256']
    assert service_receipt['test_script_sha256'] == controls_sha[str(service_test)]
    assert service_receipt['hardware_reproduction'] is False
    report['actual_Service_fragments_virtual_framework_passed'] = True
    report['Service_fragment_result'] = str(service_result)
    report['Service_fragment_result_sha256'] = sha(service_result)
    # Persist the complete lock including tests before Android compilation.
    write_json(delivery / 'input-lock.json', lock)
    report['input_lock_sha256'] = sha(delivery / 'input-lock.json')
    gen, classes, dexdir = work / 'gen', work / 'classes', work / 'dex'
    for p in (gen, classes, dexdir):
        p.mkdir()
    resource_apk = work / 'resources.apk'
    run([sdk / 'bin/aapt', 'package', '-f', '-M', candidate / 'AndroidManifest.xml',
         '-S', candidate / 'res', '-I', android, '-J', gen, '-F', resource_apk], 'aapt-package')
    java_sources = sorted((candidate / 'src').rglob('*.java')) + sorted(gen.rglob('*.java'))
    run([javac, '-J-Xmx1g', '-source', '8', '-target', '8', '-g:none', '-bootclasspath',
         str(android) + ':' + str(sdk / 'bin/core-lambda-stubs.jar'), '-d', classes, *java_sources], 'android-javac')
    jar = work / 'classes.jar'
    with zipfile.ZipFile(jar, 'x') as archive:
        for p in sorted(classes.rglob('*.class')):
            archive.write(p, p.relative_to(classes).as_posix())
    run([java, '-Xmx2g', '-cp', sdk / 'lib/d8.jar', 'com.android.tools.r8.D8',
         '--min-api', '29', '--lib', android, '--output', dexdir, jar], 'd8')
    dex = regular(dexdir / 'classes.dex')
    report['DEX_header_normalization'] = normalize_pinned_d8_header(dex, delivery)
    data = dex.read_bytes()
    assert data[:4] == b'dex\n' and struct.unpack_from('<I', data, 32)[0] == len(data)
    assert data[12:32] == hashlib.sha1(data[32:]).digest()
    assert struct.unpack_from('<I', data, 8)[0] == zlib.adler32(data[12:]) & 0xffffffff
    for descriptor in (b'Lcom/roc/rgsp/navtrial/NavigationService;', b'Lcom/roc/rgsp/navtrial/AxisNavigation;'):
        assert descriptor in data, descriptor
    run([sdk / 'bin/dexdump', '-d', dex], 'dexdump')
    unsigned = work / 'unsigned.apk'
    with zipfile.ZipFile(resource_apk) as incoming, zipfile.ZipFile(unsigned, 'x') as outgoing:
        assert len(incoming.namelist()) == len(set(incoming.namelist()))
        for info in incoming.infolist():
            assert not info.filename.startswith('META-INF/') and not info.filename.endswith('.dex')
            outgoing.writestr(info, incoming.read(info.filename))
        outgoing.write(dex, 'classes.dex', compress_type=zipfile.ZIP_STORED)
    aligned = work / 'aligned.apk'
    run([sdk / 'bin/zipalign', '-f', '-p', '4', unsigned, aligned], 'zipalign')
    apk = delivery / 'ROCNavigation17.apk'
    run([java, '-Xmx256m', '-jar', sdk / 'lib/apksigner.jar', 'sign', '--min-sdk-version', '29',
         '--key', key, '--cert', cert, '--out', apk, aligned], 'sign')
    verification = run([java, '-Xmx256m', '-jar', sdk / 'lib/apksigner.jar', 'verify',
                        '--min-sdk-version', '29', '--max-sdk-version', '29', '--verbose', '--print-certs', apk], 'signature-verification')
    assert re.findall(r'certificate SHA-256 digest: (\w+)', verification) == [PLATFORM_CERT]
    run([sdk / 'bin/zipalign', '-c', '4', apk], 'alignment-verification')
    badging = run([sdk / 'bin/aapt', 'dump', 'badging', apk], 'badging')
    assert re.search(r"package: name='" + re.escape(PACKAGE) + r"' versionCode='17'", badging)
    assert "sdkVersion:'29'" in badging and "targetSdkVersion:'29'" in badging
    assert re.findall(r"uses-permission: name='([^']+)'", badging) == ['android.permission.EXPAND_STATUS_BAR']

    def payload(path):
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            assert len(names) == len(set(names))
            assert [n for n in names if n.endswith('.dex')] == ['classes.dex']
            return {n: hashlib.sha256(archive.read(n)).hexdigest() for n in names
                    if not n.startswith('META-INF/')}

    assert payload(aligned) == payload(apk), 'Signing changed non-signature payload'
    for relative, item in inputs.items():
        assert sha(Path(item['path'])) == item['sha256'], 'Source changed while building: ' + relative
    assert set(overlay_files()) == overlay_set, 'Candidate input set changed while building'
    assert tree_hashes(NATIVE / 'device/roc/roc_os_source64/Navigation') == native_guard
    assert all(sha(Path(p)) == digest for p, digest in controls_sha.items()), 'Control/test input changed'
    assert all(sha(NATIVE / p) == digest for p, digest in TOOL_PINS.items()), 'Tool changed'
    assert (key.stat().st_ino, key.stat().st_size, key.stat().st_mtime_ns, key.stat().st_mode) == key_stat
    report.update({'artifact': str(apk), 'artifact_bytes': apk.stat().st_size, 'artifact_sha256': sha(apk),
                   'DEX_sha256': sha(dex), 'DEX_integrity_and_required_classes': True,
                   'Android10_signature_verified': True, 'zipalign_verified': True,
                   'APK_unique_members_and_payload_verified': True, 'all_inputs_unchanged_after_build': True,
                   'Native_Navigation_unchanged': True, 'limits': {'aggregate_cpu': 1, 'cpus': '0-1',
                   'nice': 19, 'memory_max_GiB': 6, 'swap_max_MiB': 512}})


if __name__ == '__main__':
    main()

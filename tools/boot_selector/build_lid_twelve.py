"""Build an isolated production-signed twelve-model Lid4; never edit mother images or Native.

Run through tools/public_build/run-limited.sh. Only the signing subprocess reads
the existing production key. The boot selector must emit androidboot.roc_model
and androidboot.roc_clamshell. No root-init changes are required.
"""
from pathlib import Path
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
sys.path.insert(0, str(REPO / 'tools/release'))
from build_navigation_fix import (KEYS, NATIVE, PLATFORM_CERT, TOOL_PINS,
                                  constrained, regular, sha, write_json)

SOURCE = REPO / 'android/h700-android10/device/roc/roc_os_release_candidate/Lid'
SUPPORT = Path(__file__).parent / 'twelve_model/lid'
MOTHER = Path('/home/lpf/roc-os-002-20261114-v1/system.002.raw')
INSTALL = '/system/priv-app/ROCReleaseLid/ROCReleaseLid.apk'
OLD_SHA = 'dbe920ca66e95dce77764e517da99e71f4708ba2135e4db860163983f1283bc2'
OLD_OAT = {
    '/system/priv-app/ROCReleaseLid/oat/arm64/ROCReleaseLid.odex': 'b2589b223e78627bb347680d65771c084cb367b64bb1622123b810c9ab6c7e96',
    '/system/priv-app/ROCReleaseLid/oat/arm64/ROCReleaseLid.vdex': '94308d91e161092a7b97b92ccd94845a6bc068a187eadda78cfff1b2f37e5217',
}
PRODUCT = Path('/home/lpf/roc-os-user-20261104/out/target/product/roc_os_source64')
HOST = Path('/home/lpf/roc-os-user-20261104/out/host/linux-x86/bin')
NS = '{http://schemas.android.com/apk/res/android}'


def normalize_dex(dex, delivery):
    raw = regular(dex).read_bytes()
    (delivery / 'classes.d8-raw.dex').write_bytes(raw)
    assert len(raw) > 164 and raw[:8] == b'dex\n038\0'
    assert struct.unpack_from('<I', raw, 32)[0] == len(raw)
    assert raw[12:32] == hashlib.sha1(raw[32:-52]).digest()
    assert struct.unpack_from('<I', raw, 8)[0] == zlib.adler32(raw[12:]) & 0xffffffff
    result = bytearray(raw)
    result[12:32] = hashlib.sha1(raw[32:]).digest()
    struct.pack_into('<I', result, 8, zlib.adler32(result[12:]) & 0xffffffff)
    result = bytes(result)
    assert result[:8] == raw[:8] and result[32:] == raw[32:]
    dex.write_bytes(result)
    receipt = {'raw_sha256': hashlib.sha256(raw).hexdigest(), 'normalized_sha256': sha(dex),
               'only_offsets8_to31_changed': True, 'body_sha256': hashlib.sha256(raw[32:]).hexdigest(),
               'pinned_d8_sha256': TOOL_PINS['prebuilts/sdk/tools/linux/lib/d8.jar'],
               'standard_sha1_and_adler_after': True}
    write_json(delivery / 'dex-header-normalization.json', receipt)
    return receipt


def main():
    constrained()
    assert len(sys.argv) == 1, 'No arguments accepted'
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    work = Path('/home/lpf/roc-os-lid-twelve-20261116-' + stamp)
    work.mkdir()
    delivery = REPO / 'out/twelve-model-enablement-20261116/lid' / stamp
    delivery.mkdir(parents=True)
    report = {'schema': 1, 'passed': False, 'work': str(work), 'output': str(delivery),
              'Android_images_built': False, 'Native_written': False, 'mother_image_written': False,
              'device_accessed': False, 'APK_installed': False, 'private_key_copied': False}
    try:
        build(work, delivery, report)
        report['passed'] = True
    except BaseException as error:
        report['failure'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        write_json(delivery / 'build-result.json', report)
        write_json(delivery.parent / 'latest-build.json', report)
    print('LID4_MODEL_GATE_PRODUCTION_SIGNED_PASS; NOT_INSTALLED', flush=True)


def build(work, delivery, report):
    sdk = NATIVE / 'prebuilts/sdk/tools/linux'
    java = NATIVE / 'prebuilts/jdk/jdk9/linux-x86/bin/java'
    javac = java.with_name('javac')
    android = NATIVE / 'prebuilts/sdk/29/public/android.jar'
    for path, digest in TOOL_PINS.items():
        assert sha(regular(NATIVE / path)) == digest
    identity = regular(KEYS / 'generation-complete.public.json')
    assert json.loads(identity.read_text())['roles']['platform']['certificate_sha256'] == PLATFORM_CERT
    cert, key = regular(KEYS / 'platform.x509.pem'), regular(KEYS / 'platform.pk8')
    assert hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.read_text())).hexdigest() == PLATFORM_CERT
    key_stat = (key.stat().st_ino, key.stat().st_size, key.stat().st_mtime_ns, key.stat().st_mode)
    controls = [Path(__file__), SUPPORT / 'LidProfile.java', SUPPORT / 'LidProfileTest.java',
                REPO / 'tools/lid_tests/UniversalLidStateTest.java',
                REPO / 'tools/release/build_navigation_fix.py', REPO / 'tools/public_build/run-limited.sh',
                REPO / 'docs/SPACE_REVIEW_20261028.md', identity, cert]
    control_sha = {str(p): sha(regular(p)) for p in controls}
    assert control_sha[str(REPO / 'docs/SPACE_REVIEW_20261028.md')] == '847b55c93f1c0a36983ada5a500d4311b18022ef86b2db2aa3dc5614f0f400d6'
    original_sha = {p.relative_to(SOURCE).as_posix(): sha(regular(p)) for p in sorted(SOURCE.rglob('*')) if p.is_file()}
    candidate = work / 'candidate'
    shutil.copytree(SOURCE, candidate)
    package = candidate / 'src/com/roc/rgsp/lid'
    shutil.copyfile(SUPPORT / 'LidProfile.java', package / 'LidProfile.java')
    service = package / 'LidService.java'
    text = service.read_text()
    old = ('return "rgsp".equals(property("ro.product.device"))\n'
           '                && "rg34xxsp".equals(property("persist.vendor.rgsp.input_profile"))\n'
           '                && SENSOR.canRead();')
    new = ('return LidProfile.supported(property("ro.boot.roc_model"),\n'
           '                property("ro.boot.roc_clamshell"), property("ro.product.device"),\n'
           '                property("persist.vendor.rgsp.input_profile"), SENSOR.canRead());')
    assert text.count(old) == 1
    service.write_text(text.replace(old, new).replace('Explicit RG34XXSP profile only',
                       'Explicit boot-selected clamshell profile only'))
    manifest = candidate / 'AndroidManifest.xml'
    text = manifest.read_text()
    assert text.count('versionCode="2" android:versionName="1.1"') == 1
    manifest.write_text(text.replace('versionCode="2" android:versionName="1.1"',
                        'versionCode="4" android:versionName="1.3-twelve-model"'))
    root = ET.parse(manifest).getroot()
    assert root.get('package') == 'com.roc.rgsp.lid' and root.get(NS + 'versionCode') == '4'
    expected_permissions = ['android.permission.DEVICE_POWER', 'android.permission.RECEIVE_BOOT_COMPLETED',
                            'android.permission.FOREGROUND_SERVICE']
    assert [node.get(NS + 'name') for node in root.findall('uses-permission')] == expected_permissions
    candidate_sha = {p.relative_to(candidate).as_posix(): sha(regular(p)) for p in sorted(candidate.rglob('*')) if p.is_file()}
    changed = [p for p in original_sha if candidate_sha[p] != original_sha[p]]
    assert changed == ['AndroidManifest.xml', 'src/com/roc/rgsp/lid/LidService.java'], changed
    assert sha(package / 'LidState.java') == original_sha['src/com/roc/rgsp/lid/LidState.java']
    write_json(delivery / 'input-lock.json', {'original_source': str(SOURCE), 'original_sha256': original_sha,
               'candidate_sha256': candidate_sha, 'control_sha256': control_sha, 'tool_sha256': TOOL_PINS,
               'changed_original_members': changed, 'added_members': ['src/com/roc/rgsp/lid/LidProfile.java']})
    shutil.copytree(candidate, delivery / 'candidate-source')
    env = os.environ.copy()
    env['LD_LIBRARY_PATH'] = str(sdk / 'lib64')

    def run(args, name, expected=(0,)):
        result = subprocess.run(list(map(str, args)), cwd=work, env=env, text=True, capture_output=True)
        (delivery / (name + '.txt')).write_text(result.stdout + result.stderr)
        with (delivery / 'commands.jsonl').open('a') as log:
            log.write(json.dumps({'argv': list(map(str, args)), 'rc': result.returncode}) + '\n')
        assert result.returncode in expected, name + ' failed'
        return result.stdout

    old_apk = work / 'original-system-Lid.apk'
    run(['/usr/sbin/debugfs', '-R', f'dump {INSTALL} {old_apk}', regular(MOTHER)], 'mother-apk-readonly-extract')
    assert sha(old_apk) == OLD_SHA
    shutil.copyfile(old_apk, delivery / 'original-system-Lid.apk')
    run(['/usr/sbin/debugfs', '-R', 'stat ' + INSTALL, MOTHER], 'mother-apk-stat')
    run(['/usr/sbin/debugfs', '-R', 'ea_list ' + INSTALL, MOTHER], 'mother-apk-label')
    for name, digest in OLD_OAT.items():
        saved = work / Path(name).name
        run(['/usr/sbin/debugfs', '-R', f'dump {name} {saved}', MOTHER], 'mother-' + Path(name).suffix[1:] + '-extract')
        assert sha(saved) == digest
    old_verification = run([java, '-Xmx256m', '-jar', sdk / 'lib/apksigner.jar', 'verify',
               '--min-sdk-version', '29', '--max-sdk-version', '29', '--verbose', '--print-certs', old_apk], 'old-signature')
    assert re.findall(r'certificate SHA-256 digest: (\w+)', old_verification) == [PLATFORM_CERT]
    with zipfile.ZipFile(old_apk) as archive:
        old_dex = archive.read('classes.dex')
    assert b'ro.product.device' in old_dex and b'persist.vendor.rgsp.input_profile' in old_dex
    assert b'ro.boot.roc_model' not in old_dex and b'ro.boot.roc_clamshell' not in old_dex
    policy = regular(PRODUCT / 'vendor/etc/selinux/precompiled_sepolicy')
    for permission in ['read', 'open', 'getattr', 'map']:
        run([HOST / 'sepolicy-analyze', policy, 'neverallow', '-n',
             f'neverallow platform_app exported2_default_prop:file {permission};'], 'policy-read-' + permission, (255,))
    run([HOST / 'sepolicy-analyze', policy, 'neverallow', '-n',
         'neverallow platform_app exported2_default_prop:property_service set;'], 'policy-no-write')
    gen, classes, dexdir = work / 'gen', work / 'classes', work / 'dex'
    for path in [gen, classes, dexdir]:
        path.mkdir()
    resources = work / 'resources.apk'
    run([sdk / 'bin/aapt', 'package', '-f', '-M', manifest, '-I', android, '-J', gen, '-F', resources], 'aapt')
    sources = sorted((candidate / 'src').rglob('*.java')) + sorted(gen.rglob('*.java'))
    run([javac, '-J-Xmx512m', '-source', '8', '-target', '8', '-g:none', '-bootclasspath',
         str(android) + ':' + str(sdk / 'bin/core-lambda-stubs.jar'), '-d', classes, *sources], 'android-javac')
    jar = work / 'classes.jar'
    with zipfile.ZipFile(jar, 'x') as archive:
        for path in sorted(classes.rglob('*.class')):
            archive.write(path, path.relative_to(classes).as_posix())
    tests = work / 'tests'
    tests.mkdir()
    run([javac, '-J-Xmx256m', '-source', '8', '-target', '8', '-cp', classes, '-d', tests,
         SUPPORT / 'LidProfileTest.java', REPO / 'tools/lid_tests/UniversalLidStateTest.java'], 'test-javac')
    checks = run([java, '-Xmx64m', '-cp', str(classes) + ':' + str(tests), 'com.roc.rgsp.lid.LidProfileTest'], 'model-tests')
    state = run([java, '-Xmx64m', '-cp', str(classes) + ':' + str(tests), 'com.roc.rgsp.lid.UniversalLidStateTest'], 'state-tests')
    assert 'LID_MODEL_PROFILE_PASS checks=656' in checks and 'UNIVERSAL_HALL_EDGE_PASS checks=3613' in state
    run([java, '-Xmx512m', '-cp', sdk / 'lib/d8.jar', 'com.android.tools.r8.D8', '--min-api', '29',
         '--lib', android, '--output', dexdir, jar], 'd8')
    dex = dexdir / 'classes.dex'
    normalization = normalize_dex(dex, delivery)
    data = dex.read_bytes()
    for value in [b'ro.boot.roc_model', b'ro.boot.roc_clamshell', b'Lcom/roc/rgsp/lid/LidProfile;',
                  b'Lcom/roc/rgsp/lid/LidService;', b'Lcom/roc/rgsp/lid/LidState;']:
        assert value in data
    run([sdk / 'bin/dexdump', '-d', dex], 'dexdump')
    unsigned = work / 'unsigned.apk'
    with zipfile.ZipFile(resources) as incoming, zipfile.ZipFile(unsigned, 'x') as outgoing:
        for info in incoming.infolist():
            assert not info.filename.startswith('META-INF/') and not info.filename.endswith('.dex')
            outgoing.writestr(info, incoming.read(info.filename))
        outgoing.write(dex, 'classes.dex', compress_type=zipfile.ZIP_STORED)
    aligned = work / 'aligned.apk'
    run([sdk / 'bin/zipalign', '-f', '-p', '4', unsigned, aligned], 'zipalign')
    apk = delivery / 'ROCReleaseLid4_TwelveModel.apk'
    run([java, '-Xmx256m', '-jar', sdk / 'lib/apksigner.jar', 'sign', '--min-sdk-version', '29',
         '--key', key, '--cert', cert, '--out', apk, aligned], 'sign')
    verification = run([java, '-Xmx256m', '-jar', sdk / 'lib/apksigner.jar', 'verify', '--min-sdk-version', '29',
                        '--max-sdk-version', '29', '--verbose', '--print-certs', apk], 'new-signature')
    assert re.findall(r'certificate SHA-256 digest: (\w+)', verification) == [PLATFORM_CERT]
    badge = run([sdk / 'bin/aapt', 'dump', 'badging', apk], 'badging')
    assert "name='com.roc.rgsp.lid' versionCode='4' versionName='1.3-twelve-model'" in badge
    assert re.findall(r"uses-permission: name='([^']+)'", badge) == expected_permissions
    run([sdk / 'bin/zipalign', '-c', '4', apk], 'align-verify')
    assert all(sha(Path(path)) == digest for path, digest in control_sha.items())
    assert original_sha == {p.relative_to(SOURCE).as_posix(): sha(p) for p in sorted(SOURCE.rglob('*')) if p.is_file()}
    assert (key.stat().st_ino, key.stat().st_size, key.stat().st_mtime_ns, key.stat().st_mode) == key_stat
    write_json(delivery / 'semantic-tests.json', {'passed': True, 'model_gate_checks': 656,
               'actual_compiled_LidState_checks': 3613, 'original_LidState_source_unchanged': True,
               'rg35xxh_all_flags_denied': True, 'legacy_absent_both_preserved': True,
               'explicit_unknown_or_mismatched_identities_denied': True, 'hardware_tested': False})
    report.update({'artifact': str(apk), 'artifact_sha256': sha(apk), 'artifact_bytes': apk.stat().st_size,
                   'install_path': INSTALL, 'remove_stale_oat': OLD_OAT, 'original_apk_sha256': OLD_SHA,
                   'platform_certificate_sha256': PLATFORM_CERT, 'old_and_new_Android10_signature_verified': True,
                   'permissions_unchanged': expected_permissions, 'ro_boot_property_read_allowed': True,
                   'ro_boot_property_write_forbidden': True, 'policy_sha256': sha(policy),
                   'model_gate_checks': 656, 'state_checks': 3613, 'dex_normalization': normalization,
                   'original_source_unchanged': True, 'limits': {'cpu_quota': '100%', 'cpus': '0,1',
                   'memory_max': '6G', 'swap_max': '512M', 'nice': 19, 'shared_flock': True}})


if __name__ == '__main__':
    main()

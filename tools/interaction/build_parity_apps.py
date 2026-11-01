"""Rebase pinned final ARM32 UI APK resources onto GSI API29, offline only.

Outputs use this project's development signing roles. They require a coherent
new system signing set; these are never installed over the running GSI.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained

constrained()
ROOT = Path('/home/lpf/h700-dualabi-parity-20261101')
WORK = ROOT / 'rebased-apps-v2'
WORK.mkdir(exist_ok=False)
OUT = REPO / 'out/dualabi-parity-20261101'
native = Path('/home/lpf/h700-android10/android')
sdk = native / 'prebuilts/sdk/tools/linux'
jdk = native / 'prebuilts/jdk/jdk9/linux-x86/bin'
os.environ['LD_LIBRARY_PATH'] = str(sdk / 'lib64')
tool = Path('/home/lpf/h700-at4k-20261028/apktool-2.9.3.jar')
assert hashlib.sha256(tool.read_bytes()).hexdigest() == '7956eb04194300ce0d0a84ad18771eebc94b89fb8d1ddcce8ea4c056818646f4'
comparison = json.loads((OUT / 'component-comparison.json').read_text())['components']
receipt = {'status': 'building', 'requires_coherent_new_system_signing': True, 'apps': {}}

def run(*args):
    p = subprocess.run(list(map(str, args)), capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stdout.decode(errors='replace')[-5000:] + p.stderr.decode(errors='replace')[-5000:])
    return p.stdout.decode(errors='replace') + p.stderr.decode(errors='replace')

def save():
    (OUT / 'rebased-apps-v2.json').write_text(json.dumps(receipt, indent=2) + '\n')

try:
    mappings = {}
    for flavor in ('arm32', 'gsi'):
        apk = ROOT / ('inputs-' + flavor) / 'framework-res.apk'
        listing = run(sdk / 'bin/aapt', 'dump', 'resources', apk)
        (WORK / (flavor + '-framework-res.txt')).write_text(listing)
        mappings[flavor] = {int(a, 16): b for a, b in re.findall(
            r'spec resource (0x[0-9a-f]+) android:([^: ]+):', listing)}
        cache = WORK / ('framework-' + flavor)
        cache.mkdir()
        run(jdk / 'java', '-Xmx1g', '-jar', tool, 'if', '-p', cache, apk)
    byname = {name: value for value, name in mappings['gsi'].items()}
    rebase = {old: byname[name] for old, name in mappings['arm32'].items() if name in byname}
    receipt['framework_ids'] = {'old_count': len(mappings['arm32']), 'gsi_count': len(byname),
                              'changed': sum(k != v for k, v in rebase.items())}
    cert_roles = {}
    for role in ('platform', 'testkey', 'shared', 'media'):
        pem = native / f'build/make/target/product/security/{role}.x509.pem'
        certificate = run('openssl', 'x509', '-in', pem, '-noout', '-fingerprint', '-sha256')
        cert_roles[certificate.strip().split('=')[-1].replace(':', '').lower()] = role
    for name in ('Settings', 'DocumentsUI', 'LatinIME', 'PermissionController',
                 'PackageInstaller', 'SettingsIntelligence', 'Calendar', 'Contacts', 'Traceur',
                 'MediaProvider'):
        if name in ('Settings', 'DocumentsUI') and (OUT / 'rebased-apps-v1.json').exists():
            previous = json.loads((OUT / 'rebased-apps-v1.json').read_text())['apps'][name]
            candidate = ROOT / 'rebased-apps-v1' / (name + '.apk')
            assert hashlib.sha256(candidate.read_bytes()).hexdigest() == previous['sha256']
            shutil.copyfile(candidate, WORK / (name + '.apk'))
            receipt['apps'][name] = {**previous, 'reused_verified_v1_candidate': True}
            save()
            print('PARITY_REUSE_VERIFIED', name, flush=True)
            continue
        source = ROOT / 'inputs-arm32' / (name + '.apk')
        lock = comparison[name]['arm32']
        assert hashlib.sha256(source.read_bytes()).hexdigest() == lock['sha256']
        cert = re.search(r'certificate SHA-256 digest: (\w+)', lock['signature']).group(1)
        role = cert_roles[cert]
        decoded = WORK / (name + '-decoded')
        print('PARITY_DECODE', name, flush=True)
        run(jdk / 'java', '-Xmx2g', '-jar', tool, 'd', '-f', '-p', WORK / 'framework-arm32', '-o', decoded, source)
        changed = 0
        missing = set()
        for smali in decoded.rglob('*.smali'):
            text = smali.read_text()
            def remap(match):
                nonlocal_changed = int(match[0], 16)
                if nonlocal_changed not in mappings['arm32']:
                    return match[0]
                if nonlocal_changed not in rebase:
                    missing.add(mappings['arm32'][nonlocal_changed])
                    return match[0]
                return hex(rebase[nonlocal_changed])
            updated = re.sub(r'(?<![\w])0x1[0-9a-f]{6}(?![\w])', remap, text)
            if updated != text:
                changed += 1
                smali.write_text(updated)
        if missing:
            receipt['apps'][name] = {'missing_framework_ids': sorted(missing)}
            raise ValueError('Unmapped framework IDs in ' + name + ': ' + str(sorted(missing)))
        unsigned = WORK / (name + '-unsigned.apk')
        print('PARITY_REBUILD', name, 'rebased_smali_files', changed, flush=True)
        run(jdk / 'java', '-Xmx2g', '-jar', tool, 'b', '-p', WORK / 'framework-gsi', '-o', unsigned, decoded)
        aligned = WORK / (name + '-aligned.apk')
        run(sdk / 'bin/zipalign', '-f', '-p', '4', unsigned, aligned)
        target = WORK / (name + '.apk')
        run(jdk / 'java', '-Xmx1g', '-jar', sdk / 'lib/apksigner.jar', 'sign',
            '--key', native / f'build/make/target/product/security/{role}.pk8',
            '--cert', native / f'build/make/target/product/security/{role}.x509.pem',
            '--min-sdk-version', '29', '--out', target, aligned)
        verified = run(jdk / 'java', '-Xmx1g', '-jar', sdk / 'lib/apksigner.jar', 'verify',
                       '--min-sdk-version', '29', '--print-certs', target)
        with zipfile.ZipFile(target) as z:
            assert not [n for n in z.namelist() if n.startswith('lib/') and n.endswith('.so')]
            markers = sorted(set(m.decode() for n in z.namelist() if n.endswith('.dex')
                                 for m in re.findall(rb'Rgsp[A-Za-z0-9_$]+', z.read(n))))
        assert set(lock['rgsp_dex_markers']) <= set(markers)
        receipt['apps'][name] = {'source_sha256': lock['sha256'], 'signing_role': role,
            'bytes': target.stat().st_size, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
            'smali_resource_files_rebased': changed, 'rgsp_markers_preserved': True,
            'apk_signature_verified': bool(verified)}
        save()
        print('PARITY_APP_CANDIDATE', name, flush=True)
    receipt['status'] = 'all_rebased_signed_offline_not_runtime_accepted'
    save()
except Exception as error:
    receipt['status'] = 'failed_preserved'
    receipt['error'] = str(error)
    save()
    raise

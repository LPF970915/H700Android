"""Validate original publisher APKs for the requested ARM64 preinstall batch."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained
constrained()
OUT = REPO / 'out/dualabi-parity-20261101'
downloads = OUT / 'arm64-apps'
native = Path('/home/lpf/h700-android10/android')
sdk = native / 'prebuilts/sdk/tools/linux'
java = native / 'prebuilts/jdk/jdk9/linux-x86/bin/java'
os.environ['LD_LIBRARY_PATH'] = str(sdk / 'lib64')
old = {a['id']: a for a in json.loads((REPO / 'config/pegasus/preinstall-apks-v6b.json').read_text())}
selected = [('AnimekoTV', 'animeko'), ('NOVA', 'nova'), ('KOReader', 'koreader'),
            ('Pegasus', 'pegasus'), ('RetroArch', 'retroarch'), ('PPSSPP', None), ('MTManager', None)]
result = {'requested_abi': 'arm64-v8a', 'apps': [], 'excluded': [
    {'id': 'QQMusicTV', 'reason': 'Current official TV download is armeabi-v7a only; no automatic ARM32 or phone fallback'}]}

def run(*args):
    p = subprocess.run(list(map(str, args)), capture_output=True, check=True)
    return p.stdout.decode(errors='replace') + p.stderr.decode(errors='replace')

def certificate(file):
    text = run(java, '-Xmx256m', '-jar', sdk / 'lib/apksigner.jar', 'verify',
               '--min-sdk-version', '29', '--max-sdk-version', '29', '--print-certs', file)
    return re.search(r'certificate SHA-256 digest: (\w+)', text)[1]

for identifier, key in selected:
    if key:
        source = json.loads((downloads / (key + '-download.json')).read_text())
        file = downloads / source['file']
    else:
        source = old[identifier]
        file = REPO / source['file']
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    assert digest == source['sha256'] and file.stat().st_size == source['bytes']
    cert = certificate(file)
    assert cert == certificate(REPO / old[identifier]['file']), identifier + ' publisher changed'
    badging = run(sdk / 'bin/aapt', 'dump', 'badging', file)
    package = re.search(r"package: name='([^']+)'", badging)[1]
    version_name = re.search(r"versionName='([^']+)'", badging)[1]
    version_code = int(re.search(r"versionCode='([^']+)'", badging)[1])
    minimum = int(re.search(r"sdkVersion:'([^']+)'", badging)[1])
    assert minimum <= 29, identifier
    expected_package = 'com.retroarch.aarch64' if identifier == 'RetroArch' else old[identifier]['package']
    assert package == expected_package, (identifier, package)
    with zipfile.ZipFile(file) as z:
        libraries = [n for n in z.namelist() if n.startswith('lib/arm64-v8a/') and n.endswith('.so')]
        assert libraries, identifier
        abis = sorted({n.split('/')[1] for n in z.namelist() if n.startswith('lib/') and n.endswith('.so')})
        for name in libraries:
            with z.open(name) as stream:
                header = stream.read(64)
            assert header[:5] == b'\x7fELF\x02' and int.from_bytes(header[18:20], 'little') == 183, name
    result['apps'].append({'id': identifier, 'package': package, 'version_name': version_name,
        'version_code': version_code, 'minimum_api': minimum, 'file': file.relative_to(REPO).as_posix(),
        'bytes': file.stat().st_size, 'sha256': digest, 'publisher_certificate_sha256': cert,
        'same_publisher_as_validated_arm32': True, 'available_abis': abis,
        'install_abi': 'arm64-v8a', 'elf64_libraries_checked': len(libraries),
        'url': source.get('url'), 'runtime_accepted': False})
    print('ARM64_ORIGINAL_SIGNATURE_ELF_API29_VALIDATED', identifier, package, version_name, flush=True)
(OUT / 'preinstall64-audit-v1.json').write_text(json.dumps(result, indent=2) + '\n')
print('ARM64_PREINSTALL_STATIC_AUDIT_COMPLETE', flush=True)

"""Read pinned ARM32 and GSI application inputs without changing either image."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained

constrained()
WORK = Path('/home/lpf/h700-dualabi-parity-20261101')
OUT = REPO / 'out/dualabi-parity-20261101'
OUT.mkdir(exist_ok=True)
WORK.mkdir(exist_ok=True)
images = {
    'arm32': Path('/home/lpf/h700-release-v6b-20261030/system.candidate.raw'),
    'gsi': Path('/home/lpf/h700-dualabi-test1-20261031/system.candidate.raw'),
}
components = json.loads((REPO / 'out/h700-v5i-dpad-20261027-native35-notouch-stage/components.json').read_text())
native = Path('/home/lpf/h700-android10/android')
sdk = native / 'prebuilts/sdk/tools/linux'
java = native / 'prebuilts/jdk/jdk9/linux-x86/bin/java'
names = ['Settings', 'SettingsIntelligence', 'SettingsProvider', 'MediaProvider', 'SystemUI',
         'DocumentsUI', 'LatinIME', 'LeanbackIME', 'PermissionController', 'PackageInstaller',
         'Calendar', 'Contacts', 'Traceur']
result = {'inputs': {}, 'components': {}}

def run(*args):
    p = subprocess.run(list(map(str, args)), capture_output=True, check=True)
    return p.stdout.decode(errors='replace') + p.stderr.decode(errors='replace')

for flavor, image in images.items():
    assert image.is_file() and image.stat().st_size == 8589934592
    dest = WORK / ('inputs-' + flavor)
    dest.mkdir(exist_ok=True)
    for name in names + ['framework-res', 'services', 'framework']:
        extension = '.jar' if name in ('services', 'framework') else '.apk'
        candidates = ([f'/system/framework/{name}{extension}'] if name in ('framework-res', 'services', 'framework') else
            [f'/system/{part}/{name}/{name}.apk' for part in ('product/priv-app', 'priv-app', 'product/app', 'app')])
        found = []
        for candidate in candidates:
            stat = run('debugfs', '-R', 'stat ' + candidate, image)
            if 'Type: regular' in stat:
                found.append(candidate)
        if len(found) != 1:
            if not found:
                result['components'].setdefault(name, {})[flavor] = {'present': False}
                continue
            raise ValueError((flavor, name, found))
        target = dest / (name + extension)
        if not target.exists():
            run('debugfs', '-R', f'dump {found[0]} {target}', image)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        expected = components.get('system:' + found[0]) if flavor == 'arm32' else None
        if name == 'services' and flavor == 'arm32':
            expected = 'd291bfeadf578ae923c4dc11577a78724df78e7b54503ebf2e3f80da0d916c11'
        if expected and digest != expected:
            raise ValueError('Pinned ARM32 component mismatch: ' + name)
        with zipfile.ZipFile(target) as archive:
            libs = [x for x in archive.namelist() if x.startswith('lib/') and x.endswith('.so')]
            dex = [x for x in archive.namelist() if x.endswith('.dex')]
            markers = sorted(set(x.decode() for d in dex for x in
                __import__('re').findall(rb'Rgsp[A-Za-z0-9_$]+', archive.read(d))))
        item = {'present': True, 'path': found[0], 'bytes': target.stat().st_size,
                'sha256': digest, 'embedded_native_libraries': libs, 'rgsp_dex_markers': markers}
        if extension == '.apk':
            signature = run(java, '-Xmx256m', '-jar', sdk / 'lib/apksigner.jar', 'verify',
                            '--print-certs', '--min-sdk-version', '29', target)
            item['signature'] = signature
            manifest = run(sdk / 'bin/aapt', 'dump', 'xmltree', target, 'AndroidManifest.xml')
            (dest / (name + '.manifest.txt')).write_text(manifest)
            item['manifest_header'] = manifest.splitlines()[:14]
        result['components'].setdefault(name, {})[flavor] = item
        print('COMPONENT', flavor, name, digest[:12], flush=True)
(OUT / 'component-comparison.json').write_text(json.dumps(result, indent=2) + '\n')
print('PARITY_INPUT_COMPARISON_COMPLETE', flush=True)

"""Offline ELF closure and Binder-interface comparison; never executes vold."""
import hashlib
import json
from pathlib import Path
import posixpath
import re
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained, debug, dump
from dex_port import DexPort, methods
constrained()
ROOT = Path('/home/lpf/h700-dualabi-parity-20261101')
OUT = REPO / 'out/dualabi-parity-20261101'
WORK = ROOT / 'vold-audit-v1'
port = DexPort(REPO, WORK)
native = Path('/home/lpf/h700-android10/android')
product = Path('/home/lpf/h700-dualabi-prototype-20261030/out/target/product/rgsp64proto')
image = Path('/home/lpf/h700-dualabi-test1-20261031/system.candidate.raw')
binary = WORK / 'vold'
shutil.copyfile(product / 'system/bin/vold', binary)
assert binary.read_bytes()[:5] == b'\x7fELF\x02'
assert int.from_bytes(binary.read_bytes()[18:20], 'little') == 183
report = {'vold_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
          'native_elf64': True, 'daemon_executed': False, 'libraries': {}, 'errors': []}

def needed(file):
    text = subprocess.check_output(['readelf', '-d', str(file)], text=True)
    return re.findall(r'Shared library: \[(.*?)\]', text)

def resolve(inside):
    for attempt in range(10):
        if inside.startswith('/apex/com.android.runtime/'):
            inside = '/system/apex/com.android.runtime.release/' + inside.split('/apex/com.android.runtime/', 1)[1]
        record = debug(image, 'stat ' + inside)
        if 'Type: regular' in record:
            return inside
        link = re.search(r'Fast link dest: "([^"]+)"', record)
        if not link:
            return None
        inside = posixpath.normpath(link[1] if link[1].startswith('/') else posixpath.dirname(inside) + '/' + link[1])
    raise ValueError('Input symlink loop')

queue = needed(binary)
files = {'vold': binary}
directories = ['/system/lib64', '/system/lib64/bootstrap',
               '/system/apex/com.android.runtime.release/lib64/bionic',
               '/system/apex/com.android.runtime.release/lib64', '/system/lib64/vndk-sp-29', '/system/lib64/vndk-29']
while queue:
    name = queue.pop(0)
    if name in files:
        continue
    if '/' in name or '..' in name:
        raise ValueError('Unsafe DT_NEEDED')
    inside = next((p for directory in directories if (p := resolve(directory + '/' + name))), None)
    target = WORK / name
    if inside:
        dump(image, inside, target)
        source = 'gsi:' + inside
    else:
        candidate = product / 'system/lib64' / name
        if not candidate.is_file() or candidate.is_symlink():
            report['errors'].append('Missing library: ' + name)
            continue
        shutil.copyfile(candidate, target)
        source = 'new_missing_library:' + str(candidate.relative_to(product))
    header = target.read_bytes()[:64]
    assert header[:5] == b'\x7fELF\x02' and int.from_bytes(header[18:20], 'little') == 183, name
    files[name] = target
    dependencies = needed(target)
    queue += dependencies
    report['libraries'][name] = {'source': source, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                                'needed': dependencies}

exports, undefined = set(), {}
for name, file in files.items():
    symbols = subprocess.check_output(['readelf', '--dyn-syms', '--wide', str(file)], text=True)
    undefined[name] = []
    for line in symbols.splitlines():
        fields = line.split()
        if len(fields) < 8 or not fields[0].rstrip(':').isdigit():
            continue
        symbol = fields[7]
        if fields[6] == 'UND':
            if fields[4] != 'WEAK' and symbol:
                undefined[name].append(symbol)
        elif fields[4] in ('GLOBAL', 'WEAK') and fields[5] in ('DEFAULT', 'PROTECTED'):
            exports.add(symbol.replace('@@', '@'))
            if '@@' in symbol or '@' not in symbol:
                exports.add(symbol.split('@')[0])
missing = {name: sorted(set(values) - exports) for name, values in undefined.items() if set(values) - exports}
report['unresolved_dynamic_symbols'] = missing
if missing:
    report['errors'].append('ELF symbols unresolved against proposed GSI closure')

types = [f'android/os/{name}{suffix}' for name in ('IVold', 'IVoldListener', 'IVoldTaskListener') for suffix in ('', '$Stub')]
old = port.load(ROOT / 'inputs-arm32/framework.jar', types, 'arm32')
gsi = port.load(ROOT / 'inputs-gsi/framework.jar', types, 'gsi')
protocols = {}
for name in types:
    if name.endswith('$Stub'):
        pattern = r'^\.field .* (TRANSACTION_\w+):I = (\S+)'
        before, after = dict(re.findall(pattern, old[name], re.M)), dict(re.findall(pattern, gsi[name], re.M))
    else:
        before = sorted(signature for signature, body in methods(old[name]).items() if ' abstract ' in body.splitlines()[0])
        after = sorted(signature for signature, body in methods(gsi[name]).items() if ' abstract ' in body.splitlines()[0])
    protocols[name] = before == after
    if before != after:
        report['errors'].append('Binder protocol differs: ' + name)
        report.setdefault('protocol_differences', {})[name] = {'arm32': before, 'gsi': after}
report['binder_protocols_match'] = protocols
report['binder_aidl_source_sha256'] = {name: hashlib.sha256((native / f'system/vold/binder/android/os/{name}.aidl').read_bytes()).hexdigest()
    for name in ('IVold', 'IVoldListener', 'IVoldTaskListener')}
report['offline_checks_passed'] = not report['errors']
report['runtime_accepted'] = False
(OUT / 'vold-audit-v1.json').write_text(json.dumps(report, indent=2) + '\n')
print('VOLD_ELF_CLOSURE', len(files), 'MISSING', missing, 'PROTOCOLS', protocols, flush=True)
if report['errors']:
    raise ValueError('; '.join(report['errors']))

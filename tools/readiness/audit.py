"""Audit the ARM64 light service against pinned Test2a files, without running it."""
import hashlib
import json
from pathlib import Path
import posixpath
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained, debug, dump, sha
constrained()
out = REPO / 'out/rg34xxsp-readiness-20261102'
build = json.loads((out / 'latest-build.json').read_text())
work = Path(build['work']) / 'audit'
work.mkdir(exist_ok=False)
native_light = Path('/home/lpf/h700-android10/android/device/roc/rgsp/H700Light')
product = Path('/home/lpf/h700-dualabi-prototype-20261030/out/target/product/rgsp64proto')
binary = product / 'vendor/bin/hw/android.hardware.light@2.0-service.h700'
candidate = work / binary.name
shutil.copy2(binary, candidate)
snapshot = work / 'source'
snapshot.mkdir()
for name, digest in build['source'].items():
    assert sha(native_light / name) == digest
    shutil.copy2(native_light / name, snapshot / name)
# The inherited vendor policy grants open/read/ioctl, not write access.
# Refuse an O_RDWR prototype even on a permissive development system.
assert 'O_RDONLY | O_CLOEXEC' in (snapshot / 'service.cpp').read_text(), 'Use the existing read/open/ioctl policy'
images = {
    'system': Path('/home/lpf/h700-dualabi-parity-20261101/defaults-stage-v1/system.candidate.raw'),
    'vendor': Path('/home/lpf/h700-dualabi-parity-20261101/final-stage-v2/vendor.candidate.raw'),
}
parentfile = REPO / 'docs/baselines/rg34xxsp-arm64-defaults-test2a-20261101/components-lock.json'
parent = json.loads(parentfile.read_text())
for name, image in images.items():
    assert image.is_file() and not image.is_symlink()
    assert image.stat().st_size == parent[name]['bytes']
    print('VERIFY_PINNED_PARENT', name, flush=True)
    assert sha(image) == parent[name]['sha256']

def resolve(partition, inside):
    for _ in range(12):
        if inside.startswith('/apex/com.android.runtime/'):
            inside = '/system/apex/com.android.runtime.release/' + inside.split('/apex/com.android.runtime/')[1]
            partition = 'system'
        info = debug(images[partition], 'stat ' + inside)
        if 'Type: regular' in info:
            return partition, inside
        link = re.search(r'Fast link dest: "([^"]+)"', info)
        if not link:
            return None
        inside = posixpath.normpath(link[1] if link[1].startswith('/') else posixpath.dirname(inside) + '/' + link[1])
    raise ValueError('Symlink cycle')

def needed(path):
    return re.findall(r'Shared library: \[(.*?)\]', subprocess.check_output(['readelf', '-d', str(path)], text=True))

# Follow the parent's vendor/system/VNDK links instead of guessing a short
# LLNDK list or flattening system-private dependencies into the vendor namespace.
ld = dump(images['system'], '/system/etc/ld.config.29.txt', work / 'ld.config.29.txt').read_text()
section = re.search(r'^\[vendor\]\s*$(.*?)(?=^\[|\Z)', ld, re.M | re.S)[1]
links = {}
for namespace, destination, value in re.findall(
        r'^namespace\.(default|vndk)\.link\.(system|vndk)\.shared_libs\s*\+?=\s*(.*)$', section, re.M):
    links.setdefault((namespace, destination), set()).update(value.strip().split(':'))
assert ('default', 'system') in links and ('default', 'vndk') in links
folders = {
    'vendor': [('vendor', '/lib64')],
    'vndk': [('system', '/system/lib64/vndk-sp-29'), ('system', '/system/lib64/vndk-29')],
    'system': [('system', '/system/lib64'), ('system', '/system/lib64/bootstrap'),
               ('system', '/system/apex/com.android.runtime.release/lib64/bionic')],
}
provider_cache = {}
added = {}

def provider(namespace, name):
    assert '/' not in name and '..' not in name
    cache_key = (namespace, name)
    if cache_key in provider_cache: return provider_cache[cache_key]
    result = next(((namespace, *resolved) for partition, directory in folders[namespace]
                   if (resolved := resolve(partition, directory + '/' + name))), None)
    if result is None and namespace != 'system':
        owner = 'default' if namespace == 'vendor' else 'vndk'
        for destination in ('system', 'vndk'):
            if destination == namespace: continue
            if name in links.get((owner, destination), set()):
                result = provider(destination, name)
                break
    if result is None and namespace == 'vendor' and name == 'android.hardware.light@2.0.so':
        supplied = product / 'vendor/lib64' / name
        assert supplied.is_file() and not supplied.is_symlink()
        result = ('vendor', 'new-interface', str(supplied))
    assert result is not None, 'Unresolved namespace dependency: ' + str(cache_key)
    provider_cache[cache_key] = result
    return result

files = {'vendor:service': candidate}
sources = {}
graph = {}
queue = ['vendor:service']
while queue:
    key = queue.pop(0)
    namespace = key.split(':', 1)[0]
    graph[key] = []
    for name in needed(files[key]):
        owner, partition, inside = provider(namespace, name)
        dependency = owner + ':' + name
        graph[key].append(dependency)
        if dependency in files: continue
        target = work / (owner + '-' + name)
        if partition == 'new-interface':
            shutil.copy2(inside, target)
            added['/lib64/' + name] = {'path': str(target), 'sha256': sha(target)}
        else:
            dump(images[partition], inside, target)
        sources[dependency] = owner + ':' + partition + ':' + inside
        files[dependency] = target
        queue.append(dependency)

exports, undefined = {}, {}
for name, file in files.items():
    data = file.read_bytes()
    assert data[:5] == b'\x7fELF\x02' and int.from_bytes(data[18:20], 'little') == 183, name
    symbols = subprocess.check_output(['readelf', '--dyn-syms', '--wide', str(file)], text=True)
    undefined[name], exports[name] = [], set()
    for line in symbols.splitlines():
        fields = line.split()
        if len(fields) < 8 or not fields[0].rstrip(':').isdigit(): continue
        symbol = fields[7]
        if fields[6] == 'UND':
            if fields[4] != 'WEAK': undefined[name].append(symbol)
        elif fields[4] in ('GLOBAL', 'WEAK') and fields[5] in ('DEFAULT', 'PROTECTED'):
            exports[name].add(symbol.replace('@@', '@'))
            if '@@' in symbol or '@' not in symbol: exports[name].add(symbol.split('@')[0])
missing = {}
for key in files:
    pending, seen, visible = [key], set(), set()
    while pending:
        item = pending.pop()
        if item in seen: continue
        seen.add(item)
        visible.update(exports[item])
        pending.extend(graph[item])
    unresolved = sorted(set(undefined[key]) - visible)
    if unresolved: missing[key] = unresolved
source = REPO / 'android/h700-android10/device/roc/rgsp/H700Light'
fragment = ET.fromstring((source / 'h700-light.xml').read_bytes())
assert fragment.findtext('hal/name') == 'android.hardware.light'
assert fragment.findtext('hal/transport') == 'hwbinder'
assert fragment.findtext('hal/interface/name') == 'ILight'
assert fragment.findtext('hal/interface/instance') == 'default'
manifest = ET.fromstring(debug(images['vendor'], 'cat /etc/vintf/manifest.xml'))
assert not any(h.findtext('name') == 'android.hardware.light' for h in manifest.findall('hal'))
contexts = debug(images['vendor'], 'cat /etc/selinux/vendor_file_contexts')
assert 'hal_light_default_exec' in contexts
policy = debug(images['vendor'], 'cat /etc/selinux/vendor_sepolicy.cil')
assert '(type hal_light_default_exec)' in policy
assert '(allow hal_light_default graphics_device_29_0 (chr_file (ioctl read open)))' in policy
rc = (source / 'h700-light.rc').read_text()
assert 'group system graphics' in rc and 'user system' in rc
report = {'parent_components_sha256': sha(parentfile), 'parent_images': parent,
    'source': build['source'], 'work': str(work), 'binary': str(candidate), 'binary_sha256': sha(candidate),
    'elf_class': 64, 'libraries': {n: {'source': sources[n], 'sha256': sha(files[n]), 'needed': needed(files[n])} for n in sources},
    'dependency_graph': graph, 'ld_config_sha256': sha(work / 'ld.config.29.txt'),
    'added_libraries': added, 'unresolved_symbols': missing, 'host_tests': build['host_tests'],
    'vintf_fragment_valid': True, 'existing_light_conflict': False,
    'existing_light_exec_label_found': True, 'offline_passed': not missing,
    'existing_vendor_read_open_ioctl_rule_found': True, 'display_open_read_only': True,
    'daemon_executed': False, 'device_installed': False, 'physical_brightness_accepted': False}
(out / ('audit-' + Path(build['work']).name + '.json')).write_text(json.dumps(report, indent=2) + '\n')
assert not missing, missing
(out / 'light-candidate.json').write_text(json.dumps(report, indent=2) + '\n')
print('LIGHT_ELF64_CLOSURE_AND_INPUTS_PASS', len(files), flush=True)

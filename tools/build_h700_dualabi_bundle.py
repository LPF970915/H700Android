#!/usr/bin/env python3
"""Pack self-built ELF64 window dependencies in a new data-side rootfs.

No device access, mount, image writes, or fallback to a shipping system library.
The complete AOSP product and an installed ARM64 APK remain separate gates.
"""
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
from package_h700_v6a import constrained, sha

constrained()
repo = Path(__file__).resolve().parents[1]
native = Path('/home/lpf/h700-android10/android')
product = Path('/home/lpf/h700-dualabi-prototype-20261030/out/target/product/rgsp64proto')
out = repo / 'out/dualabi-prototype-20261030'
stage = out / 'window-bundle'
stage.mkdir()  # A failed or completed stage must be retained for inspection.
rootfs = stage / 'rootfs'
for directory in ['system/bin', 'system/etc', 'system/lib64', 'vendor/lib64/hw',
                  'vendor/lib64/egl', 'apex/com.android.runtime/bin',
                  'apex/com.android.runtime/lib64/bionic', 'proc', 'sys', 'dev/__properties__']:
    (rootfs / directory).mkdir(parents=True, exist_ok=True)

def resolve(p):
    seen = set()
    while p.is_symlink():
        if p in seen: raise ValueError('Symlink cycle')
        seen.add(p)
        link = os.readlink(p)
        if link.startswith('/apex/'):
            p = product / 'system' / link.lstrip('/')
        elif link.startswith('/'):
            p = product / link.lstrip('/')
        else: p = p.parent / link
    if not p.is_file() or not p.resolve().is_relative_to(product.resolve()):
        raise ValueError('Missing or out-of-product input: ' + str(p))
    return p

files = {}
def copy(source, destination):
    source = resolve(source)
    if source.read_bytes()[:5] != b'\x7fELF\x02': raise ValueError('Not ELF64: ' + str(source))
    info = subprocess.check_output(['readelf', '-h', str(source)], text=True)
    if 'AArch64' not in info: raise ValueError('Not AArch64')
    target = rootfs / destination
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    if destination.endswith('linker64') or destination.endswith('h700_window_probe64'): target.chmod(0o755)
    needed = re.findall(r'Shared library: \[(.*?)\]', subprocess.check_output(['readelf', '-d', str(target)], text=True))
    files[destination] = {'source': source.relative_to(product).as_posix(), 'sha256': sha(target), 'needed': needed}
    return needed

directories = ['system/lib64/bootstrap', 'system/apex/com.android.runtime/lib64/bionic',
               'system/apex/com.android.runtime.release/lib64/bionic', 'system/lib64',
               'system/lib64/vndk-sp-29', 'system/lib64/vndk-29', 'vendor/lib64']
def find(name):
    if '/' in name or '..' in name: raise ValueError('Invalid DT_NEEDED')
    for directory in directories:
        p = product / directory / name
        try: return resolve(p)
        except ValueError: pass
    raise ValueError('Missing self-built dependency: ' + name)

loader = product / 'system/bin/bootstrap/linker64'
if not loader.exists(): loader = product / 'system/bin/linker64'
queue = copy(loader, 'system/bin/linker64')
copy(loader, 'apex/com.android.runtime/bin/linker64')
queue += copy(product / 'system/bin/h700_window_probe64', 'system/bin/h700_window_probe64')
queue += copy(product / 'vendor/lib64/hw/gralloc.h700proto.so', 'vendor/lib64/hw/gralloc.cupid.so')
copy(product / 'vendor/lib64/hw/gralloc.h700proto.so', 'vendor/lib64/hw/gralloc.h700proto.so')
mapper = 'android.hardware.graphics.mapper@2.0-impl-2.1.so'
queue += copy(product / 'vendor/lib64/hw' / mapper, 'vendor/lib64/hw/' + mapper)
mali = native / 'hardware/aw/gpu/mali-bifrost/mali-g31/arm64/lib64/libGLES_mali.so'
if sha(mali) != '03333d495e3566c7d85ca2e000da569a16ce8f022ea25c0ea61950c891d5c7f8':
    raise ValueError('Candidate Mali changed')
shutil.copyfile(mali, rootfs / 'vendor/lib64/egl/libGLES_mali.so')
needed = re.findall(r'Shared library: \[(.*?)\]', subprocess.check_output(['readelf', '-d', str(mali)], text=True))
files['vendor/lib64/egl/libGLES_mali.so'] = {'source': 'BSP arm64 Mali', 'sha256': sha(mali), 'needed': needed}
queue += needed
done = set()
while queue:
    name = queue.pop(0)
    if name in done or name == 'ld-android.so': continue  # The running linker supplies ld-android.
    done.add(name)
    queue += copy(find(name), 'system/lib64/' + name)
for name in ['libc.so', 'libdl.so', 'libm.so']:
    copy(find(name), 'apex/com.android.runtime/lib64/bionic/' + name)
(rootfs / 'system/etc/ld.config.txt').write_text(
    'dir.default = /system/bin\n[default]\nnamespace.default.isolated = false\n'
    'namespace.default.search.paths = /system/lib64:/vendor/lib64:/vendor/lib64/hw:/vendor/lib64/egl\n')
for name in ['null','zero','urandom','random','ashmem','binder','hwbinder','vndbinder','mali0','ion']:
    (rootfs / 'dev' / name).touch()
clang = native / 'prebuilts/clang/host/linux-x86/clang-r353983c/bin/clang.real'
subprocess.run([str(clang), '--target=aarch64-linux-android29', '-fuse-ld=lld',
    '-nostdlib', '-static', '-fno-builtin', '-Wl,-e,_start',
    '-DROOTFS_PREFIX="/data/local/tmp/h700-dualabi-prototype-20261030/rootfs/"',
    str(repo / 'tools/arm64_probe/mount_guard.c'), '-o', str(stage / 'mount64')], check=True)
shutil.copyfile(repo / 'tools/arm64_probe/dualabi_namespace_run.sh', stage / 'namespace-run.sh')
(stage / 'bundle-lock.json').write_text(json.dumps({'files': files,
    'mount64_sha256': sha(stage / 'mount64'), 'namespace_sha256': sha(stage / 'namespace-run.sh'),
    'payload_sha256': {p.relative_to(stage).as_posix(): sha(p) for p in sorted(stage.rglob('*')) if p.is_file()},
}, indent=2) + '\n')
print('DUAL_ABI_WINDOW_BUNDLE_READY', len(files), flush=True)

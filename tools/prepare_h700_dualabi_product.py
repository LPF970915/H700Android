#!/usr/bin/env python3
"""Add only the separate prototype product. Never edit the ARM32 product."""
from pathlib import Path
import hashlib
import json
import shutil
from package_h700_v6a import constrained

constrained()
repo = Path(__file__).resolve().parents[1]
native = Path('/home/lpf/h700-android10/android')
source = repo / 'android/h700-android10/device/roc/rgsp64proto'
destination = native / 'device/roc/rgsp64proto'
out = repo / 'out/dualabi-prototype-20261030'
out.mkdir(exist_ok=True)

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

# Preserve byte identities of all existing product inputs and critical source.
protected = [native / p for p in (
    'device/roc/rgsp/BoardConfig.mk', 'device/roc/rgsp/h700_rgsp.mk',
    'device/roc/h700-common/BoardConfigCommon.mk', 'device/roc/h700-common/device.mk',
    'hardware/aw/gpu/mali-bifrost/gralloc/src/mali_gralloc_bufferallocation.cpp')]
before = {str(p.relative_to(native)): digest(p) for p in protected}
# Keep the small upstream Gralloc fork local to this product. Only its module
# name and four printf argument types change. Do not edit the original BSP.
upstream = native / 'hardware/aw/gpu/mali-bifrost/gralloc'
variant = destination / 'gralloc-variant'
upstream_lock = {}
variant_lock = {}
for p in sorted(upstream.rglob('*')):
    if p.is_dir(): continue
    if p.is_symlink() or not p.is_file(): raise ValueError('Unexpected Gralloc input')
    relative = p.relative_to(upstream)
    content = p.read_bytes()
    upstream_lock[relative.as_posix()] = digest(p)
    if relative.as_posix() == 'src/mali_gralloc_bufferallocation.cpp':
        substitutions = {
            b'ALOGD("sunxi format do not run here %lld",bufDescriptor->hal_format);':
            b'ALOGD("sunxi format do not run here %llu",static_cast<unsigned long long>(bufDescriptor->hal_format));',
            b'fmt:%d if:%lld af:%lld usg:%llx fg:%08x': b'fmt:%d if:%llu af:%llu usg:%llx fg:%08x',
            b'hnd->format, hnd->internal_format, hnd->alloc_format, usage, hnd->flags);':
            b'hnd->format, static_cast<unsigned long long>(hnd->internal_format), static_cast<unsigned long long>(hnd->alloc_format), static_cast<unsigned long long>(usage), hnd->flags);',
        }
        for old, new in substitutions.items():
            if content.count(old) != 1: raise ValueError('Unexpected Gralloc source format')
            content = content.replace(old, new)
    if relative.as_posix() == 'src/Android.mk':
        old = b'LOCAL_MODULE := gralloc.$(TARGET_BOARD_PLATFORM)'
        if content.count(old) != 1: raise ValueError('Unexpected upstream module name')
        content = content.replace(old, b'LOCAL_MODULE := gralloc.h700proto')
    target = variant / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() != content:
        backup = out / 'source-backups/gralloc-variant' / (relative.as_posix() + '.' + digest(target))
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists(): shutil.copyfile(target, backup)
    if not target.exists() or target.read_bytes() != content: target.write_bytes(content)
    variant_lock[relative.as_posix()] = digest(target)
if upstream_lock != {p.relative_to(upstream).as_posix(): digest(p) for p in sorted(upstream.rglob('*')) if p.is_file()}:
    raise RuntimeError('Original Gralloc tree changed')
(out / 'gralloc-variant-inputs.json').write_text(json.dumps({
    'upstream_unchanged': upstream_lock, 'variant': variant_lock,
    'module': 'gralloc.h700proto', 'logging_only_source_fix': True,
}, indent=2) + '\n')
(destination / 'configs').mkdir(exist_ok=True)  # Optional vendor efuse search directory.
for p in sorted(source.rglob('*')):
    if p.is_dir(): continue
    if not p.is_file() or p.is_symlink(): raise ValueError('Unexpected prototype input')
    relative = p.relative_to(source)
    target = destination / relative
    if target.exists() and target.read_bytes() == p.read_bytes():
        continue  # Preserve mtimes, so an unchanged retry can reuse the graph.
    if target.exists() and target.read_bytes() != p.read_bytes():
        backup = out / 'source-backups' / (relative.as_posix() + '.' + digest(target))
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists(): shutil.copyfile(target, backup)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(p, target)
if before != {str(p.relative_to(native)): digest(p) for p in protected}:
    raise RuntimeError('Protected source changed')
(out / 'product-inputs.json').write_text(json.dumps({
    'product': 'h700_rgsp64proto-eng',
    'out_dir': '/home/lpf/h700-dualabi-prototype-20261030/out',
    'arm32_inputs_unchanged': before,
    'prototype': {p.relative_to(source).as_posix(): digest(p) for p in sorted(source.rglob('*')) if p.is_file()},
}, indent=2) + '\n')
print('DUAL_ABI_PRODUCT_PREPARED', flush=True)

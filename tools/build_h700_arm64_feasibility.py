#!/usr/bin/env python3
"""Small offline ARM64 audit and syscall-only probe, under the fixed build cap."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

from package_h700_v6a import constrained

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('/home/lpf/h700-android10/android')
OUT = ROOT / 'out/arm64-feasibility-20261030'


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT)


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    constrained()
    OUT.mkdir(exist_ok=True)
    gpu = SOURCE / 'hardware/aw/gpu/mali-bifrost/mali-g31'
    libraries = []
    for relative in ['arm/lib/libGLES_mali.so', 'arm64/lib/libGLES_mali.so', 'arm64/lib64/libGLES_mali.so']:
        p = gpu / relative
        dynamic = run('readelf', '-d', str(p))
        symbols = run('readelf', '--dyn-syms', '--wide', str(p))
        strings = run('strings', str(p))
        libraries.append({'file': relative, 'sha256': sha(p), 'bytes': p.stat().st_size,
                          'elf_class': 64 if p.read_bytes()[4] == 2 else 32,
                          'needed': re.findall(r'Shared library: \[(.*?)\]', dynamic),
                          'egl_exports': [s for s in ['eglGetDisplay', 'eglInitialize', 'eglCreateContext', 'eglCreatePbufferSurface', 'eglMakeCurrent'] if s in symbols],
                          'driver_version_strings': sorted(set(re.findall(r'[^\n]{0,45}r\d+p\d+[^\n]{0,70}', strings)))[:20]})
    # Build records are evidence about source configuration, not successful HAL builds.
    config = {}
    for rel in ['hardware/aw/gpu/mali-bifrost/gralloc/Android.mk',
                'hardware/aw/gpu/mali-bifrost/gralloc/src/Android.mk',
                'hardware/aw/audio/hal/Android.mk',
                'hardware/aw/hwc2/Android.mk', 'hardware/aw/hwc2/Android.bp',
                'hardware/aw/audio/Android.mk', 'build/target/product/core_64_bit.mk',
                'system/core/rootdir/init.zygote64_32.rc']:
        p = SOURCE / rel
        if p.is_file():
            content = p.read_text(errors='replace')
            config[rel] = {'sha256': sha(p), 'selected_lines': [s for s in content.splitlines() if any(k in s for k in ['MULTILIB', 'compile_multilib', '32', '64', 'LOCAL_SHARED_LIBRARIES', 'LOCAL_SRC_FILES'])][:70]}
    clang = SOURCE / 'prebuilts/clang/host/linux-x86/clang-r353983c/bin/clang.real'
    binary = OUT / 'h700-kernel64-probe'
    if binary.exists():
        raise ValueError('Probe output already exists; retain previous evidence')
    args = [str(clang), '--target=aarch64-linux-android29', '-fuse-ld=lld', '-nostdlib', '-static',
            '-Wl,-e,_start', '-Wl,--build-id=sha1', str(ROOT / 'tools/arm64_probe/kernel64.S'), '-o', str(binary)]
    subprocess.run(args, check=True)
    header = run('readelf', '-h', str(binary))
    program = run('readelf', '-l', str(binary))
    if 'AArch64' not in header or 'ELF64' not in header or 'INTERP' in program:
        raise ValueError('Expected standalone static ELF64 AArch64 probe')
    (OUT / 'probe-readelf.txt').write_text(header + program)
    report = {'libraries': libraries, 'source_configuration': config,
              'probe': {'sha256': sha(binary), 'bytes': binary.stat().st_size, 'elf_class': 64,
                        'machine': 'AArch64', 'dynamic_interpreter': False,
                        'scope': 'mmap one page, 64-bit load/store, munmap, stdout, exit only'},
              'compiler': run(str(clang), '--version').splitlines()[0],
              'aosp_system_build_started': False, 'device_driver_modified': False,
              'arm64_android_apps_verified': False, 'arm64_graphics_runtime_verified': False}
    (OUT / 'offline-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print('ARM64_AUDIT_AND_STATIC_PROBE_BUILT', flush=True)


if __name__ == '__main__':
    main()

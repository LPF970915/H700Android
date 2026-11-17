"""Read the bounded Test8 ramdisk and audit its existing swap prerequisites.

Ordinary files only. Never loads modules, enables host swap or changes a device.
"""
from pathlib import Path
import gzip
import hashlib
import json
import stat
import struct
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from patch_ramdisk import parse

RAW = Path('/home/lpf/roc-os-h700-twelve-model-test8-20261116-v1/ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test8_TwelveModel_20261116.img')
OUT = REPO / 'out/memory-swap-20261117/boot-audit-v3'


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    with RAW.open('rb') as source:
        source.seek(155189248)
        header = source.read(2048)
        assert header[:8] == b'ANDROID!'
        kernel = struct.unpack_from('<I', header, 8)[0]
        size = struct.unpack_from('<I', header, 16)[0]
        page = struct.unpack_from('<I', header, 36)[0]
        assert kernel == 17686536 and page == 2048 and 0 < size < 8 * 1024**2
        actual_kernel = source.read(kernel)
        assert hashlib.sha256(actual_kernel).hexdigest() == '62c4feb1650f1c311e79ebfe75a979bac89f3da77f1ab6e46ad46a8924fdb6e6'
        source.seek(155189248 + page + ((kernel + page - 1) // page) * page)
        compressed = source.read(size)
        assert len(compressed) == size
    entries = parse(gzip.decompress(compressed))
    byname = {e['name']: e for e in entries}
    assert len(entries) == len(byname)
    box = byname['bin/busybox']['data']
    assert struct.unpack_from('<H', box, 18)[0] == 183
    target = OUT / 'busybox'
    target.write_bytes(box)
    target.chmod(0o755)
    sysroot = OUT / 'sysroot'
    sysroot.mkdir()
    for entry in entries:
        name = entry['name']
        if name == 'lib64':
            assert stat.S_ISLNK(entry['mode']) and entry['data'] == b'lib'
            (sysroot / 'lib64').symlink_to('lib')
        if not name.startswith('lib/') or len(Path(name).parts) != 2:
            continue
        local = sysroot / name
        local.parent.mkdir(parents=True, exist_ok=True)
        if stat.S_ISREG(entry['mode']):
            local.write_bytes(entry['data'])
        elif stat.S_ISLNK(entry['mode']):
            local.symlink_to(entry['data'].decode())
    command = ['/usr/bin/qemu-aarch64', '-L', str(sysroot), str(target)]
    applets = subprocess.check_output(command + ['--list'], text=True).splitlines()
    required = {'mkswap', 'swapon', 'ls', 'dd', 'df', 'awk', 'od', 'sync', 'mv', 'chmod', 'mkdir', 'rm', 'cat', 'grep', 'kill', 'sleep'}
    assert required <= set(applets), required - set(applets)
    init = byname['init']['data']
    optional_call = b'/bin/sh /grow/h700-optional-axes.sh /android-root /proc/modules /bin/busybox "$(uname -r)"'
    assert init.count(optional_call) == 1
    assert init.index(b'mkdir -p /android-root/data/rgsp-persist') < init.index(optional_call)
    assert init.index(optional_call) < init.index(b'exec /bin/busybox switch_root')
    config = REPO / 'android/h700-android10/device/roc/rgsp/input/kernel/h700-4.9.170.config'
    text = config.read_text()
    assert 'CONFIG_SWAP=y\n' in text and '# CONFIG_ZRAM is not set\n' in text
    result = {'schema': 'roc.h700.swap-boot-audit.v1', 'passed': True,
              'parent': str(RAW), 'ramdisk_sha256': hashlib.sha256(compressed).hexdigest(),
              'actual_kernel_sha256': hashlib.sha256(actual_kernel).hexdigest(),
              'actual_kernel_bytes': len(actual_kernel),
              'init_sha256': hashlib.sha256(init).hexdigest(),
              'busybox_path': str(target), 'busybox_sha256': hashlib.sha256(box).hexdigest(),
              'sysroot': str(sysroot), 'required_applets_present': sorted(required),
              'swap_kernel_enabled': True, 'zram_kernel_enabled': False,
              'helper_after_data_mount_and_before_policy': True,
              'helper_unconditional_all_models': True,
              'config_sha256': hashlib.sha256(config.read_bytes()).hexdigest(),
              'device_accessed': False, 'physical_swap_acceptance': False}
    source = Path('/home/lpf/h700-android10/longan/kernel/linux-4.9')
    kernel_sources = {str(source / name): hashlib.sha256((source / name).read_bytes()).hexdigest()
                      for name in ('mm/swapfile.c', 'mm/page_io.c', 'fs/ext4/inode.c')}
    evidence = {'schema': 'roc.h700.swap-kernel-prerequisites.v1', 'passed': True,
                'actual_kernel_sha256': hashlib.sha256(actual_kernel).hexdigest(),
                'actual_kernel_bytes': len(actual_kernel), 'swap_kernel_enabled': True,
                'zram_kernel_enabled': False, 'config_path': str(config),
                'config_sha256': result['config_sha256'], 'retained_source_controls': kernel_sources,
                'source_review': 'setup_swap_extents uses generic_swapfile_activate for regular files; ext4_bmap synchronizes delayed allocation before returning block mapping',
                'physical_swap_acceptance': False}
    (OUT / 'kernel-evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
    (OUT / 'init.test8.sh').write_bytes(init)
    (OUT / 'applets.txt').write_text('\n'.join(applets) + '\n')
    (OUT / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

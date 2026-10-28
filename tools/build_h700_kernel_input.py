"""Prepare the matching BSP outside its sources, under the low-pressure wrapper.

This deliberately does not load modules or bypass MODVERSIONS checks. Local
export CRCs must be compared with the running kernel before any deployment.
"""
from pathlib import Path
import hashlib
import os
import shutil
import subprocess
import tarfile

REPO = Path(__file__).resolve().parents[1]
LONGAN = Path('/home/lpf/h700-android10/longan')
WORK = Path('/home/lpf/h700-input-kbuild')
DELIVERY = REPO / 'out/rg34xxsp-dev-20261028'


def run(*args, **kwargs):
    print('RUN', *map(str, args), flush=True)
    subprocess.run(list(map(str, args)), check=True, **kwargs)


def main():
    cg = Path('/sys/fs/cgroup') / Path('/proc/self/cgroup').read_text().strip().split('::')[-1].lstrip('/')
    quota, period = (cg / 'cpu.max').read_text().split()
    assert quota != 'max' and int(quota) <= int(period)
    assert int((cg / 'memory.max').read_text()) <= 6442450944
    assert os.sched_getaffinity(0) <= {0, 1} and os.getpriority(os.PRIO_PROCESS, 0) == 19
    WORK.mkdir(exist_ok=True)
    toolchain_name = 'gcc-linaro-5.3.1-2016.05-x86_64_aarch64-linux-gnu'
    toolchain = WORK / toolchain_name
    if not toolchain.is_dir():
        archive = LONGAN / 'build/toolchain' / (toolchain_name + '.tar.xz')
        with tarfile.open(archive) as source:
            source.extractall(WORK, filter='data')
    config = WORK / '.config'
    source_config = REPO / 'android/h700-android10/device/roc/rgsp/input/kernel/h700-4.9.170.config'
    assert hashlib.sha256(source_config.read_bytes()).hexdigest() == '565948300ae2d0f68a8ec85a18be033cde06ad4c46a988bebf708b9ce35cb119'
    if not config.exists():
        config.write_bytes(source_config.read_bytes())
    prefix = toolchain / 'bin/aarch64-linux-gnu-'
    run(str(prefix) + 'gcc', '--version')
    make = ['make', '-j1', '-C', LONGAN / 'kernel/linux-4.9', 'O=' + str(WORK),
            'ARCH=arm64', 'CROSS_COMPILE=' + str(prefix),
            'HOSTCFLAGS=-O2 -fcommon']
    run(*make, 'olddefconfig', 'prepare', 'scripts', 'modules_prepare')
    # Build just the translation units that export APIs used by this add-on.
    # Their genksyms output proves the local headers' ABI; it is never forced.
    objects = ['drivers/input/input.o', 'drivers/gpio/gpiolib.o',
               'drivers/gpio/gpiolib-legacy.o', 'kernel/workqueue.o',
               'kernel/module.o', 'drivers/of/base.o', 'kernel/printk/printk.o',
               'mm/page_alloc.o', 'arch/arm64/kernel/arm64ksyms.o',
               'arch/arm64/mm/ioremap.o', 'kernel/locking/spinlock.o',
               'kernel/time/timer.o', 'kernel/time/time.o', 'kernel/params.o',
               'kernel/panic.o', 'arch/arm64/kernel/process.o',
               'arch/arm64/kernel/cpufeature.o', 'lib/string.o']
    run(*make, *objects)
    records = []
    for relative in objects:
        output = subprocess.check_output([str(prefix) + 'nm', str(WORK / relative)], text=True)
        for line in output.splitlines():
            parts = line.split()
            if len(parts) == 3 and parts[1] == 'A' and parts[2].startswith('__crc_'):
                records.append('0x' + parts[0][-8:] + '\t' + parts[2][6:] + '\tvmlinux\tEXPORT_SYMBOL\n')
    (WORK / 'Module.symvers').write_text(''.join(records))
    print('LOCALLY_COMPUTED_EXPORT_CRCS', len(records), flush=True)
    module = WORK / 'stick-module'
    module.mkdir(exist_ok=True)
    source = REPO / 'android/h700-android10/device/roc/rgsp/input'
    for name in ['Makefile', 'h700_stick_axes.c']:
        shutil.copy2(source / 'kernel' / name, module / name)
    shutil.copy2(source / 'axis_math.h', WORK / 'axis_math.h')
    run(*make, 'M=' + str(module), 'modules')
    run('gcc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
        REPO / 'tools/tests/h700_stick_math_test.c', '-o', WORK / 'axis-math-test')
    run(WORK / 'axis-math-test')
    target = DELIVERY / 'h700_stick_axes.ko'
    run(str(prefix) + 'strip', '--strip-debug', '-o', target, module / 'h700_stick_axes.ko')
    run('python3', REPO / 'tools/h700_kernel_abi.py', '--boot', REPO / 'input/boot-live.img',
        '--reference-module', REPO / 'android/h700-android10/device/roc/rgsp/prebuilts/wifi/8821cs.ko',
        '--reference-module', Path('/home/lpf/h700-android10/android/device/roc/rgsp/prebuilts/local/mali_kbase.ko'),
        '--symvers', WORK / 'Module.symvers', '--module', target,
        '--receipt', DELIVERY / 'kernel-abi.json')


if __name__ == '__main__':
    main()

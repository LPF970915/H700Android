"""Build only the isolated H700 stick add-on and the ABI export objects.

Execution requires the repository's normal resource caps and a new work path.
The original kernel/device/prebuilt files are read-only inputs. No module load,
image mutation, device access, CRC rewriting, or full kernel target exists here.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LONGAN = Path("/home/lpf/h700-android10/longan")
OBJECTS = ["drivers/input/input.o", "drivers/gpio/gpiolib.o",
           "drivers/gpio/gpiolib-legacy.o", "kernel/workqueue.o",
           "kernel/module.o", "drivers/of/base.o", "kernel/printk/printk.o",
           "mm/page_alloc.o", "arch/arm64/kernel/arm64ksyms.o",
           "arch/arm64/mm/ioremap.o", "kernel/locking/spinlock.o",
           "kernel/time/timer.o", "kernel/time/time.o", "kernel/params.o",
           "kernel/panic.o", "arch/arm64/kernel/process.o",
           "arch/arm64/kernel/cpufeature.o", "lib/string.o", "kernel/power/main.o"]
SOURCES = ["h700_stick_axes.c", "axis_math.h", "h700_profile_policy.h",
           "h700_profile_table.h", "Makefile"]
CONFIG = REPO / "android/h700-android10/device/roc/rgsp/input/kernel/h700-4.9.170.config"
CONFIG_SHA = "565948300ae2d0f68a8ec85a18be033cde06ad4c46a988bebf708b9ce35cb119"
TEST7_KERNEL_SHA = "2495e91a0a2a9aca0845a7d364c023a068b7e2f06cafe490927ffde8b8490670"
TEST7_RAW = Path("/home/lpf/roc-os-h700-manual-selector-test7-20261116-v1/ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test7_BootHandoff_20261116.img")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args):
    print("RUN", *map(str, args), flush=True)
    subprocess.run(list(map(str, args)), check=True)


def resource_guard():
    group = Path("/sys/fs/cgroup") / Path("/proc/self/cgroup").read_text().strip().split("::")[-1].lstrip("/")
    quota, period = (group / "cpu.max").read_text().split()
    assert quota != "max" and int(quota) <= int(period)
    assert int((group / "memory.max").read_text()) <= 6442450944
    assert int((group / "memory.swap.max").read_text()) <= 536870912
    assert os.sched_getaffinity(0) <= {0, 1}
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19


def actual_kernel_export_binding(abi):
    """Bind ABI tables to Test7's actual kernel, with bounded ordinary-file reads.

    Pin the complete 17MB actual kernel, then prove original export records,
    CRC records, and every referenced symbol name are byte-identical. This does
    not pretend the old whole-kernel hash accepts arbitrary patched kernels.
    """
    import struct
    original_boot = REPO / "input/boot-live.img"
    _, header = abi.read_header(original_boot)
    offset = abi.component_offsets(header)["kernel"]
    with original_boot.open("rb") as source:
        source.seek(offset)
        original = source.read(header["kernel_size"])
    if original.startswith(b"\x1f\x8b"):
        original = gzip.decompress(original)
    assert hashlib.sha256(original).hexdigest() == abi.KERNEL_SHA
    with TEST7_RAW.open("rb") as source:
        source.seek(155189248)
        raw_header = source.read(2048)
        assert raw_header[:8] == b"ANDROID!"
        kernel_size, = struct.unpack_from("<I", raw_header, 8)
        page_size, = struct.unpack_from("<I", raw_header, 36)
        assert kernel_size == 17686536 and page_size == 2048
        actual = source.read(kernel_size)
    assert hashlib.sha256(actual).hexdigest() == TEST7_KERNEL_SHA
    count = (abi.EXPORT_END - abi.EXPORT_START) // 16
    end = abi.CRC_START + count * 8
    assert actual[abi.EXPORT_START:end] == original[abi.EXPORT_START:end]
    # Symbol-name pointers are fixed by the pinned original RELA table. Its
    # complete saved region and referenced names remain identical in Test7.
    relocation_start = 0xebe8f8
    relocation_end = relocation_start + 93585 * 24
    assert actual[relocation_start:relocation_end] == original[relocation_start:relocation_end]
    relocated = bytearray(original)
    import re
    applied = 0
    for match in re.finditer(re.escape(struct.pack("<Q", 0x403)), original):
        where = match.start() - 8
        if where < 0 or (where - relocation_start) % 24:
            continue
        target, kind, value = struct.unpack_from("<QQQ", original, where)
        if abi.BASE <= target <= abi.BASE + len(original) - 8:
            struct.pack_into("<Q", relocated, target - abi.BASE, value)
            applied += 1
    assert applied == 93585
    for where in range(abi.EXPORT_START, abi.EXPORT_END, 16):
        _, pointer = struct.unpack_from("<QQ", relocated, where)
        start = pointer - abi.BASE
        name = original[start:start + 150].split(b"\0")[0] + b"\0"
        assert actual[start:start + len(name)] == name
    return {"actual_test7_kernel_sha256": TEST7_KERNEL_SHA,
            "actual_kernel_bytes_read": len(actual), "export_count": count,
            "export_crc_tables_equal": True, "relocation_region_equal": True,
            "all_export_names_equal": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    plan = {"full_kernel_build": False, "objects": OBJECTS,
            "kernel_source": str(LONGAN / "kernel/linux-4.9"),
            "work": str(args.work), "output": str(args.output),
            "original_inputs_mutated": False, "module_loaded": False}
    if not args.execute:
        print(json.dumps(plan, indent=2)); return
    resource_guard()
    assert sha(CONFIG) == CONFIG_SHA
    args.work.mkdir(exist_ok=False)
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    before = {name: sha(HERE / name) for name in SOURCES}
    (args.output / "source-before.json").write_text(json.dumps(before, indent=2) + "\n")
    toolchain_name = "gcc-linaro-5.3.1-2016.05-x86_64_aarch64-linux-gnu"
    archive = LONGAN / "build/toolchain" / (toolchain_name + ".tar.xz")
    with tarfile.open(archive) as source:
        source.extractall(args.work, filter="data")
    prefix = args.work / toolchain_name / "bin/aarch64-linux-gnu-"
    shutil.copyfile(CONFIG, args.work / ".config")
    make = ["make", "-j1", "-C", LONGAN / "kernel/linux-4.9", "O=" + str(args.work),
            "ARCH=arm64", "CROSS_COMPILE=" + str(prefix), "HOSTCFLAGS=-O2 -fcommon"]
    run(str(prefix) + "gcc", "--version")
    run(*make, "olddefconfig", "prepare", "scripts", "modules_prepare")
    run(*make, *OBJECTS)
    records = []
    for relative in OBJECTS:
        output = subprocess.check_output([str(prefix) + "nm", str(args.work / relative)], text=True)
        for line in output.splitlines():
            parts = line.split()
            if len(parts) == 3 and parts[1] == "A" and parts[2].startswith("__crc_"):
                records.append("0x" + parts[0][-8:] + "\t" + parts[2][6:] + "\tvmlinux\tEXPORT_SYMBOL\n")
    (args.work / "Module.symvers").write_text("".join(records))
    module = args.work / "stick-module"
    module.mkdir()
    for name in SOURCES:
        shutil.copyfile(HERE / name, module / name)
    assert before == {name: sha(HERE / name) for name in SOURCES}
    run(*make, "M=" + str(module), "modules")
    target = args.output / "h700_stick_axes.ko"
    run(str(prefix) + "strip", "--strip-debug", "-o", target, module / "h700_stick_axes.ko")
    run(sys.executable, "-B", REPO / "tools/h700_kernel_abi.py",
        "--boot", REPO / "input/boot-live.img",
        "--reference-module", REPO / "android/h700-android10/device/roc/rgsp/prebuilts/wifi/8821cs.ko",
        "--reference-module", Path("/home/lpf/h700-android10/android/device/roc/rgsp/prebuilts/local/mali_kbase.ko"),
        "--symvers", args.work / "Module.symvers", "--module", target,
        "--receipt", args.output / "kernel-abi.json")
    sys.path.insert(0, str(REPO / "tools"))
    import h700_kernel_abi as abi
    binding = actual_kernel_export_binding(abi)
    (args.output / "actual-test7-kernel-binding.json").write_text(json.dumps(binding, indent=2) + "\n")
    after = {name: sha(HERE / name) for name in SOURCES}
    assert before == after
    result = {**plan, "passed": True, "elapsed_seconds": time.monotonic() - started,
              "source_sha256": before, "config_sha256": sha(CONFIG),
              "module_sha256": sha(target), "module_bytes": target.stat().st_size,
              "actual_test7_kernel_binding": binding,
              "module_version_crc_rewriting": False}
    (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()

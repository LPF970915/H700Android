"""Compile the new sampling candidate in a copy of the validated module cache.

Ordinary files only. Original BSP, Test8 source, cache and receipts stay intact.
The caller supplies the normal systemd resource caps and global flock.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[3]
HERE = REPO / "tools/input_profiles/stick_sampling_v2"
OLD = Path("/home/lpf/roc-os-h700-input-profiles-20261116-v1")
WORK = Path("/home/lpf/roc-os-h700-stick-sampling-module-20261117-v2")
OUT = REPO / "out/test8-sticks-runtime-20261117/module-v3"
KERNEL = Path("/home/lpf/h700-android10/longan/kernel/linux-4.9")
PARENT = REPO / "out/test7-rg35xxh-sticks-20261116/module-build-v1"
SOURCES = ["h700_stick_axes.c", "axis_math.h", "h700_profile_policy.h",
           "h700_profile_table.h", "Makefile"]


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(*args):
    print("RUN", *map(str, args), flush=True)
    subprocess.run(list(map(str, args)), check=True)


def main():
    sys.path[:0] = [str(REPO / "tools"), str(REPO / "tools/release")]
    from package_h700_v6a import constrained
    constrained()
    assert not WORK.exists() and not OUT.exists()
    assert not any(p.is_symlink() for p in [WORK, OUT, *OUT.parents])
    parent = json.loads((PARENT / "result.json").read_text())
    assert parent["passed"] is True
    for name, value in parent["source_sha256"].items():
        assert sha(REPO / "tools/input_profiles" / name) == value
        assert sha(OLD / "stick-module" / name) == value
    assert sha(REPO / "android/h700-android10/device/roc/rgsp/input/kernel/h700-4.9.170.config") == parent["config_sha256"]
    # The prior validated olddefconfig output omits vendor Kconfig options
    # absent from the retained source. Reuse that exact generated state;
    # actual module CRCs below remain the compatibility authority.
    generated_config_sha = "8d76497d7ab68f05d545ec17c56805440e3ed0c9ddd8594ff9ad2bb557d41baa"
    assert sha(OLD / ".config") == generated_config_sha
    symvers_sha = sha(OLD / "Module.symvers")
    sources = {name: sha(HERE / name) for name in SOURCES}
    host = json.loads((HERE / "host-result.json").read_text())
    assert host["passed"] is True
    for name in SOURCES:
        assert host["source_sha256"][name] == sources[name]
    OUT.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    run("cp", "-a", "--reflink=auto", "--sparse=always", OLD, WORK)
    module = WORK / "sampling-module-v2"
    module.mkdir()
    for name in SOURCES:
        shutil.copyfile(HERE / name, module / name)
    prefix = WORK / "gcc-linaro-5.3.1-2016.05-x86_64_aarch64-linux-gnu/bin/aarch64-linux-gnu-"
    # New diagnostics use jiffies, whose real export translation unit was not
    # needed by Test8. Generate its CRC normally with the retained source and
    # headers, then verify it against the actual kernel below. No guessed or
    # rewritten symbol versions are permitted.
    common = ["make", "-j1", "-C", str(KERNEL), "O=" + str(WORK), "ARCH=arm64",
              "CROSS_COMPILE=" + str(prefix), "HOSTCFLAGS=-O2 -fcommon"]
    run(*common, "kernel/time/jiffies.o")
    previous_symvers = (WORK / "Module.symvers").read_text()
    generated = subprocess.check_output([str(prefix) + "nm", str(WORK / "kernel/time/jiffies.o")], text=True)
    extra = []
    old_versions = {line.split()[1]: line.split()[0] for line in previous_symvers.splitlines()}
    for line in generated.splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[1] == "A" and fields[2].startswith("__crc_"):
            name, value = fields[2][6:], "0x" + fields[0][-8:]
            assert name not in old_versions or old_versions[name] == value
            if name not in old_versions:
                extra.append(value + "\t" + name + "\tvmlinux\tEXPORT_SYMBOL\n")
    assert any("\tjiffies\t" in row for row in extra)
    (WORK / "Module.symvers").write_text(previous_symvers + "".join(extra))
    extended_symvers_sha = sha(WORK / "Module.symvers")
    run("make", "-j1", "-C", KERNEL, "O=" + str(WORK), "ARCH=arm64",
        "CROSS_COMPILE=" + str(prefix), "HOSTCFLAGS=-O2 -fcommon",
        "M=" + str(module), "modules")
    target = OUT / "h700_stick_axes.ko"
    run(str(prefix) + "strip", "--strip-debug", "-o", target, module / "h700_stick_axes.ko")
    run(sys.executable, "-B", REPO / "tools/h700_kernel_abi.py",
        "--boot", REPO / "input/boot-live.img",
        "--reference-module", REPO / "android/h700-android10/device/roc/rgsp/prebuilts/wifi/8821cs.ko",
        "--reference-module", "/home/lpf/h700-android10/android/device/roc/rgsp/prebuilts/local/mali_kbase.ko",
        "--symvers", WORK / "Module.symvers", "--module", target,
        "--receipt", OUT / "kernel-abi.json")
    spec = importlib.util.spec_from_file_location("parent_input_build", REPO / "tools/input_profiles/build_module.py")
    oldbuild = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oldbuild)
    import h700_kernel_abi as abi
    binding = oldbuild.actual_kernel_export_binding(abi)
    # Test8 changes panel code only. Bind every import to the actual Test8
    # export/CRC/name/RELA byte ranges, in addition to the original ABI proof.
    test8 = Path("/home/lpf/roc-os-h700-twelve-model-test8-20261116-v1/ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test8_TwelveModel_20261116.img")
    with test8.open("rb") as stream:
        stream.seek(155189248 + 2048)
        actual = stream.read(17686536)
    assert hashlib.sha256(actual).hexdigest() == "62c4feb1650f1c311e79ebfe75a979bac89f3da77f1ab6e46ad46a8924fdb6e6"
    with oldbuild.TEST7_RAW.open("rb") as stream:
        stream.seek(155189248 + 2048)
        previous = stream.read(17686536)
    assert actual[abi.EXPORT_START:abi.EXPORT_END] == previous[abi.EXPORT_START:abi.EXPORT_END]
    crcend = abi.CRC_START + ((abi.EXPORT_END - abi.EXPORT_START) // 16) * 8
    assert actual[abi.CRC_START:crcend] == previous[abi.CRC_START:crcend]
    assert actual[0xebe8f8:0xebe8f8 + 93585 * 24] == previous[0xebe8f8:0xebe8f8 + 93585 * 24]
    # Names used by the exports are original pointers after RELA. All their
    # strings are part of the earlier fixed kernel binding; compare the
    # complete immutable rodata area that contains those names as well.
    import struct
    relocated = bytearray(previous)
    for offset in range(0xebe8f8, 0xebe8f8 + 93585 * 24, 24):
        address, kind, value = struct.unpack_from("<QQQ", previous, offset)
        if kind == 0x403 and abi.BASE <= address <= abi.BASE + len(previous) - 8:
            struct.pack_into("<Q", relocated, address - abi.BASE, value)
    for offset in range(abi.EXPORT_START, abi.EXPORT_END, 16):
        _, pointer = struct.unpack_from("<QQ", relocated, offset)
        startname = pointer - abi.BASE
        endname = previous.index(b"\0", startname) + 1
        assert actual[startname:endname] == previous[startname:endname]
    test8_binding = {"actual_kernel_sha256": hashlib.sha256(actual).hexdigest(),
        "actual_kernel_bytes_read": len(actual), "export_count": (abi.EXPORT_END - abi.EXPORT_START) // 16,
        "export_crc_tables_equal": True, "relocation_region_equal": True,
        "all_export_names_equal": True, "parent_test7_binding": binding}
    (OUT / "kernel-binding.json").write_text(json.dumps(test8_binding, indent=2) + "\n")
    assert sources == {name: sha(HERE / name) for name in SOURCES}
    assert sha(OLD / ".config") == sha(WORK / ".config") == generated_config_sha
    assert sha(OLD / "Module.symvers") == symvers_sha
    assert sha(WORK / "Module.symvers") == extended_symvers_sha
    for name, value in parent["source_sha256"].items():
        assert sha(REPO / "tools/input_profiles" / name) == value
        assert sha(OLD / "stick-module" / name) == value
    result = {"schema": "roc.h700.stick-sampling-module.v2", "passed": True,
        "elapsed_seconds": time.monotonic() - start, "source_sha256": sources,
        "module_path": str(target), "module_sha256": sha(target),
        "module_bytes": target.stat().st_size, "host_receipt": str(HERE / "host-result.json"),
        "host_receipt_sha256": sha(HERE / "host-result.json"),
        "abi_receipt_sha256": sha(OUT / "kernel-abi.json"),
        "kernel_binding_sha256": sha(OUT / "kernel-binding.json"),
        "actual_test7_binding": binding, "actual_test8_kernel_sha256": hashlib.sha256(actual).hexdigest(),
        "actual_test8_exports_crc_names_relocations_equal": True,
        "parent_sources_cache_preserved": True, "kernel_module_loaded": False,
        "generated_config_sha256": generated_config_sha, "symvers_sha256": symvers_sha,
        "candidate_symvers_sha256": extended_symvers_sha, "additional_generated_exports": extra,
        "physical_acceptance": False, "device_accessed": False}
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()

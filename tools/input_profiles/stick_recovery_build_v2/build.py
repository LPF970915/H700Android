"""Build and bind the isolated recovery module; never load it or change images."""
from pathlib import Path
import gzip
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[3]
HERE = REPO / "tools/input_profiles/stick_recovery_v4"
PARENT = REPO / "out/test8-sticks-runtime-20261117/module-v3"
CACHE = Path("/home/lpf/roc-os-h700-stick-sampling-module-20261117-v2")
WORK = Path("/home/lpf/roc-os-h700-stick-adc-control-20261117-v1")
OUT = REPO / "out/stick-adc-control-repair-20261117-v1/module-v1"
KERNEL = Path("/home/lpf/h700-android10/longan/kernel/linux-4.9")
SOURCES = ["h700_stick_axes.c", "axis_math.h", "h700_profile_policy.h",
           "h700_profile_table.h", "Makefile"]


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(*args):
    print("RUN", *map(str, args), flush=True)
    subprocess.run(list(map(str, args)), check=True)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    sys.path[:0] = [str(REPO / "tools"), str(REPO / "tools/release")]
    from package_h700_v6a import constrained
    import h700_kernel_abi as abi
    constrained()
    assert not WORK.exists() and not OUT.exists()
    parent = json.loads((PARENT / "result.json").read_text())
    assert parent["passed"] is True
    # Validate every frozen parent control before reusing its isolated cache.
    for path, expected in parent["controls"].items():
        assert sha(path) == expected, path
    assert sha(CACHE / ".config") == parent["generated_config_sha256"]
    old_symvers = sha(CACHE / "Module.symvers")
    host_path = OUT.parent / "host-final/host-result.json"
    host = json.loads(host_path.read_text())
    assert host["passed"] is True
    source_hashes = {name: sha(HERE / name) for name in SOURCES}
    for name, value in source_hashes.items():
        assert host["source_sha256"][name] == value
    OUT.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    run("cp", "-a", "--reflink=auto", "--sparse=always", CACHE, WORK)
    module_dir = WORK / "recovery-module-v4"
    module_dir.mkdir()
    for name in SOURCES:
        shutil.copyfile(HERE / name, module_dir / name)
    prefix = WORK / "gcc-linaro-5.3.1-2016.05-x86_64_aarch64-linux-gnu/bin/aarch64-linux-gnu-"
    run("make", "-j1", "-C", KERNEL, "O=" + str(WORK), "ARCH=arm64",
        "CROSS_COMPILE=" + str(prefix), "HOSTCFLAGS=-O2 -fcommon",
        "M=" + str(module_dir), "modules")
    target = OUT / "h700_stick_axes.ko"
    run(str(prefix) + "strip", "--strip-debug", "-o", target, module_dir / target.name)
    run(sys.executable, "-B", REPO / "tools/h700_kernel_abi.py",
        "--boot", REPO / "input/boot-live.img",
        "--reference-module", REPO / "android/h700-android10/device/roc/rgsp/prebuilts/wifi/8821cs.ko",
        "--reference-module", "/home/lpf/h700-android10/android/device/roc/rgsp/prebuilts/local/mali_kbase.ko",
        "--symvers", WORK / "Module.symvers", "--module", target,
        "--receipt", OUT / "kernel-abi.json")
    # The retained bounded RELA reader only defines functions when imported.
    old_verifier = REPO / "tools/input_profiles/stick_build_v2/postverify.py"
    verifier = load_module("recovery_parent_kernel_reader", old_verifier)
    original_boot = REPO / "input/boot-live.img"
    _, header = abi.read_header(original_boot)
    with original_boot.open("rb") as stream:
        stream.seek(abi.component_offsets(header)["kernel"])
        original = stream.read(header["kernel_size"])
    if original.startswith(b"\x1f\x8b"):
        original = gzip.decompress(original)
    assert hashlib.sha256(original).hexdigest() == abi.KERNEL_SHA
    records, fields, exports = verifier.relocated_exports(original, abi)
    imports = abi.versions(target)
    assert abi.undefined_symbols(target) <= imports.keys()
    local = {row.split()[1]: int(row.split()[0], 16)
             for row in (WORK / "Module.symvers").read_text().splitlines()}
    bindings = []
    cards = [
        ("test7", "/home/lpf/roc-os-h700-manual-selector-test7-20261116-v1/ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test7_BootHandoff_20261116.img", "2495e91a0a2a9aca0845a7d364c023a068b7e2f06cafe490927ffde8b8490670"),
        ("test8", "/home/lpf/roc-os-h700-twelve-model-test8-20261116-v1/ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test8_TwelveModel_20261116.img", "62c4feb1650f1c311e79ebfe75a979bac89f3da77f1ab6e46ad46a8924fdb6e6"),
        ("test9", "/home/lpf/roc-os-h700-stick-memory-test9-20261117-v1/ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test9_StickMemory_20261117.img", "62c4feb1650f1c311e79ebfe75a979bac89f3da77f1ab6e46ad46a8924fdb6e6"),
    ]
    for name, path, expected in cards:
        kernel = verifier.card_kernel(Path(path), expected)
        current_records, current_fields, current_exports = verifier.relocated_exports(kernel, abi)
        assert current_records == records and current_fields == fields and current_exports == exports
        assert kernel[verifier.RELA_ANCHOR:] == original[verifier.RELA_ANCHOR:]
        for symbol, crc in imports.items():
            assert exports[symbol] == current_exports[symbol] == local[symbol] == crc, symbol
        bindings.append({"image": name, "kernel_sha256": expected,
                         "exports_matched": len(exports), "relative_records_matched": len(records),
                         "module_imports_matched": len(imports)})
    assert sha(CACHE / "Module.symvers") == old_symvers == sha(WORK / "Module.symvers")
    assert sha(CACHE / ".config") == sha(WORK / ".config") == parent["generated_config_sha256"]
    assert source_hashes == {name: sha(HERE / name) for name in SOURCES}
    for path, expected in parent["controls"].items():
        assert sha(path) == expected, path
    binding_path = OUT / "kernel-binding.json"
    binding_path.write_text(json.dumps({"passed": True, "module_sha256": sha(target),
        "original_kernel_sha256": abi.KERNEL_SHA, "cards": bindings,
        "module_version_crc_rewriting": False}, indent=2) + "\n")
    controls = {str(path): sha(path) for path in [Path(__file__).resolve(), old_verifier,
        REPO / "tools/h700_kernel_abi.py", host_path, PARENT / "result.json",
        WORK / ".config", WORK / "Module.symvers", target,
        OUT / "kernel-abi.json", binding_path]}
    result = {"schema": "roc.h700.stick-adc-control-module.v1", "passed": True,
        "elapsed_seconds": time.monotonic() - started, "source_sha256": source_hashes,
        "module_sha256": sha(target), "module_path": str(target),
        "module_bytes": target.stat().st_size, "host_receipt_sha256": sha(host_path),
        "kernel_binding_sha256": sha(binding_path), "controls": controls,
        "parent_cache_preserved": True, "kernel_module_loaded": False,
        "physical_acceptance": False, "device_accessed": False,
        "images_mutated": False, "module_version_crc_rewriting": False}
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()

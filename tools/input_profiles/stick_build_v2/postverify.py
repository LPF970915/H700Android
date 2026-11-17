"""Complete the existing v3 module audit without compiling or loading it.

The earlier build linked/stripped the module and passed its ABI audit, then
failed in its final RELA loop. That failure and its exact log remain retained.
This separate verifier bounds each actual RELA record and verifies every import
against the original, Test7 and Test8 kernels, rather than guessing a table end.
"""
from pathlib import Path
import gzip
import hashlib
import importlib.util
import json
import re
import struct
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[3]
HERE = REPO / "tools/input_profiles/stick_sampling_v2"
OUT = REPO / "out/test8-sticks-runtime-20261117/module-v3"
WORK = Path("/home/lpf/roc-os-h700-stick-sampling-module-20261117-v2")
OLD = Path("/home/lpf/roc-os-h700-input-profiles-20261116-v1")
MODULE_SHA = "5a017572b601ac8ae70216852cce3763428d5fa5793c4767812c8caf7b2d0deb"
TEST8_SHA = "62c4feb1650f1c311e79ebfe75a979bac89f3da77f1ab6e46ad46a8924fdb6e6"
CONFIG_SHA = "8d76497d7ab68f05d545ec17c56805440e3ed0c9ddd8594ff9ad2bb557d41baa"
SOURCES = ["h700_stick_axes.c", "axis_math.h", "h700_profile_policy.h",
           "h700_profile_table.h", "Makefile"]
RELA_ANCHOR = 0xebe8f8


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def relocated_exports(kernel, abi):
    records = []
    expanded = bytearray(kernel)
    for match in re.finditer(re.escape(struct.pack("<Q", 0x403)), kernel):
        where = match.start() - 8
        if where < 0 or where + 24 > len(kernel) or (where - RELA_ANCHOR) % 24:
            continue
        target, kind, value = struct.unpack_from("<QQQ", kernel, where)
        if kind == 0x403 and abi.BASE <= target <= abi.BASE + len(kernel) - 8:
            records.append((where, target, kind, value))
            struct.pack_into("<Q", expanded, target - abi.BASE, value)
    assert len(records) == 93585
    exports, fields = {}, []
    for i, where in enumerate(range(abi.EXPORT_START, abi.EXPORT_END, 16)):
        value, pointer = struct.unpack_from("<QQ", expanded, where)
        assert abi.BASE <= pointer < abi.BASE + len(kernel)
        start = pointer - abi.BASE
        end = expanded.find(b"\0", start, min(start + 150, len(kernel)))
        assert end > start
        name = bytes(expanded[start:end])
        assert re.fullmatch(rb"[A-Za-z_][A-Za-z_0-9]*", name)
        name = name.decode("ascii")
        assert name not in exports
        crc, = struct.unpack_from("<Q", expanded, abi.CRC_START + i * 8)
        exports[name] = crc
        fields.append((value, pointer, name, crc))
    assert len(exports) == 8715
    return records, fields, exports


def card_kernel(path, digest):
    with path.open("rb") as stream:
        stream.seek(155189248)
        header = stream.read(2048)
        assert header[:8] == b"ANDROID!"
        size, = struct.unpack_from("<I", header, 8)
        page, = struct.unpack_from("<I", header, 36)
        assert size == 17686536 and page == 2048
        data = stream.read(size)
    assert hashlib.sha256(data).hexdigest() == digest
    return data


def main():
    sys.path[:0] = [str(REPO / "tools"), str(REPO / "tools/release")]
    import h700_kernel_abi as abi
    from package_h700_v6a import constrained
    constrained()
    assert not (OUT / "result.json").exists()
    assert not (OUT / "kernel-binding.json").exists()
    hostpath = HERE / "host-result.json"
    host = json.loads(hostpath.read_text())
    assert host["passed"] and host["actual_C_host_test"]
    for name, value in host["source_sha256"].items():
        assert sha(HERE / name) == value
    for name in SOURCES:
        assert sha(WORK / "sampling-module-v2" / name) == host["source_sha256"][name]
    parentpath = REPO / "out/test7-rg35xxh-sticks-20261116/module-build-v1/result.json"
    parent = json.loads(parentpath.read_text())
    assert parent["passed"]
    for name, value in parent["source_sha256"].items():
        assert sha(REPO / "tools/input_profiles" / name) == value
        assert sha(OLD / "stick-module" / name) == value
    assert sha(REPO / "android/h700-android10/device/roc/rgsp/input/kernel/h700-4.9.170.config") == parent["config_sha256"]
    assert sha(OLD / ".config") == sha(WORK / ".config") == CONFIG_SHA
    module = OUT / "h700_stick_axes.ko"
    assert sha(module) == MODULE_SHA
    prefix = WORK / "gcc-linaro-5.3.1-2016.05-x86_64_aarch64-linux-gnu/bin/aarch64-linux-gnu-"
    with tempfile.TemporaryDirectory(prefix="h700-postverify-") as temporary:
        stripped = Path(temporary) / "module.ko"
        subprocess.run([str(prefix) + "strip", "--strip-debug", "-o", str(stripped),
                        str(WORK / "sampling-module-v2/h700_stick_axes.ko")], check=True)
        assert sha(stripped) == MODULE_SHA
    oldsymvers = (OLD / "Module.symvers").read_text()
    oldversions = {row.split()[1]: row.split()[0] for row in oldsymvers.splitlines()}
    generated = subprocess.check_output([str(prefix) + "nm", str(WORK / "kernel/time/jiffies.o")], text=True)
    extra = []
    for row in generated.splitlines():
        fields = row.split()
        if len(fields) == 3 and fields[1] == "A" and fields[2].startswith("__crc_"):
            name, value = fields[2][6:], "0x" + fields[0][-8:]
            assert name not in oldversions or oldversions[name] == value
            if name not in oldversions:
                extra.append(value + "\t" + name + "\tvmlinux\tEXPORT_SYMBOL\n")
    assert any("\tjiffies\t" in row for row in extra)
    assert (WORK / "Module.symvers").read_text() == oldsymvers + "".join(extra)
    abipath = OUT / "kernel-abi.json"
    proof = json.loads(abipath.read_text())
    assert proof["module_sha256"] == MODULE_SHA
    assert proof["reference_crcs_matched"] == 410 and proof["local_crcs_matched"] == 418
    assert proof["module_imports_matched"] == 43
    originalboot = REPO / "input/boot-live.img"
    _, header = abi.read_header(originalboot)
    with originalboot.open("rb") as stream:
        stream.seek(abi.component_offsets(header)["kernel"])
        original = stream.read(header["kernel_size"])
    if original.startswith(b"\x1f\x8b"):
        original = gzip.decompress(original)
    assert hashlib.sha256(original).hexdigest() == abi.KERNEL_SHA
    test7 = card_kernel(Path("/home/lpf/roc-os-h700-manual-selector-test7-20261116-v1/ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test7_BootHandoff_20261116.img"),
                        "2495e91a0a2a9aca0845a7d364c023a068b7e2f06cafe490927ffde8b8490670")
    test8 = card_kernel(Path("/home/lpf/roc-os-h700-twelve-model-test8-20261116-v1/ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test8_TwelveModel_20261116.img"), TEST8_SHA)
    original_records, original_fields, original_exports = relocated_exports(original, abi)
    for candidate in [test7, test8]:
        assert candidate[RELA_ANCHOR:] == original[RELA_ANCHOR:]
        records, fields, exports = relocated_exports(candidate, abi)
        assert records == original_records
        assert fields == original_fields and exports == original_exports
        crcend = abi.CRC_START + len(exports) * 8
        assert candidate[abi.EXPORT_START:crcend] == original[abi.EXPORT_START:crcend]
    versions = abi.versions(module)
    undefined = abi.undefined_symbols(module)
    assert "module_layout" in versions and undefined <= versions.keys() and len(versions) == 43
    local = {p[1]: int(p[0], 16) for row in (WORK / "Module.symvers").read_text().splitlines() if (p := row.split())}
    for name, crc in versions.items():
        assert original_exports[name] == exports[name] == local[name] == crc
    for name, crc in local.items():
        assert exports[name] == crc
    binding = {"actual_kernel_sha256": TEST8_SHA, "actual_kernel_bytes_read": len(test8),
               "export_count": len(exports), "export_crc_tables_equal": True,
               "relocation_region_equal": True, "all_export_names_equal": True,
               "relocated_export_value_name_crc_fields_equal": True,
               "relocation_proof": "all bounded aligned RELATIVE records compared in all three pinned kernels",
               "relocation_tail_byte_equal": True,
               "relative_records_compared": len(records), "module_imports_matched": len(versions),
               "module_sha256": MODULE_SHA, "passed": True}
    bindingpath = OUT / "kernel-binding.json"
    failedlog = REPO / "out/test8-sticks-runtime-20261117/module-build-logs/roc-h700-stick-sampling-module-20261117-021622.log"
    log = failedlog.read_text()
    assert "LD [M]" in log and MODULE_SHA in log and "struct.error:" in log
    bindingpath.write_text(json.dumps(binding, indent=2) + "\n")
    controls = {str(path): sha(path) for path in [Path(__file__).resolve(),
                REPO / "tools/h700_kernel_abi.py",
                REPO / "tools/input_profiles/stick_build_v2/build.py", failedlog, abipath, bindingpath,
                hostpath, parentpath, module, WORK / "Module.symvers", WORK / ".config",
                WORK / "kernel/time/jiffies.o", WORK / "sampling-module-v2/h700_stick_axes.ko"]}
    result = {"schema": "roc.h700.stick-sampling-module.v2", "passed": True,
              "module_path": str(module), "module_sha256": MODULE_SHA,
              "source_sha256": {name: host["source_sha256"][name] for name in SOURCES},
              "module_bytes": module.stat().st_size, "host_receipt": str(hostpath),
              "host_receipt_sha256": sha(hostpath), "abi_receipt_sha256": sha(abipath),
              "kernel_binding_sha256": sha(bindingpath), "controls": controls,
              "compilation_and_abi_completed_in_prior_job": True,
              "prior_job_failed_final_audit": True, "final_audit_completed_separately": True,
              "module_recompiled_by_postverify": False, "module_version_crc_rewriting": False,
              "additional_generated_exports": extra, "generated_config_sha256": CONFIG_SHA,
              "parent_sources_cache_preserved": True, "kernel_module_loaded": False,
              "physical_acceptance": False, "device_accessed": False}
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()

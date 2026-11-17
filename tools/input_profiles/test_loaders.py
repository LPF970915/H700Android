"""Execute both production candidate scripts with explicit hardware boundaries.

The early script runs in the retained ARM64 mother BusyBox under qemu, using its
real cat/grep/sha256sum. Only insmod is intercepted. Android script runs through
an Android-command function boundary; its exact source is sourced unchanged.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "boot_selector"))
from reference_model import MODEL_CATALOG

MODULE = REPO / "out/test7-rg35xxh-sticks-20261116/module-build-v1/h700_stick_axes.ko"
MODULE_SHA = "bc7a000ecc6ad0eaabe0cfb137ebb8b49f739b89b2473b5204ec67c437dae38f"
BUSYBOX = REPO / "out/boot-selector-integration-20261114/selector-init-fixture-v7/busybox"
BUSYBOX_SHA = "ac739b9a7263faf678d29691e10fabd7edcee61fc18cf4aed57c8d270d0894c7"
SYSROOT = BUSYBOX.parent / "mother-sysroot"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    assert digest(MODULE) == MODULE_SHA
    # Pin the exact retained binary in the receipt. Its original-image binding
    # is retained by Test5/Test7 prefix receipts, not invented by this test.
    actual_busybox_sha = digest(BUSYBOX)
    assert actual_busybox_sha == BUSYBOX_SHA
    fixture = json.loads((BUSYBOX.parent / "result.json").read_text())
    libraries = fixture["mother_busybox"]["actual_mother_libraries_sha256"]
    for name, expected in libraries.items():
        assert digest(SYSROOT / name) == expected
    rows = []

    def early(name, model="rg35xxh", sticks="2", expect_load=True, **kw):
        case = args.output / ("early-" + name)
        case.mkdir()
        root = case / "root"
        module = root / "vendor/modules/h700_stick_axes.ko"
        module.parent.mkdir(parents=True)
        if not kw.get("missing_module"):
            data = MODULE.read_bytes()
            module.write_bytes((b"!" + data[1:]) if kw.get("bad_hash") else data)
        cmdline = case / "cmdline"
        cmdline.write_text(kw.get("cmdline", "androidboot.roc_model=%s androidboot.roc_sticks=%s" % (model, sticks)))
        modules = case / "modules"
        modules.write_text("h700_stick_axes 23808 0 - Live 0\n" if kw.get("loaded") else "")
        sysmodules = case / "sysmodules/h700_stick_axes/parameters"
        sysmodules.mkdir(parents=True)
        (sysmodules / "profile").write_text(kw.get("loaded_profile", model))
        attempts = case / "attempts"
        bb = case / "busybox-boundary"
        bb.write_text("#!/bin/sh\nif [ \"$1\" = insmod ]; then\n"
                      + " shift\n printf '%s\\n' \"$*\" >> " + shlex.quote(str(attempts)) + "\n"
                      + " exit " + str(kw.get("load_result", 0)) + "\nfi\n"
                      + "exec /usr/bin/qemu-aarch64 -L " + shlex.quote(str(SYSROOT)) + " "
                      + shlex.quote(str(BUSYBOX)) + ' "$@"\n')
        bb.chmod(0o755)
        command = ["/usr/bin/qemu-aarch64", "-L", str(SYSROOT), str(BUSYBOX), "sh",
                   str(HERE / "h700_optional_axes.sh"), str(root), str(modules),
                   str(bb), kw.get("kernel", "4.9.170"), str(cmdline), str(case / "sysmodules")]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=15)
        (case / "output.txt").write_text(completed.stdout + completed.stderr)
        loads = attempts.read_text().splitlines() if attempts.exists() else []
        assert completed.returncode == 0, (name, completed.returncode, completed.stderr)
        assert len(loads) == (1 if expect_load else 0), (name, loads, completed.stdout, completed.stderr)
        if loads:
            assert loads[0] == str(module) + " profile=" + model, (name, loads)
        rows.append({"name": "early-" + name, "passed": True, "insmod_calls": len(loads),
                     "mother_busybox_shell_and_hash": True, "module_load_mocked": True})

    def android(name, model="rg35xxh", sticks="2", expect_load=True, **kw):
        case = args.output / ("android-" + name)
        case.mkdir()
        attempts = case / "attempts"
        logs = case / "android.log"
        def quoted(value): return shlex.quote(str(value))
        script = case / "boundary.sh"
        script.write_text("#!/bin/sh\n"
            + "getprop(){ case \"$1\" in ro.boot.roc_model) printf '%s\\n' " + quoted(model)
            + ";; ro.boot.roc_sticks) printf '%s\\n' " + quoted(sticks) + ";; *) exit 99;; esac; }\n"
            + "uname(){ printf '%s\\n' " + quoted(kw.get("kernel", "4.9.170")) + "; }\n"
            + "sha256sum(){ [ \"$1\" = /vendor/modules/h700_stick_axes.ko ] || exit 99; printf '%s  %s\\n' "
            + quoted("0" * 64 if kw.get("bad_hash") else MODULE_SHA) + ' "$1"; }\n'
            + "grep(){ [ \"$2\" = '^h700_stick_axes ' ] && [ \"$3\" = /proc/modules ] || exit 99; return "
            + ("0" if kw.get("loaded") else "1") + "; }\n"
            + "cat(){ [ \"$1\" = /sys/module/h700_stick_axes/parameters/profile ] || exit 99; printf '%s\\n' "
            + quoted(kw.get("loaded_profile", model)) + "; }\n"
            + "insmod(){ printf '%s\\n' \"$*\" >> " + quoted(attempts) + "; return " + str(kw.get("load_result", 0)) + "; }\n"
            + "log(){ printf '%s\\n' \"$*\" >> " + quoted(logs) + "; }\n"
            + ". " + quoted(HERE / "rgsp-stick-axes.sh") + "\n")
        completed = subprocess.run(["/bin/sh", str(script)], capture_output=True, text=True, timeout=5)
        (case / "output.txt").write_text(completed.stdout + completed.stderr)
        loads = attempts.read_text().splitlines() if attempts.exists() else []
        assert completed.returncode == 0, (name, completed.returncode, completed.stderr)
        assert len(loads) == (1 if expect_load else 0), (name, loads)
        if loads: assert loads[0] == "/vendor/modules/h700_stick_axes.ko profile=" + model
        rows.append({"name": "android-" + name, "passed": True,
                     "insmod_calls": len(loads), "Android_commands_mocked": True})

    for model in MODEL_CATALOG:
        early(model.model_id, model.model_id, str(model.sticks), bool(model.sticks))
        android(model.model_id, model.model_id, str(model.sticks), bool(model.sticks))
    for loader in (early, android):
        loader("bad_hash", bad_hash=True, expect_load=False)
        loader("wrong_kernel", kernel="other", expect_load=False)
        loader("metadata_mismatch", sticks="1", expect_load=False)
        loader("noncanonical", model="RG35XXH", expect_load=False)
        loader("missing_model", model="", expect_load=False)
        loader("loaded_same", loaded=True, expect_load=False)
        loader("loaded_other", loaded=True, loaded_profile="rg34xxsp", expect_load=False)
        loader("hardware_refusal_nonfatal", load_result=19)
    early("missing_module", missing_module=True, expect_load=False)
    early("duplicate_model", cmdline="androidboot.roc_model=rg35xxh androidboot.roc_model=rg34xxsp androidboot.roc_sticks=2", expect_load=False)
    early("duplicate_sticks", cmdline="androidboot.roc_model=rg35xxh androidboot.roc_sticks=2 androidboot.roc_sticks=0", expect_load=False)
    early("missing_sticks", cmdline="androidboot.roc_model=rg35xxh", expect_load=False)
    early("injection", cmdline="androidboot.roc_model=rg35xxh;touch androidboot.roc_sticks=2", expect_load=False)
    result = {"passed": True, "cases": len(rows), "rows": rows,
              "module_sha256": MODULE_SHA, "mother_busybox_sha256": actual_busybox_sha,
              "mother_libraries_sha256": libraries,
              "source_sha256": {name: digest(HERE / name) for name in
                  ("h700_optional_axes.sh", "rgsp-stick-axes.sh", "test_loaders.py")},
              "hardware_module_not_loaded": True,
              "scope": "actual candidate shell scripts; insmod and Android commands mocked"}
    (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()

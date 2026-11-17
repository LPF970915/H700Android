"""Run light actual-C tests; no kernel build, device access or old input writes."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess

HERE = Path(__file__).resolve().parent
SOURCE_FILES = (
    "h700_stick_axes.c", "axis_math.h", "h700_profile_policy.h",
    "h700_profile_table.h", "test_kernel_shim.h", "test_driver.c", "Makefile",
    "test_parent_negative.c", "parent-manifest.json", "README.md", "run_host.py",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert os.sched_getaffinity(0) <= {0, 1}
    parent = json.loads((HERE / "parent-manifest.json").read_text(encoding="utf-8-sig"))
    for name, expected in parent["source_sha256"].items():
        assert sha(HERE.parent / name) == expected, ("parent changed", name)
    controls = {name: sha(HERE / name) for name in SOURCE_FILES}
    results = {}
    for stem in ("test_driver", "test_parent_negative"):
        binary = output / stem
        command = ["gcc", "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
                   "-Wno-sign-compare", str(HERE / (stem + ".c")), "-o", str(binary)]
        compiled = subprocess.run(command, text=True, capture_output=True)
        (output / (stem + "-compile.txt")).write_text(compiled.stdout + compiled.stderr)
        assert compiled.returncode == 0, compiled.stderr
        ran = subprocess.run([str(binary)], text=True, capture_output=True)
        (output / (stem + "-output.txt")).write_text(ran.stdout + ran.stderr)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        results[stem] = {"compile_command": command, "output": ran.stdout,
                         "binary_path": str(binary), "binary_sha256": sha(binary),
                         "exit_code": ran.returncode}
        print(ran.stdout, end="", flush=True)
    match = re.search(r"(\d+) scenarios / (\d+) checks", results["test_driver"]["output"])
    negative = re.search(r"reproduced (\d+) software blockers / (\d+) checks",
                         results["test_parent_negative"]["output"])
    assert match and negative
    assert {name: sha(HERE / name) for name in SOURCE_FILES} == controls
    for name, expected in parent["source_sha256"].items():
        assert sha(HERE.parent / name) == expected, ("parent changed", name)
    receipt = {
        "schema": "roc.h700.stick-sampling-v2-host.v1", "passed": True,
        "actual_C_host_test": True, "kernel_APIs_mocked": True,
        "scenarios": int(match[1]), "checks": int(match[2]),
        "negative_control_blockers": int(negative[1]),
        "negative_control_checks": int(negative[2]),
        "source_sha256": controls,
        "controls": {str(HERE / name): digest for name, digest in controls.items()},
        "parent_manifest_sha256": sha(HERE / "parent-manifest.json"),
        "parent_sources_unchanged": True, "details": results,
        "physical_acceptance": False, "kernel_module_built": False,
        "device_accessed": False,
        "limitations": "Physical raw ADC root cause unproven; host APIs mocked; no actual module load or physical acceptance.",
    }
    encoded = json.dumps(receipt, indent=2) + "\n"
    (output / "host-result.json").write_text(encoded)
    (HERE / "host-result.json").write_text(encoded)
    print("HOST_RECEIPT", output / "host-result.json", flush=True)


if __name__ == "__main__":
    main()

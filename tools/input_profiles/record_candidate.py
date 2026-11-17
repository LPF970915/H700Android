"""Record the candidate's real host build, ABI proof and loader-test identities."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASE = REPO / "out/test7-rg35xxh-sticks-20261116"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    subprocess.run([sys.executable, "-B", str(HERE / "generate_profiles.py"), "--check"], check=True)
    before = {str(path.relative_to(HERE)): sha(path) for path in sorted(HERE.iterdir()) if path.is_file()}
    binary = args.output / "actual-driver-host-test"
    command = ["gcc", "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror", "-Wno-sign-compare",
               str(HERE / "test_driver.c"), "-o", str(binary)]
    compiled = subprocess.run(command, capture_output=True, text=True)
    (args.output / "compile.log").write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0
    executed = subprocess.run([str(binary)], capture_output=True, text=True)
    (args.output / "run.log").write_text(executed.stdout + executed.stderr)
    assert executed.returncode == 0
    counts = re.search(r"(\d+) scenarios / (\d+) checks", executed.stdout)
    assert counts
    module_dir = BASE / "module-build-v1"
    module = module_dir / "h700_stick_axes.ko"
    build = load(module_dir / "result.json")
    assert build["passed"] and build["module_sha256"] == sha(module)
    for name, digest in build["source_sha256"].items():
        assert before[name] == digest
    abi = load(module_dir / "kernel-abi.json")
    assert abi["module_sha256"] == sha(module) and abi["module_imports_matched"] == 40
    assert abi["reference_crcs_matched"] == 410 and abi["local_crcs_matched"] == 417
    sys.path.insert(0, str(REPO / "tools"))
    import h700_kernel_abi
    imports = h700_kernel_abi.undefined_symbols(module)
    assert "totalram_pages" not in imports
    assert {"register_pm_notifier", "unregister_pm_notifier"} <= imports
    assert not re.search(r"totalram_pages|MemTotal|1536", (HERE / "h700_stick_axes.c").read_text())
    loaders_path = BASE / "loader-tests-v2/result.json"
    loaders = load(loaders_path)
    assert loaders["passed"] and loaders["cases"] == 45
    assert loaders["module_sha256"] == sha(module)
    for name, digest in loaders["source_sha256"].items():
        assert before[name] == digest
    for name in ("h700_optional_axes.sh", "rgsp-stick-axes.sh"):
        assert sha(module) in (HERE / name).read_text()
    after = {str(path.relative_to(HERE)): sha(path) for path in sorted(HERE.iterdir()) if path.is_file()}
    assert before == after
    proof_paths = [module_dir / "result.json", module_dir / "kernel-abi.json",
                   module_dir / "actual-test7-kernel-binding.json", loaders_path,
                   BASE / "input-review-v1/hardware-profiles-v2.json",
                   BASE / "reference-review-v1/direction-source-conflict-supplement.json"]
    result = {"schema": "roc.h700.explicit-input-candidate.v1", "passed": True,
              "source_sha256": before, "actual_C_host_test": {
                  "scenarios": int(counts[1]), "checks": int(counts[2]),
                  "compile_command": command, "compiler": subprocess.check_output(["gcc", "--version"], text=True).splitlines()[0],
                  "binary_sha256": sha(binary), "kernel_APIs_mocked": True},
              "loader_cases": 45, "module_path": str(module), "module_sha256": sha(module),
              "module_bytes": module.stat().st_size,
              "module_imports": sorted(imports), "no_RAM_identity_gate": True,
              "catalog_models": 12, "no_stick_models": 6, "single_stick_models": 1,
              "dual_stick_models": 5,
              "proof_sha256": {str(path.relative_to(REPO)): sha(path) for path in proof_paths},
              "physical_acceptance": False,
              "direction_candidates_pending_physical_measurements": ["rg35xxh", "rgcubexx", "rg40xxh", "rg40xxv", "rg35xxpro"],
              "kernel_module_loaded": False, "images_changed": False, "device_accessed": False}
    target = args.output / "result.json"
    target.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": True, "scenarios": int(counts[1]), "checks": int(counts[2]),
                      "module_sha256": sha(module), "receipt": str(target), "receipt_sha256": sha(target)}, indent=2))


if __name__ == "__main__":
    main()

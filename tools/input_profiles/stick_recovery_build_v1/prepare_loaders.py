"""Prepare ordinary candidate files, retaining Test9's exact 2GiB swap prefix."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "out/stick-regression-repair-20261117-v1"
PARENT = REPO / "tools/memory_swap_v1"
OLD_SHA = "5a017572b601ac8ae70216852cce3763428d5fa5793c4767812c8caf7b2d0deb"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    module = OUT / "module-v1/h700_stick_axes.ko"
    receipt = json.loads((module.parent / "result.json").read_text())
    assert receipt["passed"] and receipt["module_sha256"] == sha(module)
    current = sha(module)
    target = OUT / "integration-v2"
    assert not target.exists()
    target.mkdir(parents=True)
    controls = {}
    for name in ("h700_optional_axes.sh", "rgsp-stick-axes.sh"):
        source = PARENT / name
        original = source.read_bytes()
        assert original.count(OLD_SHA.encode()) == 1
        changed = original.replace(OLD_SHA.encode(), current.encode())
        assert changed.replace(current.encode(), OLD_SHA.encode()) == original
        (target / name).write_bytes(changed)
        controls[str(source)] = sha(source)
    prefix = (PARENT / "swap_prefix.sh").read_bytes()
    assert (target / "h700_optional_axes.sh").read_bytes().startswith(b"#!/bin/sh\n" + prefix)
    controls[str(PARENT / "swap_prefix.sh")] = sha(PARENT / "swap_prefix.sh")
    controls[str(Path(__file__).resolve())] = sha(Path(__file__).resolve())
    # Run existing real BusyBox/hash/model tests on the actual new scripts.
    test_source = REPO / "tools/input_profiles/stick_sampling_v2/test_loaders.py"
    (target / "test_loaders.py").write_bytes(test_source.read_bytes())
    spec = importlib.util.spec_from_file_location("recovery_exact_loader_tests", test_source)
    tests = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tests)
    tests.HERE = target
    previous_argv = sys.argv
    try:
        sys.argv = [str(test_source), "--output", str(OUT / "loaders-v1"),
                    "--module", str(module), "--module-sha256", current]
        tests.main()
    finally:
        sys.argv = previous_argv
    controls[str(test_source)] = sha(test_source)
    result = {"passed": True, "schema": "roc.h700.stick-recovery-integration.v1",
        "module_sha256": current, "parent_module_sha256": OLD_SHA,
        "swap_prefix_byte_exact": True, "default_swap_bytes": 2147483648,
        "only_loader_change": "pinned module SHA256", "controls": controls,
        "artifacts": {str(path): sha(path) for path in
            [module, target / "h700_optional_axes.sh", target / "rgsp-stick-axes.sh"]},
        "loaders_receipt_sha256": sha(OUT / "loaders-v1/result.json"),
        "images_mutated": False, "device_accessed": False, "physical_acceptance": False}
    (target / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()

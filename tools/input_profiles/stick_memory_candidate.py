"""Freeze independently produced module, loader and memory proofs for Test9.

Ordinary-file receipt assembly only: no compilation, device, swapon or flashing.
"""
from pathlib import Path
import argparse
import hashlib
import json

REPO = Path(__file__).resolve().parents[2]


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pinned(path):
    path = Path(path).resolve()
    assert path.is_absolute() and path.is_file()
    return {"path": str(path), "sha256": sha(path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--memory", required=True, type=Path)
    parser.add_argument("--helper", required=True, type=Path)
    parser.add_argument("--loaders", required=True, type=Path)
    parser.add_argument("--loader-sources", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    assert not args.output.exists()
    root = REPO / "out/test8-sticks-runtime-20261117"
    artifacts = {"module": pinned(root / "module-v3/h700_stick_axes.ko"),
                 "early_helper": pinned(args.helper),
                 "android_loader": pinned(REPO / "tools/input_profiles/stick_sampling_v2/rgsp-stick-axes.sh")}
    proofs = {"host": pinned(REPO / "tools/input_profiles/stick_sampling_v2/host-result.json"),
              "build": pinned(root / "module-v3/result.json"),
              "abi": pinned(root / "module-v3/kernel-abi.json"),
              "kernel_binding": pinned(root / "module-v3/kernel-binding.json"),
              "loaders": pinned(args.loaders),
              "memory": pinned(args.memory)}
    contents = {key: json.loads(Path(row["path"]).read_text()) for key, row in proofs.items()}
    module_sha = artifacts["module"]["sha256"]
    for key in ["build", "abi", "kernel_binding", "loaders"]:
        assert contents[key]["module_sha256"] == module_sha
    assert all(contents[key]["passed"] for key in ["host", "build", "kernel_binding", "loaders", "memory"])
    assert contents["loaders"]["source_sha256"]["h700_optional_axes.sh"] == artifacts["early_helper"]["sha256"]
    assert contents["loaders"]["source_sha256"]["rgsp-stick-axes.sh"] == artifacts["android_loader"]["sha256"]
    memory = contents["memory"]
    assert memory["schema"] == "roc.h700.swap2g-host.v1"
    assert memory["helper_sha256"] == artifacts["early_helper"]["sha256"]
    assert memory["swap_bytes"] == 2147483648 and memory["default_enabled"] is True
    assert memory["failure_nonfatal"] and memory["reuse_size_or_space_guard"] and memory["no_RAM_identity_gate"]
    assert memory["physical_acceptance"] is False and memory["actual_host_swapon"] is False
    controls = {}

    def control(path, value=None):
        path = Path(path)
        assert path.is_absolute() and path.is_file() and not path.is_symlink()
        actual = sha(path)
        if value is not None:
            assert actual == value
        assert str(path) not in controls or controls[str(path)] == actual
        controls[str(path)] = actual

    control(Path(__file__).resolve())
    for row in [*artifacts.values(), *proofs.values()]:
        control(row["path"], row["sha256"])
    for key in ["host", "build", "memory"]:
        for path, value in contents[key]["controls"].items():
            control(path, value)
    for name, value in contents["loaders"]["source_sha256"].items():
        control(args.loader_sources / name, value)
    for path in [root / "loaders-v1/provenance.json", root / "loaders-v1/actual-shell-tests/result.json",
                 REPO / "tools/input_profiles/stick_sampling_v2/test_loaders.py",
                 root / "vendor-poll-review-v1/result.json"]:
        control(path)
    provenance = json.loads((root / "loaders-v1/provenance.json").read_text())
    assert provenance["passed"] and provenance["module_sha256"] == module_sha
    for row in provenance["rows"]:
        control(row["parent_path"], row["parent_sha256"])
        control(row["candidate_path"], row["candidate_sha256"])
    args.output.mkdir(parents=True, exist_ok=False)
    candidate = {"schema": "roc.h700.stick-memory-candidate.v1", "passed": True,
                 "artifacts": artifacts, "proofs": proofs, "controls": controls,
                 "module_path": artifacts["module"]["path"], "module_sha256": module_sha,
                 "physical_acceptance": False, "no_RAM_identity_gate": True, "catalog_models": 12,
                 "default_swap_bytes": 2147483648,
                 "scope": "Test8 delta: independent stick gates/read-only recovery diagnostics and default 2GiB data swap",
                 "device_modified": False, "accepted_baseline_promoted": False}
    receipt = args.output / "candidate.json"
    receipt.write_text(json.dumps(candidate, indent=2) + "\n")
    manifest = {"schema": "roc.h700.stick-memory-inputs.v1", "inputs": artifacts,
                "candidate_receipt": pinned(receipt)}
    (args.output / "inputs.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"candidate": pinned(receipt), "manifest": pinned(args.output / "inputs.json"),
                      "controls": len(controls), "device_modified": False}, indent=2))


if __name__ == "__main__":
    main()

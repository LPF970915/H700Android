"""Record a checked source/module candidate, explicitly without a new image."""
from pathlib import Path
import hashlib
import json

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "out/stick-regression-repair-20261117-v1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    destination = OUT / "candidate.json"
    assert not destination.exists()
    sources = REPO / "tools/input_profiles/stick_recovery_v3"
    paths = {
        "host": OUT / "host-final/host-result.json",
        "module": OUT / "module-v1/result.json",
        "abi": OUT / "module-v1/kernel-abi.json",
        "kernel_binding": OUT / "module-v1/kernel-binding.json",
        "loaders": OUT / "loaders-v1/result.json",
        "integration": OUT / "integration-v2/result.json",
        "source_review": REPO / "out/stick-history-regression-20261117-v1/v3-source-review.json",
    }
    proofs = {key: json.loads(path.read_text()) for key, path in paths.items()}
    for key in ("host", "module", "kernel_binding", "loaders", "integration"):
        assert proofs[key]["passed"] is True
    module_path = OUT / "module-v1/h700_stick_axes.ko"
    module_sha = sha(module_path)
    for key in ("module", "abi", "kernel_binding", "loaders", "integration"):
        assert proofs[key]["module_sha256"] == module_sha
    for key in ("host", "module"):
        for name, value in proofs[key]["source_sha256"].items():
            assert sha(sources / name) == value
        for path, value in proofs[key]["controls"].items():
            assert sha(Path(path)) == value
    review = proofs["source_review"]
    assert not review["blockers"] and all(review["checks"].values())
    assert review["source_sha256"] == sha(sources / "h700_stick_axes.c")
    assert review["policy_sha256"] == sha(sources / "h700_profile_policy.h")
    assert proofs["integration"]["swap_prefix_byte_exact"] is True
    artifacts = {"module": module_path,
                 "early_helper": OUT / "integration-v2/h700_optional_axes.sh",
                 "android_loader": OUT / "integration-v2/rgsp-stick-axes.sh"}
    parent = json.loads((sources / "parent-inputs.json").read_text())
    for name, value in parent["parent_source_sha256"].items():
        assert sha(sources.parent / "stick_sampling_v2" / name) == value
    result = {
        "schema": "roc.h700.stick-regression-repair-candidate.v1",
        "software_checks_passed": True, "recorded_local_date": "2026-11-17",
        "status": "isolated compiled candidate; no new whole-card image",
        "artifacts": {key: {"path": str(path), "sha256": sha(path)}
                      for key, path in artifacts.items()},
        "proofs": {key: {"path": str(path), "sha256": sha(path)}
                   for key, path in paths.items()},
        "host_candidate_cases": proofs["host"]["candidate_scenarios"],
        "host_negative_control_cases": proofs["host"]["negative_control_scenarios"],
        "host_checks": proofs["host"]["checks"],
        "loader_cases": proofs["loaders"]["cases"],
        "all_twelve_profiles_retained": True, "default_swap_bytes": 2147483648,
        "swap_prefix_byte_exact": True, "parent_sources_preserved": True,
        "images_mutated": False, "new_whole_card_packaged": False,
        "device_accessed": False, "physical_acceptance": False,
        "exact_hardware_trigger_proven": False,
        "limitations": ["Hardware APIs are simulated in host tests.",
                        "No failure-time ADC/CCU/GPIO readback is available.",
                        "GPIO mux restoration and closed-clock acquisition are outside this repair.",
                        "No artifact was loaded on a device or used to replace Test9 bytes."],
        "controls": {str(Path(__file__).resolve()): sha(Path(__file__).resolve())},
    }
    destination.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

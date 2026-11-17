"""Copy the retained Test8 loaders, changing only the module SHA-256 pin.

The parent scripts and module are read-only. New candidate script paths must
not exist. This does not run any loader or access a device.
"""
from pathlib import Path
import argparse
import hashlib
import json

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
OLD_MODULE_SHA = "bc7a000ecc6ad0eaabe0cfb137ebb8b49f739b89b2473b5204ec67c437dae38f"
PARENT_SCRIPTS = {
    "h700_optional_axes.sh": "f956996047957692ca690fa67288ae5aed1ccbd15bae3b5f0baaf0b19662e9ed",
    "rgsp-stick-axes.sh": "9c729c31d34ce89ac716806254748e913f1bc540b763cfbabf5a6b7a29ec3ff2",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--module-sha256", required=True)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    module = args.module.resolve()
    assert module.is_file() and sha(module.read_bytes()) == args.module_sha256
    assert len(args.module_sha256) == 64
    assert all(c in "0123456789abcdef" for c in args.module_sha256)
    assert not args.receipt.exists()
    for name in PARENT_SCRIPTS:
        assert not (HERE / name).exists()
    rows = []
    for name, expected in PARENT_SCRIPTS.items():
        original_path = PARENT / name
        original = original_path.read_bytes()
        assert sha(original) == expected
        assert original.count(OLD_MODULE_SHA.encode()) == 1
        candidate = original.replace(OLD_MODULE_SHA.encode(), args.module_sha256.encode())
        assert len(candidate) == len(original)
        assert candidate.count(args.module_sha256.encode()) == 1
        assert candidate.replace(args.module_sha256.encode(), OLD_MODULE_SHA.encode()) == original
        path = HERE / name
        with path.open("xb") as output:
            output.write(candidate)
        assert path.read_bytes() == candidate
        assert original_path.read_bytes() == original
        rows.append({"parent_path": str(original_path), "parent_sha256": expected,
                     "candidate_path": str(path), "candidate_sha256": sha(candidate),
                     "only_change": "one literal module SHA-256 pin", "replacement_count": 1})
    result = {"schema": "roc.h700.stick-sampling-v2-loader-provenance.v1",
              "passed": True, "module_path": str(module),
              "module_sha256": args.module_sha256, "parents_unchanged": True,
              "loader_hardware_execution": False, "rows": rows,
              "generator_sha256": sha(Path(__file__).read_bytes())}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open("x") as output:
        output.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

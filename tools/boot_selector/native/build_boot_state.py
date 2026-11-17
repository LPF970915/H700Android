"""Build and validate boot-state helper only; never touch block devices."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir()
    args.output.mkdir(parents=True)
    source = Path(__file__).resolve().parent.parent / "boot_state.c"
    outputs = []
    for compiler, name, static in (("/usr/bin/cc", "boot-state-host", []),
                                   ("/usr/bin/aarch64-linux-gnu-gcc", "boot-state-aarch64", ["-static"])):
        binary = args.output / name
        subprocess.run([compiler, *static, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", source, "-o", binary], check=True)
        outputs.append({"path": str(binary), "bytes": binary.stat().st_size,
                        "sha256": hashlib.sha256(binary.read_bytes()).hexdigest()})
    subprocess.run([sys.executable, str(Path(__file__).with_name("test_boot_state.py")),
                    "--prefix", "/home/lpf/roc-os-h700-shared-panel-20261114-v1/prefix.shared.raw",
                    "--work", str(args.work / "fixtures"),
                    "--host", str(args.output / "boot-state-host"),
                    "--arm", str(args.output / "boot-state-aarch64"),
                    "--output", str(args.output / "tests.json")], check=True)
    tests = json.loads((args.output / "tests.json").read_text())
    record = {"pass": tests["pass"], "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "test_source_sha256": hashlib.sha256(Path(__file__).with_name("test_boot_state.py").read_bytes()).hexdigest(),
              "binaries": outputs, "tests": str(args.output / "tests.json"),
              "scope": "host+actual A64 helper tests on ordinary fixture files; no device/partition operation"}
    (args.output / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record))


if __name__ == "__main__":
    main()

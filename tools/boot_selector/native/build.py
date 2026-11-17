"""Build and exercise the isolated native menu under the caller's resource unit."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys


def run(args, *, capture=False):
    value = subprocess.run([str(x) for x in args], check=True, text=True,
                           stdout=subprocess.PIPE if capture else None)
    return value.stdout if capture else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--generated", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.work.exists():
        raise ValueError("New work directory required")
    args.work.mkdir(parents=True)
    args.output.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).with_name("selector.c")
    flags = ["-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-Wno-misleading-indentation",
             "-fstack-protector-strong", "-D_FORTIFY_SOURCE=2", "-I", args.generated,
             source]
    host = args.work / "roc-boot-selector-host"
    arm = args.work / "roc-boot-selector"
    run(["/usr/bin/cc", *flags, "-o", host])
    test = json.loads(run([host, "--selftest"], capture=True))
    if test.get("pass") is not True:
        raise ValueError("Native selftest did not pass")
    run(["/usr/bin/aarch64-linux-gnu-gcc", "-static", *flags, "-o", arm])
    arm_test = json.loads(run(["/usr/bin/qemu-aarch64", arm, "--selftest"], capture=True))
    if arm_test != test:
        raise ValueError("Actual aarch64 ELF behavior differs from host")
    elf = run(["/usr/bin/readelf", "-h", "-l", arm], capture=True)
    if "AArch64" not in elf or "INTERP" in elf:
        raise ValueError("Expected static AArch64 ELF")
    (args.output / "elf.txt").write_text(elf)
    boot_state_source = source.parent.parent / "boot_state.c"
    boot_state_binaries = []
    if boot_state_source.is_file():
        for compiler, name, static in (("/usr/bin/cc", "boot-state-host", []),
                                       ("/usr/bin/aarch64-linux-gnu-gcc", "boot-state-aarch64", ["-static"])):
            target = args.output / name
            if target.exists():
                raise ValueError("Refusing to replace previous boot state helper")
            run([compiler, *static, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", boot_state_source, "-o", target])
            boot_state_binaries.append({"path": str(target), "bytes": target.stat().st_size,
                                        "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    previews = []
    for geometry in ("640x480", "720x480", "720x720"):
        ppm = args.output / f"menu-{geometry}.ppm"
        run([host, "--simulate", geometry, "--ppm", ppm])
        previews.append(ppm.name)
    result_path = args.output / "simulated-selection.json"
    run([arm.parent / "roc-boot-selector-host", "--simulate", "640x480", "--ppm",
         args.output / "menu-confirmed.ppm", "--initial", "rg35xxh", "--script", "DADA", "--result", result_path])
    selection = json.loads(result_path.read_text())
    if selection != {"schema": 2, "model_id": "rg35xxh", "save_default": True}:
        raise ValueError("Unexpected explicit simulated confirmation")
    for binary in (host, arm):
        target = args.output / binary.name
        if target.exists():
            raise ValueError("Refusing to replace previous output binary")
        target.write_bytes(binary.read_bytes())
        target.chmod(0o755)
    hashes = {}
    for path in (source, Path(__file__), args.generated / "assets.h", args.output / arm.name):
        hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    record = {"pass": True, "host_test": test, "actual_aarch64_test": arm_test,
              "selection": selection, "previews": previews, "sha256": hashes,
              "arm_bytes": arm.stat().st_size, "static": True,
              "boot_state_binaries": boot_state_binaries,
              "scope": "native menu component only; no physical panel, input or boot integration accepted"}
    (args.output / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record))


if __name__ == "__main__":
    main()

"""Build and exercise the isolated native menu under the caller's resource unit."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys

from models import MODEL_METADATA
from test_native_rescue import exercise


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
    source = Path(__file__).with_name("selector_rescue.c")
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
    boot_state_source = source.with_name("boot_state_preview.c")
    boot_state_binaries = []
    if boot_state_source.is_file():
        for architecture, compiler, name, static in (("host", "/usr/bin/cc", "boot-state-host", []),
                                       ("aarch64", "/usr/bin/aarch64-linux-gnu-gcc", "boot-state-aarch64", ["-static"])):
            target = args.output / name
            if target.exists():
                raise ValueError("Refusing to replace previous boot state helper")
            run([compiler, *static, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", boot_state_source, "-o", target])
            boot_state_binaries.append({"architecture": architecture, "path": str(target), "bytes": target.stat().st_size,
                                        "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    helper_test = source.with_name('test_boot_state_preview.py')
    helper_tests = args.output / 'boot-state-tests.json'
    run([sys.executable, helper_test,
         '--prefix', '/home/lpf/roc-os-h700-shared-panel-20261114-v1/prefix.shared.raw',
         '--work', args.work / 'boot-state-fixtures', '--host', args.output / 'boot-state-host',
         '--arm', args.output / 'boot-state-aarch64', '--output', helper_tests])
    helper_result = json.loads(helper_tests.read_text())
    helper_controls = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in
        (boot_state_source, helper_test, Path(__file__), helper_tests,
         args.output / 'boot-state-host', args.output / 'boot-state-aarch64')}
    helper_record = {'schema': 'roc.h700.boot-state-preview.v1', 'pass': helper_result['pass'],
        'source': str(boot_state_source), 'source_sha256': helper_controls[str(boot_state_source)],
        'artifact': str(args.output / 'boot-state-aarch64'),
        'artifact_sha256': helper_controls[str(args.output / 'boot-state-aarch64')],
        'preview_keeps_saved_default': True, 'preview_next_start': '2',
        'binaries': boot_state_binaries, 'rows': helper_result['architectures'],
        'controls': helper_controls, 'hardware_accessed': False}
    (args.output / 'boot-state-preview.json').write_text(json.dumps(helper_record, indent=2) + '\n')
    previews = []
    for geometry in ("640x480", "720x480", "720x720", "480x640"):
        ppm = args.output / f"menu-{geometry}.ppm"
        run([host, "--simulate", geometry, "--ppm", ppm])
        previews.append(ppm.name)
        loading = args.output / f"loading-{geometry}.ppm"
        run([host, "--loading-only", "--simulate", geometry, "--ppm", loading])
        arm_loading = args.output / f"loading-aarch64-{geometry}.ppm"
        run(["/usr/bin/qemu-aarch64", arm, "--loading-only", "--simulate", geometry, "--ppm", arm_loading])
        if arm_loading.read_bytes() != loading.read_bytes():
            raise ValueError("Loading-only render differs between host and actual AArch64")
        previews.append(loading.name)
    result_path = args.output / "simulated-selection.json"
    run([arm.parent / "roc-boot-selector-host", "--simulate", "640x480", "--ppm",
         args.output / "menu-confirmed.ppm", "--initial", "rg35xxh", "--script", "DADA", "--result", result_path])
    selection = json.loads(result_path.read_text())
    if selection != {"schema": 2, "model_id": "rg35xxh", "save_default": True}:
        raise ValueError("Unexpected explicit simulated confirmation")
    if (args.output / "menu-confirmed.ppm").read_bytes() != (args.output / "loading-640x480.ppm").read_bytes():
        raise ValueError("Accepted menu and loading-only must leave the same frame")
    loading_rejects = []
    for command in ([host], ["/usr/bin/qemu-aarch64", arm]):
        for forbidden in ("--output", "--input-directory", "--inputs"):
            absent = args.output / ("must-not-create-" + forbidden[2:])
            check = subprocess.run([*map(str, command), "--loading-only", forbidden, str(absent)],
                                   capture_output=True, text=True)
            if check.returncode != 2 or absent.exists() or "open framebuffer" in check.stderr:
                raise ValueError("Loading-only must reject input/result before opening framebuffer")
            loading_rejects.append({"command": list(map(str, command)), "forbidden": forbidden, "pass": True})
    loading_cases = []
    for model, metadata in MODEL_METADATA.items():
        width, height = metadata['native_size']
        geometry = f"{width}x{height}"
        rendered = []
        for architecture, command in (("host", [host]), ("aarch64", ["/usr/bin/qemu-aarch64", arm])):
            target = args.output / f"loading-{model}-{architecture}.ppm"
            run([*command, "--loading-only", "--simulate", geometry, "--ppm", target,
                 "--initial-model", model, "--rotation", str(metadata['display_rotation'])])
            rendered.append(target.read_bytes())
            loading_cases.append({"model": model, "architecture": architecture,
                "native_size": [width, height], "rotation": metadata['display_rotation'],
                "ppm_sha256": hashlib.sha256(rendered[-1]).hexdigest(),
                "no_input_or_selection_arguments": True, "pass": True})
        if rendered[0] != rendered[1]:
            raise ValueError("Per-model loading render differs across architectures")
    for binary in (host, arm):
        target = args.output / binary.name
        if target.exists():
            raise ValueError("Refusing to replace previous output binary")
        target.write_bytes(binary.read_bytes())
        target.chmod(0o755)
    hashes = {}
    for path in (source, Path(__file__), source.with_name('generate_assets_rescue.py'),
                 source.with_name('test_native_rescue.py'), source.with_name('models.py'),
                 source.parent.parent / 'reference_model.py', args.generated / "assets.h",
                 args.output / host.name, args.output / arm.name):
        hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    rescue = exercise(args.output / host.name, args.output / arm.name, args.output / 'rescue-fixtures',
                      args.work / 'fifo-fixtures')
    record = {"pass": True, "host_test": test, "actual_aarch64_test": arm_test,
              "selection": selection, "previews": previews, "sha256": hashes,
              "arm_bytes": arm.stat().st_size, "static": True,
              "boot_state_binaries": boot_state_binaries,
              "loading_only_rejections": loading_rejects,
              "loading_only_cases": loading_cases,
              "loading_only_models": len(MODEL_METADATA),
              "loading_text": "加载中，请稍后",
              "loading_only_has_no_input_or_result": True,
              "manual_panel_recovery": True, "preview_exit_code": 4,
              "preview_profiles": 3, "catalog_electrical_profiles": 10,
              "volume_press_release_guard": True, "rescue": rescue, "controls": hashes,
              "scope": "native menu component only; no physical panel, input or boot integration accepted"}
    (args.output / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record))


if __name__ == "__main__":
    main()

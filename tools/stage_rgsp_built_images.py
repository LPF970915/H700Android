#!/usr/bin/env python3
"""Stage fresh built images separately; leave all previous preflight packages untouched."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from android_sparse_to_raw import convert
from prepare_rgsp_wifi_deployment import sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--product", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, product, output = args.workspace.resolve(), args.product.resolve(), args.output.resolve()
    if not output.is_relative_to(root / "out") or output == root / "out" or output.exists():
        raise ValueError("Output must be a new directory strictly inside workspace out")
    if shutil.disk_usage(root).free < 120 * 1024**3:
        raise ValueError("Less than 120 GiB free: stop before image staging")
    apk = root / "out/h700-android10-preflight/AT4K-launcher.apk"
    if sha(apk) != "1315ef01d56511a80cb6bb4b9c58bfd3233c0e84cc1e82254cd0898d5dd26ca9":
        raise ValueError("User-supplied AT4K APK hash mismatch")
    for name in ("system.img", "vendor.img", "ramdisk.img"):
        if not (product / name).is_file():
            raise ValueError(f"Missing build artifact: {name}")
    output.mkdir()
    for name in ("system.img", "vendor.img", "ramdisk.img"):
        shutil.copyfile(product / name, output / name)
    shutil.copyfile(apk, output / "AT4K-launcher.apk")
    checks = []
    for name, size in (("system", 8589934592), ("vendor", 2147483648)):
        image = output / f"{name}.raw.img"
        convert(str(output / f"{name}.img"), str(image))
        if image.stat().st_size != size:
            raise ValueError(f"Unexpected {name} partition size")
        result = subprocess.run(["e2fsck", "-fn", str(image)], text=True, capture_output=True)
        (output / f"{name}.fsck.txt").write_text(result.stdout + result.stderr)
        if result.returncode != 0:
            raise ValueError(f"Filesystem check failed: {name}, {result.returncode}")
        checks.append({"image": image.name, "e2fsck_exit": result.returncode})
    manifest = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "writes_performed": False,
        "product": "h700_rgsp-eng",
        "ext4_checks": checks,
        "artifacts": {p.name: {"bytes": p.stat().st_size, "sha256": sha(p)}
                      for p in sorted(output.iterdir()) if p.is_file()},
    }
    (output / "DEPLOYMENT_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"STAGED_PREFLIGHT={output}")


if __name__ == "__main__":
    main()

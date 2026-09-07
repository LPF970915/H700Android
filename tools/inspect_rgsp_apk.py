#!/usr/bin/env python3
"""Offline APK triage for the API29 ARM32 RGSP; never installs or executes an APK."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import zipfile

from prepare_rgsp_wifi_deployment import sha


def parse_badging(text):
    result = {}
    for line in text.splitlines():
        if line.startswith("package:"):
            result.update(dict(re.findall(r"(\w+)='([^']*)'", line)))
        for prefix, key in (("sdkVersion:", "min_sdk"), ("targetSdkVersion:", "target_sdk"),
                            ("maxSdkVersion:", "max_sdk")):
            if line.startswith(prefix):
                match = re.fullmatch(re.escape(prefix) + r"'([^']+)'", line)
                if not match:
                    raise ValueError(f"Malformed {prefix}")
                result[key] = match[1]
    if "name" not in result:
        raise ValueError("No package identity in aapt2 output")
    # Android defaults minSdkVersion to 1 when uses-sdk is absent.
    result.setdefault("min_sdk", "1")
    result["required_features"] = re.findall(r"^\s*uses-feature: name='([^']+)'", text, re.M)
    result["permissions"] = re.findall(r"^uses-permission: name='([^']+)'", text, re.M)
    return result


def assess(metadata, abis, required_splits=False):
    blockers, warnings = [], []
    minimum = metadata["min_sdk"]
    if not minimum.isdecimal() or int(minimum) > 29:
        blockers.append("Minimum Android API is not supported by API 29")
    if abis and not set(abis).intersection(("armeabi", "armeabi-v7a")):
        blockers.append("No ARM32 native libraries in this APK")
    if metadata.get("split"):
        blockers.append("Split APK: needs the matching base and other required splits")
    if required_splits:
        warnings.append("Manifest requests split APKs; completeness must be checked")
    if "max_sdk" in metadata:
        warnings.append("maxSdkVersion declared; check distribution/runtime compatibility")
    warnings.extend([
        "Signature, installed-package version conflicts and runtime behavior are not verified",
        "GMS, DRM, network, touch/DPAD, audio and memory requirements need individual testing",
        "Required feature declarations are not proof that this RGSP provides those features",
    ])
    return {
        "static_candidate": not blockers and not required_splits,
        "blockers": blockers, "warnings": warnings,
        "runtime_verified": False, "signature_verified": False,
    }


def inspect(path, aapt2):
    path = path.resolve(strict=True)
    if not path.is_file() or path.suffix.lower() != ".apk":
        raise ValueError("Supply a regular .apk; .apks/.xapk/.apkm are containers, not single APKs")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP entries require manual review")
        if "AndroidManifest.xml" not in names:
            raise ValueError("Missing AndroidManifest.xml")
        abis = sorted({p.split("/")[1] for p in names
                       if p.startswith("lib/") and len(p.split("/")) == 3 and p.endswith(".so")})
    badging = subprocess.check_output([str(aapt2), "dump", "badging", str(path)], text=True,
                                     stderr=subprocess.PIPE, timeout=60)
    xml = subprocess.check_output([str(aapt2), "dump", "xmltree", str(path),
                                   "--file", "AndroidManifest.xml"], text=True,
                                  stderr=subprocess.PIPE, timeout=60)
    metadata = parse_badging(badging)
    required_splits = "E: uses-split" in xml or bool(
        re.search(r"isSplitRequired.*(?:0xffffffff|true)", xml))
    return {"file": path.name, "sha256": sha(path), "bytes": path.stat().st_size,
            "metadata": metadata, "native_abis": abis,
            **assess(metadata, abis, required_splits)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aapt2", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("apks", type=Path, nargs="+")
    args = parser.parse_args()
    results = [inspect(path, args.aapt2) for path in args.apks]
    text = json.dumps(results, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        if args.output.exists():
            raise ValueError("Refusing to overwrite an existing report")
        args.output.write_text(text)
    print(text)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Package three reviewed codec XMLs into a NEW local copy of frozen Fix72.

Default is hash/path preflight only. Never opens a physical device, contacts
the handheld, builds Android, or changes the frozen recovery images.
"""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from compare_rgsp_image_files import inventory
from prepare_rgsp_wifi_deployment import run, sha


IMAGE_BYTES = 2147483648
BASELINE_SHA = "cb65140203807d0d80408e314f0c76554f2f81cd13fc76bf8ef07a4e46243c34"
BUILD_SHA = "ad6b909daec8607376425f5dde01992c41dee10e52a762c6e8a17db6f87c45e0"
CHECKS_SHA = "e2f7a4172d219276365b64c317dac9b6c9a41f48f528c4d72a8400bd4ed4769b"
XML_HASHES = {
    "media_codecs.xml": "152e5797f0b9a27101faf43614b438f6b75022e9c24423e333582dccbbaed3b4",
    "media_codecs_google_audio.xml": "f33464aee38c30e1fe52764bdb1d98ccd56a8214618d03b061b0fd63c38b0000",
    "media_codecs_google_video.xml": "876f5f850cbb5ce4f7a9582654ce006888903e6016dd0b8053e61ab0fd993839",
}


def new_output(root, requested):
    output = requested.resolve()
    if not output.is_relative_to(root / "out") or output == root / "out":
        raise ValueError("Output must be inside workspace out")
    if requested.is_symlink() or output.exists():
        raise ValueError("Refusing to overwrite an existing path")
    return output


def verify_image(path, expected):
    if not path.is_file() or path.is_symlink() or path.stat().st_size != IMAGE_BYTES:
        raise ValueError(f"Not a regular, fixed-size image: {path}")
    if sha(path) != expected:
        raise ValueError(f"Image hash mismatch: {path}")


def attributes(path):
    return {key: os.getxattr(path, key, follow_symlinks=False).hex()
            for key in sorted(os.listxattr(path, follow_symlinks=False))}


def full_inventory(root):
    entries = inventory(root)
    info = root.stat()
    entries["."] = {"directory": True, "mode": stat.S_IMODE(info.st_mode),
                    "uid": info.st_uid, "gid": info.st_gid}
    for rel, entry in entries.items():
        entry["xattrs"] = attributes(root / rel)
    return entries


def check_delta(before, after, payload):
    expected_paths = {f"etc/{name}" for name in XML_HASHES}
    changes = {p for p in before.keys() | after.keys()
               if before.get(p) != after.get(p)}
    if changes != expected_paths or expected_paths & before.keys():
        raise ValueError(f"Unexpected vendor changes: {sorted(changes)}")
    for path in sorted(expected_paths):
        if after[path] != payload[path]:
            raise ValueError(f"Payload content/metadata mismatch: {path}")
    return [{"path": p, "before": None, "after": after[p]} for p in sorted(changes)]


def check_xml(directory):
    for name, expected in XML_HASHES.items():
        path = directory / name
        if path.is_symlink() or not path.is_file() or sha(path) != expected:
            raise ValueError(f"Codec payload mismatch: {name}")
        tree = ET.parse(path).getroot()
        if name == "media_codecs.xml":
            if tree.tag != "MediaCodecs" or [(e.tag, e.attrib) for e in tree] != [
                ("Include", {"href": "media_codecs_google_audio.xml"}),
                ("Include", {"href": "media_codecs_google_video.xml"}),
            ]:
                raise ValueError("Unexpected root catalog imports")
        elif tree.tag != "Included" or list(tree.iter("Include")):
            raise ValueError(f"Unexpected nested catalog: {name}")


def check_filesystem(image, report):
    result = subprocess.run(["e2fsck", "-fn", str(image)], text=True, capture_output=True)
    report.write_text(result.stdout + result.stderr)
    if result.returncode != 0:
        raise ValueError(f"Read-only fsck failed ({result.returncode}); see {report}")


@contextmanager
def mounted(image, target, writable=False):
    if not image.is_file() or image.is_symlink():
        raise ValueError("Only regular image files may be mounted")
    target.mkdir()
    options = "loop,rw" if writable else "loop,ro,noload"
    run("mount", "-t", "ext4", "-o", options, str(image), str(target))
    try:
        yield target
    finally:
        run("umount", str(target))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    root = args.workspace.resolve(strict=True)
    output = new_output(root, args.output)
    baseline = root / "out/rgsp-fix72-wifi-profile/vendor.raw.img"
    build = root / "out/rgsp-fix72-codec-probe-20260908/vendor.build.raw.img"
    checks = root / "out/rgsp-fix72-wifi-profile/CONTENT_CHECKS.json"
    for path in (baseline, build, checks):
        if not path.resolve(strict=True).is_relative_to(root / "out"):
            raise ValueError("Input escaped workspace out")
    verify_image(baseline, BASELINE_SHA)
    verify_image(build, BUILD_SHA)
    if sha(checks) != CHECKS_SHA:
        raise ValueError("Frozen component manifest changed")
    if not args.prepare:
        print("CODEC_CANDIDATE_PREFLIGHT_OK: no files written or mounted")
        return
    if os.geteuid() != 0:
        raise ValueError("Local image mounting requires root")
    if shutil.disk_usage(root).free - IMAGE_BYTES < 120 * 1024**3:
        raise ValueError("Copy would cross the 120 GiB free-space floor")
    output.mkdir()
    candidate = output / "vendor.raw.img"
    run("cp", "--sparse=always", "--", str(baseline), str(candidate))
    verify_image(candidate, BASELINE_SHA)
    for label, image in (("baseline", baseline), ("build", build), ("candidate-before", candidate)):
        check_filesystem(image, output / f"{label}.fsck.txt")
    with tempfile.TemporaryDirectory(prefix="rgsp-codec-candidate-") as temp:
        temp = Path(temp)
        with mounted(build, temp / "built") as source:
            check_xml(source / "etc")
            source_entries = full_inventory(source)
            payload = {f"etc/{name}": source_entries[f"etc/{name}"] for name in XML_HASHES}
            with mounted(candidate, temp / "candidate", writable=True) as target:
                before = full_inventory(target)
                for name in XML_HASHES:
                    src, dst = source / "etc" / name, target / "etc" / name
                    if os.path.lexists(dst):
                        raise ValueError(f"Existing catalog must not be replaced: {name}")
                    with src.open("rb") as reader, dst.open("xb") as writer:
                        shutil.copyfileobj(reader, writer)
                    info = src.stat()
                    os.chown(dst, info.st_uid, info.st_gid)
                    os.chmod(dst, stat.S_IMODE(info.st_mode))
                    for key in os.listxattr(src):
                        os.setxattr(dst, key, os.getxattr(src, key))
                check_delta(before, full_inventory(target), payload)
        check_filesystem(candidate, output / "candidate-after.fsck.txt")
        with mounted(candidate, temp / "verified") as target:
            check_xml(target / "etc")
            changes = check_delta(before, full_inventory(target), payload)
            for entry in json.loads(checks.read_text()):
                if entry["partition"] == "vendor" and sha(target / entry["path"]) != entry["sha256"]:
                    raise ValueError(f"Frozen vendor component changed: {entry['path']}")
    verify_image(baseline, BASELINE_SHA)
    verify_image(build, BUILD_SHA)
    shutil.copyfile(Path(__file__), output / "prepare-executed.py")
    for name in ("compare_rgsp_image_files.py", "prepare_rgsp_wifi_deployment.py"):
        shutil.copyfile(Path(__file__).parent / name, output / name)
    manifest = {
        "created": datetime.now(timezone.utc).isoformat(),
        "status": "OFFLINE_VERIFIED_NOT_DEPLOYED",
        "baseline_vendor_sha256": BASELINE_SHA,
        "built_vendor_sha256": BUILD_SHA,
        "frozen_content_checks_sha256": CHECKS_SHA,
        "vendor": {"bytes": candidate.stat().st_size, "sha256": sha(candidate)},
        "changes": changes,
        "comparison": "All paths, contents, modes, uid/gid, symlink targets and xattrs; not timestamps",
        "system": "Reuse unchanged frozen Fix72; no system image copied or modified",
        "recovery": "Frozen vendor remains intact; physical rollback requires guarded deployment",
        "device_writes": False,
        "gates": [
            "Persistent deployment and runtime verification required",
            "RAM trial used /vendor/odm/etc; candidate uses build's /vendor/etc",
            "No boot, cold-start, audio/video or physical-button acceptance implied",
            "Not an input for the existing two-partition deploy or boot-only helpers",
        ],
        "recipe_sha256": sha(output / "prepare-executed.py"),
        "recipe_dependencies": {name: sha(output / name) for name in (
            "compare_rgsp_image_files.py", "prepare_rgsp_wifi_deployment.py")},
    }
    (output / "CANDIDATE_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"CODEC_CANDIDATE_OFFLINE_VERIFIED={output}")
    print(f"VENDOR_SHA256={manifest['vendor']['sha256']}")


if __name__ == "__main__":
    main()

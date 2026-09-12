#!/usr/bin/env python3
"""Merge three built audio fixes into a new, frozen-codec vendor copy."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from prepare_rgsp_codec_candidate import (
    IMAGE_BYTES, check_filesystem, full_inventory, mounted, new_output,
    verify_image,
)
from prepare_rgsp_wifi_deployment import sha

BASELINE_SHA = "1e1c90ffdc6fc08e7e40d333d3fab4ea065c19a34df38b4a0889bcc83a8dc891"
FILES = {
    "etc/audio_mixer_paths.xml": "configs/audio_mixer_paths.xml",
    "ueventd.rc": "ueventd.rgsp.rc",
    "bin/rgsp-input-prepare.sh": "rgsp-input-prepare.sh",
}
SWITCHES = {
    "LINEOUT Switch", "SPK Switch", "OutputL Mixer DACL Switch",
    "OutputL Mixer DACR Switch", "OutputR Mixer DACL Switch",
    "OutputR Mixer DACR Switch",
}


def validate_route(path):
    root = ET.parse(path).getroot()
    if root.tag != "mixer":
        raise ValueError("Not a mixer document")
    gains = {"digital volume": "63", "lineout volume": "31"}
    for ctl in root.iter("ctl"):
        name, value = ctl.get("name"), ctl.get("value")
        if name in SWITCHES:
            if value not in ("0", "1"):
                raise ValueError("Invalid switch value")
        elif name not in gains or value != gains[name]:
            raise ValueError("Unqualified gain/control")
    defaults = {c.get("name"): c.get("value") for c in root.findall("ctl")}
    if any(defaults.get(name) != "0" for name in SWITCHES):
        raise ValueError("All routes must default off")
    paths = {p.get("name"): p for p in root.findall("path")}
    if set(paths) != {"media-speaker", "media-single-speaker", "null"}:
        raise ValueError("Unqualified route")
    stereo = {c.get("name"): c.get("value")
              for c in paths["media-speaker"].findall("ctl")}
    if stereo != {name: "1" for name in (
            "OutputL Mixer DACL Switch", "OutputR Mixer DACR Switch",
            "LINEOUT Switch", "SPK Switch")}:
        raise ValueError("Speaker path differs from audible trial")
    if [p.attrib for p in paths["media-single-speaker"]] != [{"name": "media-speaker"}]:
        raise ValueError("Single speaker alias mismatch")
    if list(paths["null"]):
        raise ValueError("Null path must remain empty")


def validate_changes(before, after, expected_hashes):
    changes = {p for p in before.keys() | after.keys()
               if before.get(p) != after.get(p)}
    if changes != set(FILES):
        raise ValueError(f"Unexpected image changes: {sorted(changes)}")
    for path in FILES:
        if not before.get(path) or not after.get(path):
            raise ValueError("Existing files only")
        expected = dict(before[path], sha256=expected_hashes[path])
        if after[path] != expected:
            raise ValueError(f"Content/metadata mismatch: {path}")
    return [{"path": p, "before": before[p], "after": after[p]}
            for p in sorted(changes)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.workspace.resolve(strict=True)
    baseline = root / "out/rgsp-fix72-codec-candidate-20260908/vendor.raw.img"
    built = args.build.resolve(strict=True)
    output = new_output(root, args.output)
    if not built.is_relative_to(root / "out"):
        raise ValueError("Build input must be a local out image")
    if os.geteuid() != 0:
        raise ValueError("Local loop mounts require root")
    # Three-file repack, not a full Android build: two images plus rollback space.
    if shutil.disk_usage(root).free < 12 * 1024**3:
        raise ValueError("Need 12 GiB free for this bounded vendor-only repack")
    verify_image(baseline, BASELINE_SHA)
    build_sha = sha(built)
    verify_image(built, build_sha)
    sources = root / "android/h700-android10/device/roc/rgsp"
    validate_route(sources / FILES["etc/audio_mixer_paths.xml"])
    expected = {rel: sha(sources / src) for rel, src in FILES.items()}
    output.mkdir()
    check_filesystem(baseline, output / "baseline.fsck.txt")
    check_filesystem(built, output / "build.fsck.txt")
    candidate = output / "vendor.raw.img"
    subprocess.run(["cp", "--sparse=always", "--", str(baseline), str(candidate)],
                   check=True)
    verify_image(candidate, BASELINE_SHA)
    with tempfile.TemporaryDirectory(prefix="rgsp-audio-candidate-") as temp:
        temp = Path(temp)
        with mounted(built, temp / "built") as source:
            for rel in FILES:
                if (source / rel).is_symlink() or sha(source / rel) != expected[rel]:
                    raise ValueError(f"Built image does not contain source fix: {rel}")
            with mounted(candidate, temp / "candidate", writable=True) as target:
                before = full_inventory(target)
                for rel in FILES:
                    dst = target / rel
                    if dst.is_symlink() or not dst.is_file():
                        raise ValueError(f"Unexpected baseline file type: {rel}")
                    # Truncate the existing inode to preserve mode, owner and xattrs.
                    with (source / rel).open("rb") as reader, dst.open("wb") as writer:
                        shutil.copyfileobj(reader, writer)
                validate_changes(before, full_inventory(target), expected)
        check_filesystem(candidate, output / "candidate.fsck.txt")
        with mounted(candidate, temp / "verified") as target:
            changes = validate_changes(before, full_inventory(target), expected)
            validate_route(target / "etc/audio_mixer_paths.xml")
    verify_image(baseline, BASELINE_SHA)
    verify_image(built, build_sha)
    result = {
        "created": datetime.now(timezone.utc).isoformat(),
        "status": "OFFLINE_VERIFIED_NOT_DEPLOYED", "device_writes": False,
        "baseline_vendor_sha256": BASELINE_SHA, "built_vendor_sha256": build_sha,
        "vendor": {"bytes": IMAGE_BYTES, "sha256": sha(candidate)},
        "changes": changes, "source_hashes": expected,
        "comparison": "All paths/content/modes/uid/gid/xattrs/symlinks; excludes times",
        "scope": "TF2 p3 only; preserve current codec baseline, system and user data",
        "gates": ["Fresh card backup", "Full readback", "Boot without live overrides",
                  "QQ Music playback", "Headphones/HDMI/capture remain unqualified"],
    }
    (output / "CANDIDATE_MANIFEST.json").write_text(json.dumps(result, indent=2) + "\n")
    for name in ("prepare_rgsp_audio_candidate.py", "prepare_rgsp_codec_candidate.py",
                 "compare_rgsp_image_files.py", "prepare_rgsp_wifi_deployment.py"):
        shutil.copyfile(Path(__file__).parent / name, output / name)
    print(json.dumps(result["vendor"]))
    print("AUDIO_CANDIDATE_OFFLINE_VERIFIED_NOT_DEPLOYED")


if __name__ == "__main__":
    main()

"""Extract pinned primary panel reference files into an ordinary evidence folder.

This does not implement a runtime panel resolver, edit an image, or touch a
device/card. Binary references are preserved as whole files; their presence
does not imply their command programs have been integrated or physically tested.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import argparse
import hashlib
import json
import re
import struct
from urllib.request import Request, urlopen

PIN = "57afa662009641d181f57241bcc480119b131530"
ROOT_URL = f"https://raw.githubusercontent.com/knulli-cfw/knulli-linux/{PIN}/"
MODELS = {
    "rg34xx": "rg34xx", "rg34xxsp": "rg34xx-sp", "rgcubexx": "rg-cubexx",
    "rg35xxplus": "rg35xx-plus", "rg28xx": "rg28xx", "rg35xxh": "rg35xx-h",
    "rg40xxh": "rg40xx-h", "rg40xxv": "rg40xx-v", "rg35xxsp": "rg35xx-sp",
    "rg35xxpro": "rg35xx-pro",
}
LEAF_NAMES = ("lcd0@01c0c000", "rgb24@0", "rgb24@1", "pwm0@0", "pwm0@1")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_node(text, name):
    matches = list(re.finditer(r"^\s*" + re.escape(name) + r"\s*\{", text, re.M))
    if len(matches) != 1:
        raise ValueError(f"Expected one leaf {name}; found {len(matches)}")
    start = matches[0].end()
    end = text.find("}", start)
    if end < start or "{" in text[start:end]:
        raise ValueError("Expected simple leaf node")
    rows = {}
    for statement in text[start:end].split(";"):
        if not statement.strip():
            continue
        match = re.fullmatch(r"\s*([A-Za-z0-9_,#+.@-]+)\s*(?:=\s*(.*))?\s*", statement, re.S)
        if match is None or match[1] in rows:
            raise ValueError("Unsupported/duplicate DTS property")
        key, value = match[1], match[2]
        if value is None:
            rows[key] = {"raw_hex": "", "empty": True}
        elif value.strip().startswith("<"):
            value = value.strip()
            if not value.endswith(">"):
                raise ValueError("Unterminated DTS integer list")
            numbers = value[1:-1].split()
            if not all(re.fullmatch(r"0x[0-9a-fA-F]+|[0-9]+", n) for n in numbers):
                raise ValueError("Unsupported DTS numeric token")
            numbers = [int(n, 0) for n in numbers]
            rows[key] = {"raw_hex": b"".join(struct.pack(">I", n) for n in numbers).hex(), "u32": numbers}
        else:
            strings = re.findall(r'"(?:[^"\\]|\\.)*"', value)
            if not strings or re.sub(r'"(?:[^"\\]|\\.)*"|[\s,]', "", value):
                raise ValueError("Unsupported DTS string property")
            strings = [json.loads(s) for s in strings]
            rows[key] = {"raw_hex": b"".join(s.encode() + b"\0" for s in strings).hex(), "strings": strings}
    return rows


def fetch_one(args):
    output, path, expected_git_sha = args
    target = output / "primary" / path
    url = ROOT_URL + path
    request = Request(url, headers={"User-Agent": "ROC-H700-panel-reference-audit"})
    with urlopen(request, timeout=60) as response:
        raw = response.read()
    git_sha = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    if git_sha != expected_git_sha:
        raise ValueError("Primary Git blob mismatch: " + path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() != raw:
        raise ValueError("Refuse to replace differing evidence: " + str(target))
    target.write_bytes(raw)
    return path, {"url": url, "git_blob_sha1": git_sha, "sha256": sha(raw), "bytes": len(raw), "file": str(target)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--tree", type=Path, required=True)
    args = parser.parse_args()
    tree_raw = args.tree.read_bytes()
    tree = json.loads(tree_raw)
    if tree.get("truncated") or tree.get("sha") != PIN:
        raise ValueError("Complete pinned Git tree required")
    blobs = {row["path"]: row["sha"] for row in tree["tree"] if row["type"] == "blob"}
    jobs = []
    for board in MODELS.values():
        for filename in (board + ".dts", "u-boot.bin"):
            path = f"package/boot/uboot-h700/{board}/boot_package/{filename}"
            if path not in blobs:
                raise ValueError("Missing primary reference " + path)
            jobs.append((args.output, path, blobs[path]))
    with ThreadPoolExecutor(max_workers=3) as pool:
        files = dict(pool.map(fetch_one, jobs))
    profiles = {}
    for model_id, board in MODELS.items():
        dts = f"package/boot/uboot-h700/{board}/boot_package/{board}.dts"
        uboot = f"package/boot/uboot-h700/{board}/boot_package/u-boot.bin"
        text = Path(files[dts]["file"]).read_text(encoding="utf-8")
        nodes = {name: source_node(text, name) for name in LEAF_NAMES}
        lcd = nodes["lcd0@01c0c000"]
        driver = lcd["lcd_driver_name"]["strings"][0]
        binary = Path(files[uboot]["file"]).read_bytes()
        name_bytes = driver.encode() + b"\0"
        offsets = [i for i in range(len(binary)) if binary.startswith(name_bytes, i)]
        registrations = []
        for offset in offsets:
            if offset % 4 == 0 and offset + 52 <= len(binary):
                callbacks = struct.unpack_from("<5I", binary, offset + 32)
                if all((value & 1) and 0x4a000000 <= value < 0x4a100000 for value in callbacks[:4]):
                    registrations.append({"offset": offset, "callbacks_thumb": [hex(v) for v in callbacks]})
        profiles[model_id] = {
            "source_board": board, "dts_file": files[dts], "u_boot_file": files[uboot],
            "geometry": f"{lcd['lcd_x']['u32'][0]}x{lcd['lcd_y']['u32'][0]}",
            "native_geometry": f"{lcd['lcd_x']['u32'][0]}x{lcd['lcd_y']['u32'][0]}",
            "logical_geometry": "640x480" if model_id == "rg28xx" else f"{lcd['lcd_x']['u32'][0]}x{lcd['lcd_y']['u32'][0]}",
            "rotation_required": model_id == "rg28xx",
            "driver": driver, "nodes": nodes, "driver_registrations": registrations,
            "existing_shared_panel_bridge": model_id in ("rg34xxsp", "rg35xxh"),
            "integrated_by_this_extraction": False,
            "physical_acceptance_from_this_extraction": False,
            "command_program_extracted_from_this_binary": False,
        }
    result = {
        "schema": 1, "reference_commit": PIN,
        "scope": "Pinned primary source/binary catalog only; no image/device/card changes.",
        "tree_sha256": sha(tree_raw), "files": files, "profiles": profiles,
        "unmapped_models": {
            "rgsp": "User-original working720 identity; retain project baseline, not retail35SP.",
            "rg35xx_2025": "No separate model directory at this reference commit; do not infer from Plus.",
        },
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "catalog.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"profiles": len(profiles), "files": len(files), "output": str(args.output / 'catalog.json')}))


if __name__ == "__main__":
    main()

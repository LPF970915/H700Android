#!/usr/bin/env python3
"""Read-only offline audit of captures made by inspect_rgsp_single_card_raw.ps1.

Package offsets and structures come from the local Brandy 2.0 U-Boot source:
include/spare_head.h and include/private_toc.h. They are candidate locations,
not a substitute for capturing and checking the original RGSP card.
"""
import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path

SECTOR = 512
PACKAGE_LBAS = (24576, 32800)
STAMP = 0x5F0A6C39


def sha(data):
    return hashlib.sha256(data).hexdigest()


def gpt(head):
    header = bytearray(head[512:1024])
    if header[:8] != b"EFI PART":
        raise ValueError("Missing primary GPT")
    size, crc = struct.unpack_from("<II", header, 12)
    if not 92 <= size <= 512:
        raise ValueError("Invalid GPT header length")
    struct.pack_into("<I", header, 16, 0)
    if zlib.crc32(header[:size]) != crc:
        raise ValueError("GPT header CRC mismatch")
    lba, count, entry_size, entries_crc = struct.unpack_from("<QIII", header, 72)
    if not 1 <= count <= 128 or entry_size != 128:
        raise ValueError("Unsupported GPT entry array")
    entries = head[lba * SECTOR:lba * SECTOR + count * entry_size]
    if len(entries) != count * entry_size or zlib.crc32(entries) != entries_crc:
        raise ValueError("GPT entries CRC or length mismatch")
    parts = []
    for i in range(count):
        entry = entries[i * 128:(i + 1) * 128]
        if entry[:16] == bytes(16):
            continue
        first, last = struct.unpack_from("<QQ", entry, 32)
        if last < first:
            raise ValueError("Reversed partition extent")
        parts.append({
            "number": i + 1,
            "name": entry[56:128].decode("utf-16-le").rstrip("\0"),
            "start": first * SECTOR,
            "end_exclusive": (last + 1) * SECTOR,
        })
    return parts


def package(data):
    if len(data) < 64 or struct.unpack_from("<I", data, 16)[0] != 0x89119800:
        raise ValueError("No TOC1 magic at candidate location")
    checksum = struct.unpack_from("<I", data, 20)[0]
    count, length = struct.unpack_from("<II", data, 32)
    if not 1 <= count <= 64 or length < 64 + count * 368 or length % 4:
        raise ValueError("Invalid TOC1 header")
    if length > len(data):
        raise ValueError("Truncated TOC1 payload")
    words = struct.unpack_from(f"<{length // 4}I", data)
    actual = (sum(words) - checksum + STAMP) & 0xFFFFFFFF
    if actual != checksum:
        raise ValueError("TOC1 checksum mismatch")
    items = []
    for i in range(count):
        offset = 64 + i * 368
        name = data[offset:offset + 64].split(b"\0", 1)[0].decode("ascii")
        start, size = struct.unpack_from("<II", data, offset + 64)
        if start < 64 + count * 368 or size == 0 or start + size > length:
            raise ValueError("TOC1 item outside payload")
        items.append({"name": name, "offset": start, "bytes": size,
                      "sha256": sha(data[start:start + size])})
    names = {item["name"] for item in items}
    if not {"u-boot", "monitor", "dtb"} <= names:
        raise ValueError("Missing expected RGSP boot components")
    return {"bytes": length, "sha256": sha(data[:length]), "items": items}


def audit(head, boot, reference):
    if len(head) != 8 * 1024 * 1024 or len(boot) != 64 * 1024 * 1024:
        raise ValueError("Unexpected capture sizes")
    parts = gpt(head)
    if parts[0]["start"] != len(head) or parts[0]["name"] != "boot":
        raise ValueError("Capture does not describe the expected failed layout")
    if parts[0]["end_exclusive"] != len(head) + len(boot):
        raise ValueError("Boot capture does not cover the GPT extent")
    data = head + boot
    findings = []
    for lba in PACKAGE_LBAS:
        offset = lba * SECTOR
        owner = next((p["name"] for p in parts
                      if p["start"] <= offset < p["end_exclusive"]), None)
        finding = {"lba": lba, "offset": offset, "overlapping_partition": owner,
                   "first_32_bytes": data[offset:offset + 32].hex()}
        try:
            finding["package"] = package(data[offset:])
        except ValueError as error:
            finding["error"] = str(error)
        findings.append(finding)
    return {
        "status": "LAYOUT_REJECTED" if any(f["overlapping_partition"] or
                  "error" in f for f in findings) else "OFFLINE_CANDIDATE_ONLY",
        "physical_boot_verified": False,
        "partitions": parts,
        "boot0_signature_present": head[8196:8204] == b"eGON.BT0",
        "retained_payload_sha256": sha(head[2048:]),
        "reference_payload_sha256": sha(reference[2048:]),
        "retained_payload_matches_reference": head[2048:] == reference[2048:],
        "boot_partition_sha256": sha(boot),
        "candidate_boot_packages": findings,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    args = parser.parse_args()
    paths = [args.capture / "head-8m.bin", args.capture / "boot-p1.img", args.reference]
    if not all(p.is_file() and not p.is_symlink() for p in paths):
        raise ValueError("Only regular captured files are accepted")
    result = audit(*(p.read_bytes() for p in paths))
    print(json.dumps(result, indent=2))
    return 1 if result["status"] == "LAYOUT_REJECTED" else 0


if __name__ == "__main__":
    raise SystemExit(main())

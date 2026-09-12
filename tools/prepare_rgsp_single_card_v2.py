#!/usr/bin/env python3
"""Build a local RGSP-only card recipe preserving the original boot prefix."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import uuid
import zlib

from android_bootimg import component_offsets, read_header, pack
from audit_rgsp_single_card_boot import gpt, package
from replace_ramdisk_init import replace_entry

MIB = 1024**2
SIZE = 62239277056
SOURCE_SHA = "5f194bbcd3b93c061426451ecb0e21766a019438408b7c94e03d323d17da90b3"
EXPECTED = {
    "boot-single-card.img": "d445b34c61a3f292078a4d7a811387455073236476c3ce79dc989db771aeb09d",
    "system.raw.img": "199c03bf5b46a81e26aab133d8310ae576690c99c926b1835d5f3e8ac3115faa",
    "vendor.raw.img": "9d0c8d4a95b69131a70db6aebdfa1d9b3967afa9dc7dc8e95932872ecb372cc2",
    "data.raw.img": "54a3bc84fb6701b0caee5409a1b5ee222e81d9d759f9c8687e06bbf40827c1a1",
}
GUIDS = [
    "096d7fa1-62e8-c242-9876-cfdd5a92b8eb",
    "6aa8b46e-b96f-9545-bbfb-1b7d2bdc7da8",
    "734716ed-e7d9-e74f-9b3e-4f1cb8d448ed",
    "b4d04d65-2c35-4b7f-b9c5-8f24d2f10505",
]


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def header(source, current, backup, entries_lba, entries):
    h = bytearray(source)
    struct.pack_into("<QQQQ", h, 24, current, backup, 4, SIZE // 512 - 4)
    h[56:72] = uuid.UUID("c6f0c6f8-6d07-42c7-96b7-70e146c4d8a1").bytes_le
    struct.pack_into("<QIII", h, 72, entries_lba, 8, 128, zlib.crc32(entries))
    struct.pack_into("<I", h, 16, 0)
    struct.pack_into("<I", h, 16, zlib.crc32(h[:92]))
    return h


def layout(prefix):
    old = gpt(prefix)
    if [(p["name"], p["start"]) for p in old[:4]] != [
        ("special", 36*MIB), ("boot-resource", 100*MIB),
        ("env", 132*MIB), ("boot", 148*MIB)
    ]:
        raise ValueError("Unexpected original partition geometry")
    entries = bytearray(prefix[1024:2048])
    start = 212 * MIB
    for index, (name, length, guid) in enumerate(zip(
        ("system", "vendor", "data", "ROMS"),
        (8192*MIB, 2048*MIB, 16384*MIB, SIZE - 1536 - (212+8192+2048+16384)*MIB),
        GUIDS,
    ), 4):
        e = bytearray(128)
        kind = "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7" if index == 7 else "0fc63daf-8483-4772-8e79-3d69d8477de4"
        e[:16] = uuid.UUID(kind).bytes_le
        e[16:32] = uuid.UUID(guid).bytes_le
        struct.pack_into("<QQ", e, 32, start//512, (start+length)//512-1)
        encoded = name.encode("utf-16-le")
        e[56:56+len(encoded)] = encoded
        entries[index*128:(index+1)*128] = e
        start += length
    p = bytearray(prefix)
    # Match the original compact eight-entry GPT; a 128-entry GPT overlaps Boot0.
    mbr = bytearray(512)
    mbr[450] = 0xEE
    struct.pack_into("<II", mbr, 454, 1, SIZE//512-1)
    mbr[510:512] = b"\x55\xaa"
    p[:512] = mbr
    p[512:1024] = header(prefix[512:1024], 1, SIZE//512-1, 2, entries)
    p[1024:2048] = entries
    tail = entries + header(prefix[512:1024], SIZE//512-1, 1, SIZE//512-3, entries)
    parts = gpt(p)
    if p[MIB:] != prefix[MIB:]:
        raise ValueError("Original boot payload was altered")
    for a, b in zip(parts, parts[1:]):
        if a["end_exclusive"] > b["start"]:
            raise ValueError("Overlapping partitions")
    return p, tail, parts


def cpio_entries(blob):
    result = {}
    offset = 0
    while offset + 110 <= len(blob):
        h = blob[offset:offset+110]
        if h[:6] != b"070701":
            raise ValueError("Invalid cpio")
        size, ns = int(h[54:62], 16), int(h[94:102], 16)
        name = blob[offset+110:offset+110+ns-1].decode()
        start = (offset+110+ns+3) & ~3
        if start+size > len(blob):
            raise ValueError("Truncated cpio")
        if name == "TRAILER!!!":
            return result
        result[name] = (h[:54]+h[62:], blob[start:start+size])
        offset = (start+size+3) & ~3
    raise ValueError("Missing cpio trailer")


def build(source, out, baseline, system, vendor, data):
    root = Path(__file__).resolve().parents[1]
    source = source.resolve()
    out = out.absolute()
    if out.exists() or out.resolve() != out or not out.is_relative_to(root/"out"):
        raise ValueError("Fresh workspace output required")
    receipt = json.loads((source.parent/"capture.json").read_text())
    if receipt["status"] != "HOST_CAPTURE_VERIFIED" or digest(source) != SOURCE_SHA:
        raise ValueError("Unverified original card capture")
    prefix = source.read_bytes()
    if len(prefix) != 148*MIB:
        raise ValueError("Incomplete prefix")
    pkg = package(prefix[32800*512:])
    if pkg["sha256"] != "957929afa2879e18ff758d93eafa98879b21aec70dedcb731d7862a2c20f075c":
        raise ValueError("Unexpected original boot package")
    env = prefix[132*MIB:148*MIB]
    if zlib.crc32(env[4:131072]) != struct.unpack_from("<I", env)[0]:
        raise ValueError("Original environment CRC mismatch")
    inputs = {
        "boot-single-card.img": baseline/"boot-single-card.img",
        "system.raw.img": system,
        "vendor.raw.img": vendor,
        "data.raw.img": data,
    }
    for name, expected in EXPECTED.items():
        print("Hashing", name, flush=True)
        if digest(inputs[name]) != expected:
            raise ValueError("Source image changed: "+name)
    out.mkdir()
    original = inputs["boot-single-card.img"].read_bytes()
    _, boot_h = read_header(inputs["boot-single-card.img"])
    ramoff = component_offsets(boot_h)["ramdisk"]
    raw = gzip.decompress(original[ramoff:ramoff+boot_h["ramdisk_size"]])
    init = (root/"tools/rgsp_single_card_init.sh").read_bytes()
    if b"\r" in init:
        raise ValueError("Init must use LF line endings")
    replaced = replace_entry(raw, init)
    before, after = cpio_entries(raw), cpio_entries(replaced)
    if "init" not in before or before.keys() != after.keys():
        raise ValueError("Ramdisk inventory changed")
    if [k for k in before if before[k] != after[k]] != ["init"]:
        raise ValueError("Only init may change")
    ramdisk = out/"ramdisk.gz"
    ramdisk.write_bytes(gzip.compress(replaced, compresslevel=1, mtime=0))
    boot = out/"boot.img"
    pack(argparse.Namespace(template=str(inputs["boot-single-card.img"]),
         out=str(boot), kernel=None, ramdisk=str(ramdisk), second=None, dtb=None))
    b = bytearray(boot.read_bytes())
    b[64:576] = b"selinux=1 enforcing=0 androidboot.selinux=permissive".ljust(512,b"\0")
    boot.write_bytes(b)
    _, new_h = read_header(boot)
    old_offsets, new_offsets = component_offsets(boot_h), component_offsets(new_h)
    for name in ("kernel", "dtb"):
        length = boot_h["kernel_size"] if name == "kernel" else boot_h["dt_size_detected"]
        if original[old_offsets[name]:old_offsets[name]+length] != b[new_offsets[name]:new_offsets[name]+length]:
            raise ValueError("Kernel or DTB changed")
    p, tail, parts = layout(prefix)
    candidate = out/"prefix-212m.bin"
    with candidate.open("xb") as file:
        file.write(p)
        file.write(b)
    (out/"gpt-tail.bin").write_bytes(tail)
    roms = out/"roms-format.img"
    roms_length = parts[7]["end_exclusive"]-parts[7]["start"]
    # Local sparse format image only; the card writer copies its metadata extent.
    with roms.open("xb") as file:
        file.truncate(roms_length)
    wsl_roms = "/mnt/"+str(roms)[0].lower()+str(roms)[2:].replace("\\","/")
    subprocess.run(["wsl","-d","Ubuntu","-u","root","--","mkfs.fat","-F","32",
                    "-s","64","-n","ROMS",wsl_roms],check=True)
    with roms.open("rb") as file:
        bs = file.read(512)
        reserved = struct.unpack_from("<H",bs,14)[0]
        fat_size = struct.unpack_from("<I",bs,36)[0]
        metadata_length = ((reserved + bs[16]*fat_size + bs[13])*512 + MIB-1)//MIB*MIB
        file.seek(0)
        metadata = file.read(metadata_length)
    roms_head = out/"roms-metadata.bin"
    roms_head.write_bytes(metadata)
    ranges = [
        {"path":str(candidate),"offset":0,"bytes":candidate.stat().st_size},
        *[{"path":str(inputs[name]),"offset":parts[i]["start"],
           "bytes":parts[i]["end_exclusive"]-parts[i]["start"]}
          for i,name in enumerate(("system.raw.img","vendor.raw.img","data.raw.img"),4)],
        {"path":str(roms_head),"offset":parts[7]["start"],"bytes":len(metadata)},
        {"path":str(out/"gpt-tail.bin"),"offset":SIZE-1536,"bytes":1536},
    ]
    for r in ranges:
        name = Path(r["path"]).name
        r["sha256"] = EXPECTED[name] if name in EXPECTED else digest(Path(r["path"]))
    manifest = {
        "status":"OFFLINE_CANDIDATE_NOT_WRITTEN","target_bytes":SIZE,
        "target_serial":"000000001539","source_prefix_sha256":SOURCE_SHA,
        "boot_package":pkg,"partitions":parts,"ranges":ranges,
        "init_sha256":hashlib.sha256(init).hexdigest(),
        "boot_sha256":digest(boot),
        "original_env_preserved":True,"original_work_card_writes":False,
        "system_vendor_data_recompiled":False,
        "roms_format_bytes":roms_length,"roms_metadata_bytes":metadata_length,
        "source_preimages":{name: EXPECTED[name] for name in inputs},
        "source_paths":{name: str(path) for name, path in inputs.items()},
    }
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps(manifest,indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--baseline",type=Path,
                        default=Path("out/rgsp-single-card-20260911"))
    parser.add_argument("--system",type=Path,
                        default=Path("out/rgsp-fix72-wifi-profile/system.raw.img"))
    parser.add_argument("--vendor",type=Path,
                        default=Path("out/rgsp-audio-candidate-20260910/vendor.raw.img"))
    parser.add_argument("--data",type=Path,
                        default=Path("out/rgsp-single-card-20260911/data.raw.img"))
    args = parser.parse_args()
    build(args.source,args.output,args.baseline.resolve(),args.system.resolve(),
          args.vendor.resolve(),args.data.resolve())

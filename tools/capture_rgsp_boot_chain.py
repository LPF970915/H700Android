#!/usr/bin/env python3
"""Capture the original RGSP prefix through verified SSH, without card writes."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

LENGTH = 148 * 1024 * 1024
CID = "1d414455534400002000009f9401a1e7"
HOST = "192.168.31.164"


def now():
    return datetime.now(timezone.utc).isoformat()


def identity():
    def text(path):
        return Path(path).read_text().strip()
    root = subprocess.check_output(
        ["findmnt", "-rn", "-o", "SOURCE", "--target", "/"], text=True).strip()
    if os.geteuid() != 0 or root != "/dev/mmcblk0p5":
        raise ValueError("Original Linux root required")
    if text("/sys/block/mmcblk0/device/cid") != CID:
        raise ValueError("Original TF1 CID mismatch")
    if text("/sys/class/block/mmcblk0p4/start") != "303104":
        raise ValueError("Original boot offset changed")
    if text("/sys/class/power_supply/axp2202-usb/online") != "1":
        raise ValueError("External power required")
    return {"cid": CID, "boot_id": text("/proc/sys/kernel/random/boot_id"),
            "root": root, "bytes": LENGTH}


def read_hash(source, output=None):
    sha = hashlib.sha256()
    left = LENGTH
    while left:
        data = source.read(min(left, 1024 * 1024))
        if not data:
            raise ValueError("Unexpected EOF")
        sha.update(data)
        if output:
            output.write(data)
        left -= len(data)
    return sha.hexdigest()


def device():
    before = identity()
    with open("/dev/mmcblk0", "rb", buffering=0) as source:
        with gzip.GzipFile(fileobj=sys.stdout.buffer, mode="wb",
                           compresslevel=1, mtime=0, filename="") as dest:
            first = read_hash(source, dest)
        sys.stdout.buffer.flush()
        source.seek(0)
        second = read_hash(source)
    if first != second or identity() != before:
        raise ValueError("Source changed during capture")
    print(json.dumps({"status": "SOURCE_VERIFIED", "identity": before,
                      "sha256": first, "second_sha256": second,
                      "completed": now(), "card_writes": False}),
          file=sys.stderr, flush=True)


def capture(out):
    root = Path(__file__).resolve().parents[1]
    out = out.absolute()
    if out.exists() or out.resolve() != out or not out.is_relative_to(root / "out"):
        raise ValueError("Use a fresh output directory under workspace out")
    out.mkdir()
    env = dict(os.environ, SSH_ASKPASS=str(root / "ssh-askpass.cmd"),
               SSH_ASKPASS_REQUIRE="force", DISPLAY="codex")
    recipe = Path(__file__).read_text()
    remote = "nice -n 19 python3 -c " + shlex.quote(recipe) + " --device"
    cmd = ["ssh", "-T", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=8",
           "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3",
           "-o", "NumberOfPasswordPrompts=1", "root@" + HOST, remote]
    archive = out / "tf1-prefix-148m.bin.gz"
    log = out / "source.jsonl"
    with archive.open("xb") as data, log.open("xb") as err:
        result = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=data,
                                stderr=err, env=env, timeout=240)
    if result.returncode:
        raise ValueError("Source capture failed; inspect source.jsonl")
    records = [json.loads(line) for line in log.read_text().splitlines()
               if line.startswith("{")]
    if len(records) != 1 or records[0]["status"] != "SOURCE_VERIFIED":
        raise ValueError("Missing source verification receipt")
    with gzip.open(archive, "rb") as source, (out / "tf1-prefix-148m.bin").open("xb") as dest:
        actual = read_hash(source, dest)
        if source.read(1):
            raise ValueError("Archive exceeds capture range")
    if actual != records[0]["sha256"]:
        raise ValueError("Host decompressed hash mismatch")
    receipt = {**records[0], "status": "HOST_CAPTURE_VERIFIED",
               "capture_script_sha256": hashlib.sha256(recipe.encode()).hexdigest(),
               "host_completed": now()}
    (out / "capture.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.device:
        device()
    elif args.output:
        capture(args.output)
    else:
        parser.error("--output required on host")

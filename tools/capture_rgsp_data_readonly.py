#!/usr/bin/env python3
"""Capture pinned, unmounted RGSP data over verified SSH; never repair it."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time

DATA = "/dev/mmcblk1p4"
DATA_BYTES = 17179869184
CHUNK = 1024 * 1024
HOST = "192.168.31.164"
REMOTE = "/run/capture_rgsp_data_readonly_20260909.py"
FLOOR = 80 * 1024**3


def now():
    return datetime.now(timezone.utc).isoformat()


def command(*args):
    return subprocess.check_output(args, text=True, env={**os.environ, "LC_ALL": "C"}).strip()


def identity():
    expected = {
        "/sys/block/mmcblk0/device/cid": "1d414455534400002000009f9401a1e7",
        "/sys/block/mmcblk1/device/cid": "fe3432534400000020000005bc01896b",
        "/sys/class/power_supply/axp2202-usb/online": "1",
    }
    if os.geteuid() != 0 or command("findmnt", "-rn", "-o", "SOURCE", "--target", "/") != "/dev/mmcblk0p5":
        raise ValueError("Original root Linux required")
    for path, value in expected.items():
        if Path(path).read_text().strip() != value:
            raise ValueError("Card identity or external power mismatch")
    if command("blockdev", "--getsize64", DATA) != str(DATA_BYTES):
        raise ValueError("Data partition size mismatch")
    for key, value in {
        "PARTUUID": "734716ed-e7d9-e74f-9b3e-4f1cb8d448ed",
        "UUID": "45daaa6e-724e-4d20-981c-602b3f72b8a2",
        "TYPE": "ext4",
    }.items():
        if command("blkid", "-s", key, "-o", "value", DATA) != value:
            raise ValueError("Data filesystem identity mismatch")
    mounted = subprocess.run(["findmnt", "-rn", "-S", DATA], capture_output=True)
    if mounted.returncode != 1:
        raise ValueError("Mounted or unknown data mount state")
    if Path("/mnt/sdcard/RGSP_ANDROID_TRY.ONCE").exists():
        raise ValueError("Pending boot marker")
    return {
        "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        "cid_tf1": expected["/sys/block/mmcblk0/device/cid"],
        "cid_tf2": expected["/sys/block/mmcblk1/device/cid"],
        "data_bytes": DATA_BYTES,
    }


def digest(stream, length):
    sha = hashlib.sha256()
    left = length
    while left:
        block = stream.read(min(CHUNK, left))
        if not block:
            raise ValueError("Unexpected source EOF")
        sha.update(block)
        left -= len(block)
    return sha.hexdigest()


def compress(stream, output, length, progress=None):
    sha = hashlib.sha256()
    total = 0
    next_report = 1024**3
    with gzip.GzipFile(filename="", fileobj=output, mode="wb", compresslevel=1, mtime=0) as zipped:
        while total < length:
            block = stream.read(min(CHUNK, length - total))
            if not block:
                raise ValueError("Unexpected source EOF")
            sha.update(block)
            zipped.write(block)
            total += len(block)
            if progress and total >= next_report:
                progress(total)
                next_report += 1024**3
    return sha.hexdigest()


def verify_archive(path, expected_size, expected_sha):
    with gzip.open(path, "rb") as stream:
        actual = digest(stream, expected_size)
        if stream.read(1):
            raise ValueError("Archive expands beyond expected size")
    if actual != expected_sha:
        raise ValueError("Archive raw hash mismatch")
    return actual


def device_stream():
    before = identity()
    info = os.stat(DATA, follow_symlinks=False)
    if not stat.S_ISBLK(info.st_mode):
        raise ValueError("Expected real block device")
    fd = os.open(DATA, os.O_RDONLY | os.O_NOFOLLOW)
    def log(value):
        print(json.dumps(value), file=sys.stderr, flush=True)
    with os.fdopen(fd, "rb", buffering=0) as source:
        if os.fstat(source.fileno()).st_rdev != info.st_rdev:
            raise ValueError("Block device changed while opening")
        log({"phase": "stream", "identity": before, "started": now()})
        stream_sha = compress(source, sys.stdout.buffer, DATA_BYTES,
                              lambda n: log({"phase": "stream", "raw_bytes": n}))
        sys.stdout.buffer.flush()
        if identity() != before:
            raise ValueError("Identity changed after stream")
        log({"phase": "independent_source_hash", "stream_sha256": stream_sha})
        source.seek(0)
        independent = digest(source, DATA_BYTES)
        if independent != stream_sha or identity() != before:
            raise ValueError("Source changed during capture")
        log({"status": "SOURCE_READONLY_VERIFIED", "sha256": stream_sha,
             "independent_sha256": independent, "bytes": DATA_BYTES,
             "identity": before, "completed": now(), "device_data_writes": False})


def capture(output):
    root = Path(__file__).resolve().parents[1]
    parent = (root / "out").resolve()
    target = Path(output).absolute()
    if target.resolve() != target or not target.is_relative_to(parent) or target == parent:
        raise ValueError("Output must be inside workspace out without symlinks")
    if target.exists():
        raise ValueError("Use a new output directory")
    if shutil.disk_usage(parent).free < FLOOR + DATA_BYTES + CHUNK:
        raise ValueError("Insufficient backup headroom above 80 GiB reserve")
    if not os.environ.get("SSHPASS"):
        raise ValueError("SSH password must be supplied via environment")
    target.mkdir()
    known = "/mnt/c/Users/LPF/.ssh/known_hosts"
    ssh = ["sshpass", "-e", "ssh", "-T", "-o", "StrictHostKeyChecking=yes",
           "-o", "UserKnownHostsFile=" + known, "-o", "ConnectTimeout=10",
           "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3", "root@" + HOST]
    recipe_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    remote_command = (
        "test \"$(sha256sum " + REMOTE + " | cut -d ' ' -f 1)\" = " + recipe_sha +
        " && exec nice -n 10 python3 " + REMOTE + " device-stream"
    )
    archive = target / "data.before.img.gz"
    log = target / "device-capture.jsonl"
    process = None
    try:
        with log.open("xb") as errors, archive.open("xb") as destination:
            process = subprocess.Popen(ssh + [remote_command], stdout=subprocess.PIPE, stderr=errors)
            sha = hashlib.sha256()
            total = 0
            last = time.monotonic()
            while True:
                chunk = process.stdout.read(CHUNK)
                if not chunk:
                    break
                if total + len(chunk) > DATA_BYTES + CHUNK:
                    raise ValueError("Compressed stream exceeded bounded size")
                if shutil.disk_usage(target).free - len(chunk) < FLOOR:
                    raise ValueError("Backup free-space reserve reached")
                destination.write(chunk)
                sha.update(chunk)
                total += len(chunk)
                if time.monotonic() - last > 30:
                    print("COMPRESSED_BYTES_RECEIVED=" + str(total), flush=True)
                    last = time.monotonic()
            rc = process.wait(timeout=60)
            destination.flush()
            os.fsync(destination.fileno())
        if rc != 0:
            raise ValueError("Remote capture failed; retain partial archive and log")
        records = [json.loads(line) for line in log.read_text().splitlines() if line.startswith("{")]
        result = records[-1]
        if result.get("status") != "SOURCE_READONLY_VERIFIED" or result.get("bytes") != DATA_BYTES:
            raise ValueError("Missing successful source receipt")
        print("VERIFYING_ARCHIVE_RAW_CONTENT", flush=True)
        verify_archive(archive, DATA_BYTES, result["sha256"])
        with archive.open("rb") as stream:
            archive_sha = digest(stream, total)
        if archive_sha != sha.hexdigest():
            raise ValueError("Stored compressed archive hash mismatch")
        result.update({"status": "HOST_ARCHIVE_AND_SOURCE_VERIFIED",
                       "archive": archive.name, "archive_bytes": total,
                       "archive_sha256": archive_sha, "recipe_sha256": recipe_sha,
                       "host_completed": now()})
        with (target / "capture.json").open("x") as receipt:
            json.dump(result, receipt, indent=2)
            receipt.flush()
            os.fsync(receipt.fileno())
        print(json.dumps(result, indent=2), flush=True)
    finally:
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            if process.stdout:
                process.stdout.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("device-stream")
    host = sub.add_parser("capture")
    host.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.mode == "device-stream":
        device_stream()
    else:
        capture(args.output)

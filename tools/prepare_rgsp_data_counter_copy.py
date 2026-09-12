#!/usr/bin/env python3
"""Correct only two reported superblock counters on a SECOND local copy."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from analyze_rgsp_data_copy import (check_readonly_result, header_fields, regular,
                                   run_log, save, sha, snapshot)
from capture_rgsp_data_readonly import DATA_BYTES, FLOOR, now


def counter_fixes(result):
    text = result.stdout + result.stderr
    fixes = {}
    for label, field in (("blocks", "free_blocks_count"), ("inodes", "free_inodes_count")):
        pattern = rf"Free {label} count wrong \((\d+), counted=(\d+)\)\.\s*Fix\? no"
        matches = re.findall(pattern, text)
        if len(matches) != 1:
            raise ValueError("Expected exactly the two known counter diagnostics")
        old, new = map(int, matches[0])
        if old <= 0 or new <= 0 or old == new:
            raise ValueError("Invalid counter correction")
        fixes[field] = {"before": old, "after": new}
        text = re.sub(pattern, "", text)
    check_readonly_result(subprocess.CompletedProcess([], result.returncode, text, ""))
    return fixes


def apply_counts(candidate, fixes, output):
    regular(candidate)
    for field in ("free_blocks_count", "free_inodes_count"):
        value = fixes[field]["after"]
        if not isinstance(value, int) or value <= 0:
            raise ValueError("Expected positive numeric counter")
        result = run_log(["debugfs", "-w", "-R", f"set_super_value {field} {value}",
                          str(candidate)], output / f"set-{field}.txt")
        if result.returncode != 0:
            raise ValueError("Counter update failed on local copy")


def clone(source, candidate):
    regular(source, DATA_BYTES)
    h = hashlib.sha256()
    total = 0
    with source.open("rb") as src, candidate.open("xb") as dst:
        while True:
            data = src.read(4 * 1024 * 1024)
            if not data:
                break
            total += len(data)
            if total > DATA_BYTES:
                raise ValueError("Source grew during clone")
            h.update(data)
            if data == bytes(len(data)):
                dst.seek(len(data), 1)
            else:
                dst.write(data)
            if total % (4 * 1024**3) == 0:
                print(f"SECOND_COPY_BYTES={total}", flush=True)
        dst.truncate(total)
        dst.flush()
        os.fsync(dst.fileno())
    if total != DATA_BYTES or sha(candidate) != h.hexdigest():
        raise ValueError("Second copy readback mismatch")
    return h.hexdigest()


def compare_original(archive, candidate):
    original_hash, candidate_hash = hashlib.sha256(), hashlib.sha256()
    changed = []
    offset = 0
    with gzip.open(archive, "rb") as original, candidate.open("rb") as current:
        while True:
            a, b = original.read(4 * 1024 * 1024), current.read(4 * 1024 * 1024)
            if len(a) != len(b):
                raise ValueError("Comparison lengths differ")
            if not a:
                break
            original_hash.update(a)
            candidate_hash.update(b)
            if a != b:
                for n in range(0, len(a), 4096):
                    old, new = a[n:n + 4096], b[n:n + 4096]
                    if old != new:
                        changed.append({"offset": offset + n, "bytes": len(old),
                                        "before_sha256": hashlib.sha256(old).hexdigest(),
                                        "after_sha256": hashlib.sha256(new).hexdigest()})
            offset += len(a)
    if offset != DATA_BYTES:
        raise ValueError("Incomplete full-image comparison")
    return original_hash.hexdigest(), candidate_hash.hexdigest(), changed


def counter_source_inventory(source, journal, output):
    entries = snapshot(source)
    previous = journal / "files-after.json"
    if previous.exists() and entries != json.loads(previous.read_text()):
        raise ValueError("Journal replay inventory changed before counter correction")
    save(output / "files-before-counter.json", entries)
    return entries


def prepare(directory):
    root = Path(__file__).resolve().parents[1] / "out"
    folder = Path(directory).absolute()
    if folder.resolve() != folder or not folder.is_relative_to(root.resolve()):
        raise ValueError("Backup must stay inside workspace out without symlinks")
    archive = folder / "data.before.img.gz"
    receipt_path = folder / "capture.json"
    regular(receipt_path)
    receipt = json.loads(receipt_path.read_text())
    if (receipt["status"] != "HOST_ARCHIVE_AND_SOURCE_VERIFIED" or
            receipt["bytes"] != DATA_BYTES or receipt["sha256"] != receipt["independent_sha256"] or
            sha(archive) != receipt["archive_sha256"]):
        raise ValueError("Verified complete original archive required")
    source = folder / "offline-journal-trial/data.journal-replayed.img"
    regular(source, DATA_BYTES)
    if os.geteuid() != 0:
        raise ValueError("Read-only inventory requires root")
    if shutil.disk_usage(folder).free < FLOOR + DATA_BYTES:
        raise ValueError("Insufficient second-copy headroom above reserve")
    out = folder / "offline-counter-trial"
    out.mkdir()
    observed = run_log(["e2fsck", "-fn", str(source)], out / "source-fsck.txt")
    fixes = counter_fixes(observed)
    save(out / "counter-fixes.json", fixes)
    header = run_log(["tune2fs", "-l", str(source)], out / "source-header.txt")
    fields = header_fields(header.stdout)
    if (header.returncode != 0 or "needs_recovery" in fields["Filesystem features"].split() or
            fields["Filesystem UUID"] != "45daaa6e-724e-4d20-981c-602b3f72b8a2" or
            int(fields["Free blocks"]) != fixes["free_blocks_count"]["before"] or
            int(fields["Free inodes"]) != fixes["free_inodes_count"]["before"]):
        raise ValueError("Unexpected source header; no candidate modification")
    # The journal analyzer deliberately stops before inventory on counter errors.
    baseline = counter_source_inventory(source, folder / "offline-journal-trial", out)
    candidate = out / "data.recovery-candidate.img"
    source_sha = clone(source, candidate)
    print("CORRECTING_TWO_COUNTERS_ON_SECOND_COPY_ONLY", flush=True)
    apply_counts(candidate, fixes, out)
    after_fsck = run_log(["e2fsck", "-fn", str(candidate)], out / "candidate-fsck.txt")
    check_readonly_result(after_fsck)
    after_header = run_log(["tune2fs", "-l", str(candidate)], out / "candidate-header.txt")
    after_fields = header_fields(after_header.stdout)
    if (after_header.returncode != 0 or after_fields["Filesystem state"] != "clean" or
            "needs_recovery" in after_fields["Filesystem features"].split() or
            after_fields["Filesystem UUID"] != fields["Filesystem UUID"] or
            int(after_fields["Free blocks"]) != fixes["free_blocks_count"]["after"] or
            int(after_fields["Free inodes"]) != fixes["free_inodes_count"]["after"]):
        raise ValueError("Candidate header did not match exact correction")
    entries = snapshot(candidate)
    save(out / "files-after.json", entries)
    if entries != baseline:
        raise ValueError("Counter-only correction changed file inventory")
    original_entries = json.loads((folder / "offline-journal-trial/files-before.json").read_text())
    file_delta = [{"path": name, "before": original_entries.get(name), "after": entries.get(name)}
                  for name in sorted(original_entries.keys() | entries.keys())
                  if original_entries.get(name) != entries.get(name)]
    save(out / "file-diff-from-original.json", file_delta)
    print("COMPARING_COMPLETE_ORIGINAL_AND_FINAL_COPY", flush=True)
    original_sha, candidate_sha, delta = compare_original(archive, candidate)
    if original_sha != receipt["sha256"] or sha(archive) != receipt["archive_sha256"]:
        raise ValueError("Original archive changed")
    save(out / "block-diff.json", delta)
    save(out / "result.json", {
        "status": "OFFLINE_RECOVERY_VERIFIED_NOT_DEPLOYED",
        "original_sha256": original_sha, "journal_only_sha256": source_sha,
        "candidate_sha256": candidate_sha, "bytes": DATA_BYTES,
        "counter_fixes": fixes, "changed_4096_byte_blocks": len(delta),
        "file_changes_from_counter_correction": 0,
        "changed_file_entries_from_original": len(file_delta),
        "file_entries": len(entries), "readonly_fsck_diagnostics_clean": True,
        "physical_data_writes": False, "physical_recovery_authorized": False,
        "recipe_sha256": sha(Path(__file__)), "completed": now(),
    })
    print((out / "result.json").read_text(), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True)
    parser.add_argument("--prepare", action="store_true", required=True)
    prepare(parser.parse_args().directory)

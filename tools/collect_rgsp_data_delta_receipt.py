#!/usr/bin/env python3
"""Validate a completed UART delta attempt before emitting a host receipt."""
import argparse
import json
from pathlib import Path
import re

import deploy_rgsp_data_delta as d


def validate(text, records, script_sha, bundle_sha, authorization_sha):
    begin = re.findall(r"^__CODEX_SERIAL_BEGIN_([0-9a-f]{32})__$", text, re.MULTILINE)
    end = re.findall(r"^__CODEX_SERIAL_END_([0-9a-f]{32})__:(\d+)$", text, re.MULTILINE)
    if len(begin) != 1 or end != [(begin[0], "0")]:
        raise ValueError("Missing unique successful serial completion marker")
    starts = [i for i, item in enumerate(records) if item.get("status") == "AUTHORIZED_APPLY_START"]
    if len(starts) != 1:
        raise ValueError("Missing authorized start")
    start = starts[0]
    if start:
        expected_prefix = [{"phase": "protected_hash", "bytes": n, "total": 2147483648}
                           for n in range(256 * 1024**2, 2147483648 + 1, 256 * 1024**2)]
        prefix = [{k: item.get(k) for k in ("phase", "bytes", "total")} for item in records[:start]]
        if not d.PROFILE_SHA or prefix != expected_prefix or any("status" in r for r in records[:start]):
            raise ValueError("Unexpected events before authorized start")
    first, last = records[start], records[-1]
    if (first["script_sha256"] != script_sha or first["bundle_sha256"] != bundle_sha or
            first["authorization_sha256"] != authorization_sha or first["blocks"] != d.BLOCK_COUNT):
        raise ValueError("Executed artifacts/authorization do not match archive")
    if last.get("status") != "PHYSICAL_P4_RECOVERY_VERIFIED":
        raise ValueError("Missing successful physical recovery status")
    for key, expected in {"sha256": d.CANDIDATE, "bytes": d.SIZE,
                          "strict_readonly_fsck_clean": True, "boot_marker": False,
                          "data_unmounted": True, "modified_partition": d.DATA,
                          "written_blocks": d.BLOCK_COUNT}.items():
        if last.get(key) != expected:
            raise ValueError("Final acceptance field mismatch: " + key)
    protected = {"/dev/mmcblk0p4": d.BOOT, "/dev/mmcblk0p3": d.ENV}
    protected.update({path: expected for path, _, expected in d.EXTRA_PROTECTED})
    if d.PROFILE_SHA and (first.get("recovery_profile_sha256") != d.PROFILE_SHA or
                          last.get("recovery_profile_sha256") != d.PROFILE_SHA):
        raise ValueError("Audio recovery profile mismatch")
    if first["protected"] != protected or last["protected"] != protected:
        raise ValueError("Protected hashes mismatch")
    for item in records:
        if "FAILED" in item.get("status", "") or item.get("phase", "").startswith("rollback"):
            raise ValueError("Failure/rollback records cannot form a success receipt")
    phases = {}
    for index, item in enumerate(records):
        phases.setdefault(item.get("phase"), []).append((index, item))
    for phase in ("full_original_hash", "full_candidate_readback"):
        observed = phases.get(phase, [])
        expected = list(range(256 * 1024**2, d.SIZE + 1, 256 * 1024**2))
        if ([item["bytes"] for _, item in observed] != expected or
                any(item["total"] != d.SIZE for _, item in observed)):
            raise ValueError("Incomplete full-read progress: " + phase)
    verified = []
    for phase, expected in (("full_original_verified", d.ORIGINAL),
                            ("full_candidate_verified", d.CANDIDATE)):
        events = phases.get(phase, [])
        if len(events) != 1 or events[0][1]["sha256"] != expected:
            raise ValueError("Missing full-image hash result: " + phase)
        verified.append(events[0][0])
    rows = d.manifest((d.BASE / d.TRIAL / "block-diff.json").read_bytes())
    offsets = [row["offset"] for row in sorted(rows, key=lambda row: (row["offset"] == 0, row["offset"]))]
    writes = phases.get("block_written", [])
    if ([item["offset"] for _, item in writes] != offsets or
            [item["count"] for _, item in writes] != list(range(1, d.BLOCK_COUNT + 1))):
        raise ValueError("Write sequence does not match approved blocks")
    fsck = phases.get("readonly_fsck", [])
    if len(fsck) != 1:
        raise ValueError("Missing unique read-only fsck")
    event = fsck[0][1]
    from subprocess import CompletedProcess
    d.strict_fsck(CompletedProcess([], event["exit_code"], event["output"], ""))
    if not 0 < verified[0] < writes[0][0] <= writes[-1][0] < verified[1] < fsck[0][0] < len(records) - 1:
        raise ValueError("Acceptance sequence is out of order")
    return last


def collect(transcript, directory):
    folder = Path(directory).absolute()
    if folder.resolve() != folder or not folder.is_relative_to(d.BASE.resolve()):
        raise ValueError("Evidence output must stay under the backup directory")
    raw = Path(transcript).read_bytes()
    lines = raw.decode("utf-8-sig").splitlines()
    text = "\n".join(lines)
    json_lines = [line for line in lines if line.startswith("{")]
    records = [json.loads(line) for line in json_lines]
    script_sha = d.sha((folder / "deploy_rgsp_data_delta.py").read_bytes())
    bundle_sha = d.sha((folder / "data-approved-delta.json.gz").read_bytes())
    authorization_sha = d.sha((folder / "authorization-and-intent.json").read_bytes())
    result = dict(validate(text, records, script_sha, bundle_sha, authorization_sha))
    log = ("\n".join(json_lines) + "\n").encode("ascii")
    with (folder / "device-apply.jsonl").open("xb") as stream:
        stream.write(log)
    result.update({"host_collected": d.timestamp(), "uart_transcript": str(Path(transcript).absolute()),
                   "uart_sha256": d.sha(raw), "device_log_sha256": d.sha(log),
                   "script_sha256": script_sha, "bundle_sha256": bundle_sha,
                   "authorization_sha256": authorization_sha,
                   "collector_sha256": d.sha(Path(__file__).read_bytes()),
                   "device_ram_log_hash_independently_checked": False})
    d.save_json(folder / "physical-recovery-result.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio-profile")
    parser.add_argument("--audio-profile-sha256")
    parser.add_argument("--transcript", required=True)
    parser.add_argument("--directory", required=True)
    args = parser.parse_args()
    if bool(args.audio_profile) != bool(args.audio_profile_sha256):
        parser.error("Both explicit audio profile path and hash are required")
    if args.audio_profile:
        d.configure_audio_profile(args.audio_profile, args.audio_profile_sha256)
    collect(args.transcript, args.directory)

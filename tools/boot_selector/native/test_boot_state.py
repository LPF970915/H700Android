"""Host/AArch64 boot-state tests using ordinary private files only."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import struct
import subprocess
import zlib

ENV_BYTES = 128 * 1024
PART_BYTES = 16 * 1024 * 1024
ENV_OFFSET = 138412032
OWNED = {"roc_saved_model", "roc_next_model", "roc_next_start"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def decode(blob):
    if len(blob) != ENV_BYTES or struct.unpack_from("<I", blob)[0] != zlib.crc32(blob[4:]):
        raise ValueError("Bad fixture environment")
    body = blob[4:]
    end = body.find(b"\0\0")
    if end < 0:
        raise ValueError("No terminator")
    return [tuple(row.decode("ascii").split("=", 1)) if row else ("", "")
            for row in body[:end].split(b"\0")]


def encode(rows, *, padding=b""):
    body = b"\0".join((key + "=" + value).encode("ascii") if key else b"" for key, value in rows) + b"\0\0"
    body += padding
    if len(body) >= ENV_BYTES - 4:
        raise ValueError("fixture too large")
    body = body.ljust(ENV_BYTES - 4, b"\0")
    return struct.pack("<I", zlib.crc32(body)) + body


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def run_target(command, args, *, success=True):
    result = subprocess.run([*command, *map(str, args)], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, timeout=6)
    require((result.returncode == 0) == success, f"Unexpected exit {result.returncode}: {result.stderr}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--host", type=Path, required=True)
    parser.add_argument("--arm", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir()
    with args.prefix.open("rb") as stream:
        stream.seek(ENV_OFFSET)
        source_part = stream.read(PART_BYTES)
    require(len(source_part) == PART_BYTES, "Short original partition")
    source_rows = decode(source_part[:ENV_BYTES])
    require(source_rows[0] == ("", ""), "Expected real vendor leading empty row")
    records = []
    for architecture, command in (("host", [str(args.host)]),
                                  ("aarch64", ["/usr/bin/qemu-aarch64", str(args.arm)])):
        work = args.work / architecture
        work.mkdir()
        rows = [(key, ("sunxi_flash read 45000000 boot;run roc_selector_apply;bootm 45000000" if key == "boot_normal" else value))
                for key, value in source_rows]
        rows += [("roc_selector_schema", "2"), ("roc_selector_apply", "echo roc-test-hook"),
                 ("fixture_unknown", "spaces=semicolons;${untouched} and equals=kept")]
        original = encode(rows) + source_part[ENV_BYTES:]
        fixture = work / "environment.part"
        fixture.write_bytes(original)
        base_unowned = [(k, v) for k, v in rows if k not in OWNED]
        results = []

        def invariant():
            current = fixture.read_bytes()
            require(len(current) == PART_BYTES, "Partition length changed")
            require(current[ENV_BYTES:] == original[ENV_BYTES:], "16MiB remainder changed")
            require([(k, v) for k, v in decode(current[:ENV_BYTES]) if k not in OWNED] == base_unowned,
                    "Unowned environment row/order/leading empty changed")
            return dict(decode(current[:ENV_BYTES]))

        def invoke(action, model=None):
            value = ["--fixture", fixture, action]
            if model:
                value.append(model)
            result = run_target(command, value)
            status = run_target(command, ["--fixture", fixture, "status"]).stdout
            current = invariant()
            results.append({"action": action, "model": model, "status": status.strip(),
                            "crc_valid": True, "tail_16m_preserved": True})
            return current

        require(invoke("status").get("roc_saved_model", "") == "", "Nonempty initial saved")
        require(invoke("save", "rgsp")["roc_saved_model"] == "rgsp", "Save did not persist")
        current = invoke("once", "rg35xxh")
        require((current["roc_saved_model"], current["roc_next_model"], current["roc_next_start"]) == ("rgsp", "rg35xxh", "1"), "once changed saved or next")
        current = invoke("clear-next")
        require(current["roc_saved_model"] == "rgsp" and "roc_next_model" not in current and "roc_next_start" not in current,
                "Clear next discarded saved or retained next")
        invoke("clear-next")
        identical = fixture.read_bytes()
        invoke("save", "rgsp")
        require(fixture.read_bytes() == identical, "Idempotent save changed bytes")
        invoke("once", "rg34xxsp")
        current = invoke("save", "rg35xxh")
        require(current["roc_saved_model"] == "rg35xxh" and "roc_next_model" not in current, "save did not clear next")

        # The vendor's leading empty row must not be invented for a normal env.
        no_leading = work / "without-leading.part"
        no_leading.write_bytes(encode(rows[1:]) + source_part[ENV_BYTES:])
        run_target(command, ["--fixture", no_leading, "save", "rgsp"])
        require(decode(no_leading.read_bytes()[:ENV_BYTES])[0][0] != "", "Invented leading empty row")
        results.append({"case": "no-leading-empty-preserved", "pass": True})

        negative_rows = {
            "missing-schema": [(k, v) for k, v in rows if k != "roc_selector_schema"],
            "wrong-schema": [(k, "1" if k == "roc_selector_schema" else v) for k, v in rows],
            "missing-hook-key": [(k, v) for k, v in rows if k != "roc_selector_apply"],
            "missing-hook-call": [(k, "echo roc_selector_apply" if k == "boot_normal" else v) for k, v in rows],
            "bad-saved": rows + [("roc_saved_model", "madeup")],
            "bad-next": rows + [("roc_next_model", "madeup"), ("roc_next_start", "1")],
            "next-start-zero": rows + [("roc_next_start", "0")],
            "next-start-two": rows + [("roc_next_model", "rgsp"), ("roc_next_start", "2")],
            "next-without-start": rows + [("roc_next_model", "rgsp")],
            "start-without-next": rows + [("roc_next_start", "1")],
            "duplicate-schema": rows + [("roc_selector_schema", "2")],
            "duplicate-saved": rows + [("roc_saved_model", "rgsp"), ("roc_saved_model", "rg35xxh")],
        }
        for name, bad_rows in negative_rows.items():
            bad = work / (name + ".part")
            before = encode(bad_rows) + source_part[ENV_BYTES:]
            bad.write_bytes(before)
            for action in ("status", "clear-next", "save"):
                argv = ["--fixture", bad, action]
                if action == "save":
                    argv.append("rgsp")
                run_target(command, argv, success=False)
            require(bad.read_bytes() == before, f"Negative {name} mutated file")
            results.append({"case": name, "rejected_status_and_write": True, "unchanged": True})

        bad_crc = bytearray(original)
        bad_crc[64] ^= 1
        bad = work / "bad-crc.part"
        bad.write_bytes(bad_crc)
        run_target(command, ["--fixture", bad, "clear-next"], success=False)
        require(bad.read_bytes() == bad_crc, "Bad CRC wrote")
        wrong = work / "wrong-size.part"
        wrong.write_bytes(original[:-1])
        run_target(command, ["--fixture", wrong, "save", "rgsp"], success=False)
        link = work / "symlink.part"
        link.symlink_to(fixture.name)
        run_target(command, ["--fixture", link, "clear-next"], success=False)
        hardlink = work / "hardlink.part"
        os.link(fixture, hardlink)
        run_target(command, ["--fixture", hardlink, "clear-next"], success=False)
        hardlink.unlink()
        run_target(command, ["--partition", fixture, "clear-next"], success=False)
        fifo = work / "fifo"
        os.mkfifo(fifo)
        run_target(command, ["--fixture", fifo, "status"], success=False)
        run_target(command, ["--fixture", work, "status"], success=False)
        nonzero = work / "nonzero-padding.part"
        nonzero.write_bytes(encode(rows, padding=b"x") + source_part[ENV_BYTES:])
        run_target(command, ["--fixture", nonzero, "clear-next"], success=False)
        run_target(command, ["--fixture", fixture, "once", "rg35xx-h"], success=False)
        results += [{"case": name, "rejected": True} for name in
                    ("badCRC", "wrong-size", "symlink", "hardlink", "partition-kind-regular", "fifo", "directory", "nonzero-padding", "unknown-model")]

        json_cases = {
            "native": ('{"schema":2,"model_id":"rg35xxh","save_default":true}\n', True),
            "reordered": (' { "save_default": false, "model_id":"rgsp", "schema":2 } \r\n', True),
            "extra": ('{"schema":2,"model_id":"rg35xxh","save_default":true,"extra":0}', False),
            "duplicate": ('{"schema":2,"schema":2,"save_default":true}', False),
            "schema-string": ('{"schema":"2","model_id":"rg35xxh","save_default":true}', False),
            "schema-bool": ('{"schema":true,"model_id":"rg35xxh","save_default":true}', False),
            "schema-float": ('{"schema":2.0,"model_id":"rg35xxh","save_default":true}', False),
            "save-int": ('{"schema":2,"model_id":"rg35xxh","save_default":1}', False),
            "save-string": ('{"schema":2,"model_id":"rg35xxh","save_default":"true"}', False),
            "model-alias": ('{"schema":2,"model_id":"35XX H","save_default":true}', False),
            "escape": ('{"schema":2,"model_id":"rg35xx\\u0068","save_default":true}', False),
            "trailing": ('{"schema":2,"model_id":"rg35xxh","save_default":true}{}', False),
            "missing": ('{"schema":2,"model_id":"rg35xxh"}', False),
            "NUL": ('{"schema":2,"model_id":"rg35xxh","save_default":true}\0', False),
            "vertical-whitespace": ('\v{"schema":2,"model_id":"rg35xxh","save_default":true}', False),
            "oversize": (' ' * 513, False),
            "empty": ('', False),
        }
        for name, (text, valid) in json_cases.items():
            path = work / ("result-" + name + ".json")
            path.write_bytes(text.encode())
            value = run_target(command, ["--result", path], success=valid)
            if valid:
                require(value.stdout in ("model=rg35xxh\nsave=1\n", "model=rgsp\nsave=0\n"), "Result output unsafe/unexpected")
            else:
                require(value.stdout == "", "Bad JSON produced accepted fields")
            results.append({"case": "result-" + name, "accepted": valid})
        result_link = work / "result-symlink.json"
        result_link.symlink_to("result-native.json")
        run_target(command, ["--result", result_link], success=False)
        os.link(work / "result-native.json", work / "result-hardlink.json")
        run_target(command, ["--result", work / "result-hardlink.json"], success=False)
        run_target(command, ["--result", fifo], success=False)
        records.append({"architecture": architecture, "pass": True, "checks": len(results) + 3, "cases": results})
    result = {"pass": True, "source_prefix": str(args.prefix),
              "source_environment_sha256": sha(source_part[:ENV_BYTES]),
              "source_partition_sha256": sha(source_part), "original_rows": len(source_rows),
              "architectures": records,
              "hardware_io": False, "scope": "ordinary 16MiB fixtures derived from retained exact parent environment"}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"pass": True, "architectures": [{"name": r["architecture"], "checks": r["checks"]} for r in records]}))


if __name__ == "__main__":
    main()

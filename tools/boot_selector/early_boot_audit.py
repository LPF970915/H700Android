"""Bounded read-only audit of the pinned H700 pre-display boot path.

Emits engineering evidence, never patches a bootloader, image or device.
Run under WSL where the preserved Longan sources are available.
"""
from pathlib import Path
import hashlib
import json
import re
import struct


REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "out/rg34xx-boot-analysis-20261114"
OUT = REPO / "out/boot-selector-integration-20261114/early-hook"
UBOOT = REPO / "out/roc-os-h700-universal-rg35xxh-20261107/toc/16793600-u-boot.bin"
SOURCE = Path("/home/lpf/h700-android10/longan/brandy/brandy-2.0/u-boot-2018")
EXPECTED_SHA = "a11271e1276173cee48bd5705d068fd8446cfc0ffb43fca70b3b6808c2e9d0db"
BASE = 0x4A000000


def sha(value):
    return hashlib.sha256(value).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    raw = UBOOT.read_bytes()
    if len(raw) != 1048576 or sha(raw) != EXPECTED_SHA:
        raise ValueError("pinned ordinary U-Boot file differs")
    spans = {
        "early_display": (0x2A04, 0x2A2C),
        "workmode_display_dispatch": (0x297C, 0x299C),
        "sunxi_platform": (0xF1BC, 0xF1E4),
        "persistent_environment": (0xF174, 0xF1BC),
        "recovery_key_gpio": (0x33A0, 0x3410),
        "real_arm_relocation_loop": (0x136C, 0x13D4),
        "kernel_handoff": (0xF348, 0xF374),
    }
    disassembly = (DATA / "early-hook-audit/uboot-thumb.txt").read_text().splitlines()
    instructions = []
    for line in disassembly:
        match = re.match(r"\s*([0-9a-f]+):", line)
        if match:
            instructions.append((int(match[1], 16), line))
    evidence = {}
    for name, (start, end) in spans.items():
        fragment = raw[start:end]
        text = "\n".join(line for address, line in instructions if BASE + start <= address < BASE + end)
        (OUT / (name + ".txt")).write_text(text + "\n")
        evidence[name] = {"offset": hex(start), "end_exclusive": hex(end),
                          "bytes_hex": fragment.hex(), "sha256": sha(fragment)}
    table = []
    for offset, expected, role in (
        (0x9EE34, 0x4A002A05, "board_early_init_r: clocks then first display init"),
        (0x9EE60, 0x4A00F1BD, "initr_sunxi_plat: early logo, GPIO, recovery, storage"),
        (0x9EE64, 0x4A00F175, "initr_env: relocate/import environment"),
    ):
        pointer = struct.unpack_from("<I", raw, offset)[0]
        if pointer != expected:
            raise ValueError("unexpected actual init sequence")
        table.append({"cell": hex(offset), "pointer": hex(pointer), "role": role})
    sources = {}
    ranges = {
        "common/board_r.c": ((495, 548), (842, 851), (919, 934)),
        "board/sunxi/board_common.c": ((259, 271), (318, 338), (350, 391), (410, 444)),
        "drivers/video/sunxi/disp2/disp/dev_disp.c": ((343, 365), (580, 613)),
    }
    for relative, selections in ranges.items():
        contents = (SOURCE / relative).read_bytes()
        lines = contents.decode().splitlines()
        excerpt = "\n".join(f"{n}: {lines[n-1]}" for first, last in selections
                            for n in range(first, min(last, len(lines)) + 1))
        filename = relative.replace("/", "__") + ".excerpt.txt"
        (OUT / filename).write_text(excerpt + "\n")
        sources[relative] = {"sha256": sha(contents), "excerpt": filename,
                             "matches_actual_binary_build": "not established; use actual instruction receipts for addresses"}
    strings = {}
    for name in ("drv_disp_exit", "drv_disp_init", "boot_gui_init", "boot_gui_exit"):
        encoded = name.encode() + b"\0"
        offsets, cursor = [], 0
        while True:
            found = raw.find(encoded, cursor)
            if found < 0:
                break
            offsets.append(found)
            cursor = found + 1
        rows = []
        for offset in offsets:
            address = BASE + offset
            pointer_cells = [i for i in range(0, len(raw)-3, 4)
                             if struct.unpack_from("<I", raw, i)[0] == address]
            rows.append({"string_offset": hex(offset), "pointer_cells": list(map(hex, pointer_cells)),
                         "function_address": None})
        strings[name] = rows
    report = {
        "passed": True,
        "scope": "read-only actual-byte/source engineering audit; not a compiled selector or deliverable image",
        "uboot_sha256": sha(raw), "actual_init_order": table,
        "fragments": evidence, "generic_source_evidence": sources,
        "display_named_string_references": strings,
        "potential_minimum_architecture": [
            "Preserve clock initialization while deferring the first panel parse.",
            "Suppress/defer the platform early-logo call as well; it can invoke boot_gui_init before storage.",
            "After storage and environment import, read an explicit saved canonical model identifier.",
            "Resolve a complete model and panel-revision profile; update all early FDT values before first display init.",
            "For no saved record, obtain a screen-independent manual bootstrap selection before attempting the graphical selector, or first establish a physically working default profile for the target.",
            "Draw and poll gamepad controls only after a framebuffer and physical initialization are established.",
            "After confirmation, carry the same full profile to the loaded kernel FDT before bootm; geometry alone is insufficient.",
            "A saved preference must be readable before first display on the next cold boot; ordinary late bootcmd selection does not satisfy this.",
        ],
        "not_established": [
            "35H Test2 physical display failed despite an explicitly selected complete candidate; model selection alone cannot remedy that failure.",
            "A640x480 black canvas does not initialize an unknown physical panel.",
            "Cross-model early GPIO polarity, clocks/pinmux and input acceptance remain unverified.",
            "Generic drv_disp_exit/init functions do not prove that repeatedly changing timings is safe or that complete panel close/reset/reopen works in the pinned binary.",
            "Actual binary display-exit and boot-GUI framebuffer ABI have not been fully bound.",
            "No safe injected-code placement/copy/relocation extension is accepted by this audit.",
            "No existing persistent field or spare card sector is assigned; do not write random padding or user data.",
            "Only retained720 and explicit35H profiles exist; listing12models does not create the missing electrical profiles.",
        ],
        "actions": {"image_patch": False, "build": False, "device_query": False,
                    "card_io": False, "reboot": False, "security_change": False},
    }
    (OUT / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": True, "scope": report["scope"], "report": str(OUT / "result.json")}))


if __name__ == "__main__":
    main()

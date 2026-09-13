#!/usr/bin/env python3
"""Root-only Linux loop-device integration; never opens a physical card."""
import os
from pathlib import Path
import struct
import subprocess
import tempfile

from test_rgsp_capacity import BUILD, MIN_SIZE, START, make_gpt


def run(*args):
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"{args}: {result.returncode}\n{result.stdout}\n{result.stderr}")
    return result.stdout


def main():
    if os.geteuid():
        raise SystemExit("Run as root in WSL")
    with tempfile.TemporaryDirectory(prefix="block-test-", dir=BUILD) as temp:
        path = Path(temp) / "card.img"
        size = 125069950976
        head, tail = make_gpt(MIN_SIZE)
        with path.open("wb") as f:
            f.truncate(size)
            f.write(head)
            f.seek(MIN_SIZE - 1536)
            f.write(tail)
        loop = run("losetup", "--find", "--show", "--partscan", str(path)).strip()
        try:
            run("udevadm", "settle", "--timeout=15")
            assert loop.startswith("/dev/loop") and loop[9:].isdigit()
            def sectors():
                return int(run("blockdev", "--getsz", loop + "p8"))
            before = sectors()
            assert before == (MIN_SIZE - START - 1536) // 512
            print(run(str(BUILD / "grow-host"), "--apply", loop), flush=True)
            run("udevadm", "settle", "--timeout=15")
            assert sectors() == (size - START - 1536) // 512
            for _ in range(2):
                print(run(str(BUILD / "grow-host"), "--apply", loop), flush=True)
            with path.open("rb") as f:
                new = f.read(2048)
            assert new[1024:1920] == head[1024:1920]
            assert struct.unpack_from("<Q", new, 1960)[0] == size // 512 - 4
            print("LOOP_IOCTL_AND_REPEAT_VERIFIED", flush=True)
        finally:
            run("losetup", "--detach", loop)


if __name__ == "__main__":
    main()

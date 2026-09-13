"""Shell orchestration tests: temporary files and mocked device commands only."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MOCK = r'''#!/usr/bin/python3
import json, os, sys
from pathlib import Path
p=Path(os.environ["GROW_TEST_STATE"])
s=json.loads(p.read_text())
name=Path(sys.argv[0]).name
a=sys.argv[1:]
if name=="ld-linux-aarch64.so.1":
    name=Path(a[2]).name
    a=a[3:]
s["calls"].append([name]+a)
rc=0
if name=="rgsp-grow-gpt":
    rc=s["gpt_check"] if "--check" in a else s["gpt_apply"]
elif name=="rgsp-grow-fat":
    if "--check" in a:
        rc=0 if s["grown"] else 4
    else:
        rc=s["fat_apply"]
        if not rc: s["grown"]=True
elif name in ("fsck.fat", "check-fat.sh"):
    rc=s["fsck"]
p.write_text(json.dumps(s))
sys.exit(rc)
'''


class GrowShellTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root/"bin"
        self.bin.mkdir()
        self.grow = self.root/"grow"
        (self.grow/"lib").mkdir(parents=True)
        for path in [*(self.bin/n for n in ["mount", "umount", "sync", "reboot", "fsck.fat"]),
                     self.grow/"rgsp-grow-gpt", self.grow/"lib/ld-linux-aarch64.so.1"]:
            path.write_text(MOCK)
            path.chmod(0o755)
        # auto-grow invokes its checker explicitly with /bin/sh.
        (self.grow/"check-fat.sh").write_text(
            f'#!/bin/sh\nexec "{self.bin}/fsck.fat" "$@"\n')
        self.state_dir = self.root/"data"
        self.pending = self.state_dir/".rgsp-fat-grow-pending-v1"
        self.state = self.root/"state.json"
        self.save(dict(calls=[], gpt_check=0, gpt_apply=0, fat_apply=0, fsck=0, grown=False))
        script = (ROOT/"tools/rgsp_auto_grow.sh").read_text()
        script = script.replace("export PATH=/bin:/sbin:/usr/bin:/usr/sbin",
                                f"export PATH={self.bin}:/usr/bin:/bin")
        script = script.replace("state=/grow-state", f"state={self.state_dir}")
        script = script.replace("/grow/", str(self.grow)+"/")
        script = script.replace("/sbin/fsck.fat", str(self.bin/"fsck.fat"))
        script = script.replace("/sbin/reboot", str(self.bin/"reboot"))
        script = script.replace('[ -b "$disk" ] && [ -b "$roms" ] && [ -b "$data" ]', "true")
        script = script.replace('cat /sys/class/block/mmcblk0/size', "printf 244277248")
        self.script = self.root/"test.sh"
        self.script.write_text(script)

    def save(self, state):
        self.state.write_text(json.dumps(state))

    def load(self):
        return json.loads(self.state.read_text())

    def execute(self):
        return subprocess.run(["sh", self.script], capture_output=True, text=True, timeout=15,
                              env={**os.environ, "GROW_TEST_STATE": str(self.state)})

    def test_success_and_repeat(self):
        result = self.execute()
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertFalse(self.pending.exists())
        self.assertTrue((self.state_dir/".rgsp-capacity-v1").exists())
        self.save({**self.load(), "calls": []})
        self.assertEqual(self.execute().returncode, 0)
        self.assertFalse(any(c[0]=="rgsp-grow-fat" and "--check" not in c for c in self.load()["calls"]))

    def test_bad_gpt_does_not_touch_data(self):
        self.save({**self.load(), "gpt_check": 1})
        self.assertNotEqual(self.execute().returncode, 0)
        self.assertFalse(self.state_dir.exists())
        self.assertFalse(any(c[0]=="mount" for c in self.load()["calls"]))

    def test_failed_resize_retains_pending_and_refuses_retry(self):
        self.save({**self.load(), "fat_apply": 1})
        self.assertNotEqual(self.execute().returncode, 0)
        self.assertTrue(self.pending.exists())
        self.save({**self.load(), "calls": [], "fat_apply": 0})
        self.assertNotEqual(self.execute().returncode, 0)
        self.assertFalse(any(c[0]=="rgsp-grow-fat" for c in self.load()["calls"]))

    def test_bad_fat_does_not_apply_gpt(self):
        self.save({**self.load(), "fsck": 1})
        self.assertNotEqual(self.execute().returncode, 0)
        self.assertFalse(any(c[0]=="rgsp-grow-gpt" and "--apply" in c for c in self.load()["calls"]))

    def test_kernel_refresh_requests_restart_before_fat(self):
        self.save({**self.load(), "gpt_apply": 3})
        self.assertNotEqual(self.execute().returncode, 0)
        self.assertTrue(any(c[0]=="reboot" for c in self.load()["calls"]))
        self.assertFalse(any(c[0]=="rgsp-grow-fat" for c in self.load()["calls"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""Read-only guards, disabled replay, and real-file e2fsck option precedence."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/replay_rgsp_data_journal.sh"
MOCK = r'''#!/usr/bin/python3
import json, os, sys
from pathlib import Path
p = Path(os.environ["JOURNAL_STATE"])
s = json.loads(p.read_text())
name, args = Path(sys.argv[0]).name, sys.argv[1:]
s["calls"].append([name] + args)
root = Path(s["root"])
out, rc = "", 0
if name == "id":
    out = "0"
elif name == "findmnt":
    if "-S" in args:
        rc = s.get("mount_rc", 1)
    else:
        out = str(root / "dev/mmcblk0p5")
elif name == "blockdev":
    out = "17179869184"
elif name == "blkid":
    out = {"PARTUUID": s.get("guid", "734716ed-e7d9-e74f-9b3e-4f1cb8d448ed"),
           "UUID": "45daaa6e-724e-4d20-981c-602b3f72b8a2", "TYPE": "ext4"}[args[1]]
elif name == "dd":
    assert not any(a.startswith("of=") for a in args)
    out = "env"
elif name == "e2fsck":
    raise RuntimeError("The guarded helper must no longer invoke e2fsck")
elif name == "dumpe2fs":
    out = "Filesystem features: has_journal extent" + (" needs_recovery" if s.get("pending") else "")
elif name == "sync":
    pass
else:
    raise RuntimeError(name)
p.write_text(json.dumps(s))
print(out, end="")
sys.exit(rc)
'''


class DataJournalTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel, data in {
            "dev/mmcblk0p4": b"boot",
            "dev/mmcblk1p4": b"data",
            "sys/block/mmcblk0/device/cid": b"1d414455534400002000009f9401a1e7",
            "sys/block/mmcblk1/device/cid": b"fe3432534400000020000005bc01896b",
            "sys/class/power_supply/axp2202-usb/online": b"1",
        }.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (self.root / "bin").mkdir()
        for name in ("id", "findmnt", "blockdev", "blkid", "dd", "e2fsck", "dumpe2fs", "sync"):
            path = self.root / "bin" / name
            path.write_text(MOCK)
            path.chmod(0o755)
        text = SOURCE.read_text().replace(
            "export PATH=/usr/sbin:/usr/bin:/sbin:/bin",
            f"export PATH={self.root}/bin:/usr/bin:/bin")
        text = text.replace("/dev/mmcblk", f"{self.root}/dev/mmcblk")
        text = text.replace("/sys/", f"{self.root}/sys/")
        for key, data in (("BEFORE_SHA", b"data"), ("LINUX_SHA", b"boot"), ("ENV_SHA", b"env")):
            text = "\n".join(
                f"{key}={hashlib.sha256(data).hexdigest()}" if line.startswith(key + "=") else line
                for line in text.splitlines()) + "\n"
        self.script = self.root / "replay.sh"
        self.script.write_text(text)
        self.state = self.root / "state.json"
        self.state.write_text(json.dumps({"root": str(self.root), "calls": []}))

    def run_script(self, *args, **options):
        self.state.write_text(json.dumps({"root": str(self.root), "calls": [], **options}))
        return subprocess.run(["sh", str(self.script), *args], text=True, capture_output=True,
                              env={**os.environ, "JOURNAL_STATE": str(self.state)}, timeout=10)

    def calls(self):
        return json.loads(self.state.read_text())["calls"]

    def test_default_is_read_only(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(c[0] == "e2fsck" for c in self.calls()))

    def test_replay_disabled_before_probes(self):
        result = self.run_script("--replay")
        self.assertEqual(result.returncode, 3)
        self.assertIn("REPLAY_DISABLED", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_mounted_unknown_mount_state_or_wrong_guid_stops(self):
        for options in ({"mount_rc": 0}, {"mount_rc": 2}, {"guid": "wrong"}):
            with self.subTest(options=options):
                self.assertNotEqual(self.run_script("--check", **options).returncode, 0)
                self.assertFalse(any(c[0] == "e2fsck" for c in self.calls()))

    def test_changed_data_or_other_tf1_stops(self):
        for rel in ("dev/mmcblk1p4", "sys/block/mmcblk0/device/cid"):
            with self.subTest(rel=rel):
                path = self.root / rel
                original = path.read_bytes()
                path.write_bytes(b"different")
                self.assertNotEqual(self.run_script("--check").returncode, 0)
                self.assertFalse(any(c[0] == "e2fsck" for c in self.calls()))
                path.write_bytes(original)

    def test_missing_external_power_stops(self):
        (self.root / "sys/class/power_supply/axp2202-usb/online").write_text("0")
        self.assertNotEqual(self.run_script("--check").returncode, 0)
        self.assertFalse(any(c[0] == "e2fsck" for c in self.calls()))

    def test_unknown_mode_stops_before_probes(self):
        self.assertEqual(self.run_script("--repair").returncode, 2)
        self.assertEqual(self.calls(), [])


@unittest.skipUnless(shutil.which("mke2fs") and shutil.which("e2fsck"),
                     "Real e2fsprogs required for option-precedence regression")
class E2fsckOptionsTest(unittest.TestCase):
    def test_force_overrides_journal_only_on_a_disposable_regular_file(self):
        # This demonstrates the dangerous precedence, not a qualified replay path.
        env = {**os.environ, "LC_ALL": "C"}
        with tempfile.TemporaryDirectory(prefix="rgsp-journal-options-") as temp:
            image = Path(temp) / "test.ext4"
            with image.open("xb") as stream:
                stream.truncate(64 * 1024 * 1024)
            self.assertTrue(image.is_file())
            subprocess.run(["mke2fs", "-q", "-t", "ext4", "-F", str(image)],
                           env=env, check=True, capture_output=True, timeout=30)
            plain = subprocess.run(["e2fsck", "-E", "journal_only", "-y", str(image)],
                                   env=env, text=True, capture_output=True, timeout=30)
            self.assertEqual(plain.returncode, 0, plain.stdout + plain.stderr)
            self.assertNotIn("Pass 1:", plain.stdout + plain.stderr)
            forced = subprocess.run(["e2fsck", "-E", "journal_only", "-fy", str(image)],
                                    env=env, text=True, capture_output=True, timeout=30)
            self.assertEqual(forced.returncode, 0, forced.stdout + forced.stderr)
            self.assertIn("Pass 1:", forced.stdout + forced.stderr)


if __name__ == "__main__":
    unittest.main()

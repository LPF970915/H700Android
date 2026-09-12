#!/usr/bin/env python3
"""Boot-only flow tests on temporary regular files, never physical devices."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/prepare_rgsp_fix72_boot_only.sh"
GUIDS = [
    "0720745f-bbfb-4940-bef7-8595c6f34f4b",
    "096d7fa1-62e8-c242-9876-cfdd5a92b8eb",
    "6aa8b46e-b96f-9545-bbfb-1b7d2bdc7da8",
    "734716ed-e7d9-e74f-9b3e-4f1cb8d448ed",
    "324a1514-de37-6344-8d09-ed5dd8b90da2",
]
MOCK = r'''#!/usr/bin/python3
import json, os, sys
from pathlib import Path
sfile = Path(os.environ["BOOT_MOCK_STATE"])
s = json.loads(sfile.read_text())
name, a = Path(sys.argv[0]).name, sys.argv[1:]
s["calls"].append([name] + a)
out, rc = "", 0
root = Path(s["root"])
if name == "id":
    out = str(s.get("uid", 0))
elif name == "findmnt":
    if "-S" in a:
        rc = s.get("mount_error", 0 if s.get("mounted") else 1)
    else:
        out = str(root / "dev" / ("mmcblk1p1" if "--target" in a else "mmcblk0p5"))
elif name == "blockdev":
    out = str(67108864 if "mmcblk0" in a[-1] else
              [0, 268435456, 8589934592, 2147483648, 17179869184, 96883162624][int(a[-1][-1])])
elif name == "blkid":
    out = "wrong-guid" if s.get("bad_guid") else s["guids"][int(a[-1][-1])-1]
elif name == "e2fsck":
    rc = 4 if s.get("dirty_fs") or s.get("dirty_fs_part") == Path(a[-1]).name else 0
    out = "\n".join("Pass %d: Checking" % n for n in range(1, 6))
    if s.get("counter_warning"):
        out += "\nFree blocks count wrong (12, counted=13).\nFix? no\n"
elif name == "tune2fs":
    rc = s.get("header_rc", 0)
    pending = s.get("recovery_part") == Path(a[-1]).name
    out = ("Filesystem features: has_journal extent" +
           (" needs_recovery" if pending else "") +
           "\nFilesystem state: " + s.get("fs_state", "clean"))
    if s.get("missing_header"):
        out = "unknown header"
elif name == "gzip":
    out = "template"
elif name == "python3":
    Path(a[1]).write_bytes(b"new-boot")
    if s.get("power_lost_after_build"):
        (root / "sys/class/power_supply/axp2202-usb/online").write_text("0")
elif name == "dd":
    src = Path(next(v[3:] for v in a if v.startswith("if=")))
    dst = next((v[3:] for v in a if v.startswith("of=")), None)
    if not src.is_relative_to(root) or (dst and not Path(dst).is_relative_to(root)):
        raise RuntimeError("Test attempted access outside fixture")
    if dst:
        if s.get("fail_boot_write") and src.name == "boot.img":
            Path(dst).write_bytes(b"partial")
            rc = 1
        elif s.get("fail_rollback") and src.name == "rgsp-linux-boot-original.img":
            rc = 1
        else:
            Path(dst).write_bytes(src.read_bytes())
    else:
        out = src.read_text()
elif name == "sync":
    pass
else:
    rc = 99
sfile.write_text(json.dumps(s))
if out:
    sys.stdout.write(out)
sys.exit(rc)
'''


class BootOnlyTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in ("bin", "dev", "boot", "run", "sys/block/mmcblk0/device",
                    "sys/block/mmcblk1/device", "sys/class/power_supply/axp2202-usb"):
            (self.root / rel).mkdir(parents=True, exist_ok=True)
        self.boot = self.root / "boot"
        files = {
            "dev/mmcblk0p4": b"linux-boot",
            "dev/mmcblk0p3": b"env",
            "dev/mmcblk1p2": b"system",
            "dev/mmcblk1p3": b"vendor",
            "dev/mmcblk1p4": b"user-data",
            "boot/rgsp-linux-boot-original.img": b"linux-boot",
            "boot/h700-android10-b3-diag3-boot.img.gz9": b"template",
            "boot/ramdisk-a10-handoff-fix67.gz": b"ramdisk",
            "sys/block/mmcblk0/device/cid": b"1d414455534400002000009f9401a1e7",
            "sys/block/mmcblk1/device/cid": b"fe3432534400000020000005bc01896b",
            "sys/class/power_supply/axp2202-usb/online": b"1",
        }
        for path, content in files.items():
            (self.root / path).write_bytes(content)
        for command in ("id", "findmnt", "blockdev", "blkid", "e2fsck", "tune2fs",
                        "gzip", "python3", "dd", "sync"):
            path = self.root / "bin" / command
            path.write_text(MOCK)
            path.chmod(0o755)
        self.state = self.root / "state.json"
        self.state.write_text(json.dumps({"root": str(self.root), "guids": GUIDS, "calls": []}))
        script = SOURCE.read_text()
        script = script.replace("export PATH=/usr/sbin:/usr/bin:/sbin:/bin",
                                f"export PATH={self.root}/bin:/usr/bin:/bin")
        for old, new in (("/mnt/sdcard", str(self.boot)), ("/dev/mmcblk", f"{self.root}/dev/mmcblk"),
                         ("/sys/block/mmcblk", f"{self.root}/sys/block/mmcblk"),
                         ("/sys/class/power_supply", f"{self.root}/sys/class/power_supply"),
                         ("/run/rgsp-fix72-boot.", f"{self.root}/run/rgsp-fix72-boot.")):
            script = script.replace(old, new)
        values = {"LINUX_SHA": b"linux-boot", "ENV_SHA": b"env", "BASE_SHA": b"template",
                  "RAMDISK_SHA": b"ramdisk", "BOOT_SHA": b"new-boot",
                  "SYSTEM_SHA": b"system", "VENDOR_SHA": b"vendor",
                  "CODEC_VENDOR_SHA": b"codec-vendor",
                  "AUDIO_VENDOR_SHA": b"audio-vendor"}
        script = "\n".join(
            line.split("=", 1)[0] + "=" + hashlib.sha256(values[line.split("=", 1)[0]]).hexdigest()
            if line.split("=", 1)[0] in values else line for line in script.splitlines()) + "\n"
        self.script = self.root / "boot-only.sh"
        self.script.write_text(script)

    def configure(self, **changes):
        state = json.loads(self.state.read_text())
        state.update(changes)
        self.state.write_text(json.dumps(state))

    def run_script(self, *args, vendor=b"vendor"):
        result = subprocess.run(["sh", str(self.script), *args], capture_output=True, text=True,
                                timeout=15, env={**os.environ, "BOOT_MOCK_STATE": str(self.state)})
        for name, expected in (("mmcblk0p3", b"env"), ("mmcblk1p2", b"system"),
                               ("mmcblk1p3", vendor), ("mmcblk1p4", b"user-data")):
            self.assertEqual((self.root / "dev" / name).read_bytes(), expected)
        return result

    def test_default_check_does_not_write_boot_or_marker(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("FIX72_BOOT_ONLY_CHECK_OK", result.stdout)
        self.assertEqual((self.root / "dev/mmcblk0p4").read_bytes(), b"linux-boot")
        self.assertFalse((self.boot / "RGSP_ANDROID_TRY.ONCE").exists())
        self.assertFalse(list((self.root / "run").iterdir()))

    def test_prepare_only_writes_boot_and_marker(self):
        result = self.run_script("--prepare")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("FIX72_BOOT_ONLY_PREPARED", result.stdout)
        self.assertEqual((self.root / "dev/mmcblk0p4").read_bytes(), b"new-boot")
        self.assertTrue((self.boot / "RGSP_ANDROID_TRY.ONCE").is_file())

    def test_partial_boot_write_restores_linux(self):
        self.configure(fail_boot_write=True)
        result = self.run_script("--prepare")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("LINUX_BOOT_ROLLBACK_OK", result.stderr)
        self.assertEqual((self.root / "dev/mmcblk0p4").read_bytes(), b"linux-boot")
        self.assertFalse((self.boot / "RGSP_ANDROID_TRY.ONCE").exists())

    def test_failed_restore_reports_need_for_recovery(self):
        self.configure(fail_boot_write=True, fail_rollback=True)
        result = self.run_script("--prepare")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("LINUX_BOOT_ROLLBACK_FAILED", result.stderr)
        self.assertNotIn("FIX72_BOOT_ONLY_PREPARED", result.stdout)

    def test_unsafe_states_stop_before_write(self):
        for changes in ({"uid": 1000}, {"mounted": True}, {"dirty_fs": True}, {"bad_guid": True}):
            with self.subTest(changes=changes):
                self.configure(uid=0, mounted=False, dirty_fs=False, bad_guid=False)
                self.configure(**changes)
                result = self.run_script("--prepare")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual((self.root / "dev/mmcblk0p4").read_bytes(), b"linux-boot")
                self.assertFalse((self.boot / "RGSP_ANDROID_TRY.ONCE").exists())

    def test_existing_marker_is_preserved_and_blocks_prepare(self):
        marker = self.boot / "RGSP_ANDROID_TRY.ONCE"
        marker.write_text("existing")
        self.assertNotEqual(self.run_script("--prepare").returncode, 0)
        self.assertEqual(marker.read_text(), "existing")
        self.assertEqual((self.root / "dev/mmcblk0p4").read_bytes(), b"linux-boot")

    def test_power_loss_after_hash_and_build_blocks_boot_write(self):
        self.configure(power_lost_after_build=True)
        self.assertNotEqual(self.run_script("--prepare").returncode, 0)
        self.assertEqual((self.root / "dev/mmcblk0p4").read_bytes(), b"linux-boot")
        self.assertFalse((self.boot / "RGSP_ANDROID_TRY.ONCE").exists())

    def test_unknown_mount_status_blocks_boot_write(self):
        self.configure(mount_error=2)
        self.assertNotEqual(self.run_script("--prepare").returncode, 0)
        self.assertEqual((self.root / "dev/mmcblk0p4").read_bytes(), b"linux-boot")
        self.assertFalse((self.boot / "RGSP_ANDROID_TRY.ONCE").exists())

    def test_dirty_data_reports_partition_without_repair_or_boot_write(self):
        self.configure(dirty_fs_part="mmcblk1p4")
        result = self.run_script("--prepare")
        self.assertEqual(result.returncode, 4)
        self.assertIn("READONLY_FSCK_FAILED:", result.stderr)
        self.assertIn("mmcblk1p4 (exit 4)", result.stderr)
        self.assertIn("No repair performed.", result.stderr)
        self.assertEqual((self.root / "dev/mmcblk0p4").read_bytes(), b"linux-boot")
        self.assertFalse((self.boot / "RGSP_ANDROID_TRY.ONCE").exists())
        calls = json.loads(self.state.read_text())["calls"]
        fsck = [call for call in calls if call[0] == "e2fsck"]
        self.assertEqual(len(fsck), 3)
        self.assertTrue(all(call[1] == "-fn" for call in fsck))
        self.assertFalse(any(call[0] == "dd" and any(arg.startswith("of=") for arg in call)
                             for call in calls))

    def test_wrong_recovery_image_blocks_prepare(self):
        (self.boot / "rgsp-linux-boot-original.img").write_bytes(b"wrong")
        self.assertNotEqual(self.run_script("--prepare").returncode, 0)
        self.assertEqual((self.root / "dev/mmcblk0p4").read_bytes(), b"linux-boot")

    def test_pending_journal_blocks_even_when_fsck_would_return_zero(self):
        self.configure(recovery_part="mmcblk1p4")
        result = self.run_script("--prepare")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("EXT4_RECOVERY_OR_STATE_REVIEW_REQUIRED:", result.stderr)
        self.assertNotIn("FIX72_BOOT_ONLY_CHECK_OK", result.stdout)
        self.assertEqual((self.root / "dev/mmcblk0p4").read_bytes(), b"linux-boot")
        self.assertFalse((self.boot / "RGSP_ANDROID_TRY.ONCE").exists())
        calls = json.loads(self.state.read_text())["calls"]
        self.assertFalse(any(c[0] == "e2fsck" and c[-1].endswith("mmcblk1p4")
                             for c in calls))

    def test_unreadable_unknown_or_unclean_header_blocks_prepare(self):
        for changes in ({"header_rc": 1}, {"missing_header": True},
                        {"fs_state": "clean with errors"}):
            with self.subTest(changes=changes):
                self.configure(header_rc=0, missing_header=False, fs_state="clean")
                self.configure(**changes)
                self.assertNotEqual(self.run_script("--prepare").returncode, 0)
                self.assertEqual((self.root / "dev/mmcblk0p4").read_bytes(), b"linux-boot")
                self.assertFalse((self.boot / "RGSP_ANDROID_TRY.ONCE").exists())

    def test_real_ext4_header_gate_is_readonly_and_rejects_pending_recovery(self):
        if not all(shutil.which(c) for c in ("mke2fs", "debugfs", "tune2fs")):
            self.skipTest("e2fsprogs tools required")
        image = self.root / "header-test.img"
        with image.open("wb") as stream:
            stream.truncate(64 * 1024 * 1024)
        subprocess.run(["mke2fs", "-q", "-t", "ext4", "-F", str(image)],
                       check=True, capture_output=True, timeout=30)
        function = SOURCE.read_text().split("require_clean_ext4_header() {", 1)[1]
        function = function.split("\nrequire_clean_fsck() {", 1)[0]
        command = "require_clean_ext4_header() {" + function + '\nrequire_clean_ext4_header "$1"\n'
        for pending in (False, True):
            if pending:
                subprocess.run(["debugfs", "-w", "-R", "feature needs_recovery", str(image)],
                               check=True, capture_output=True, timeout=10)
            before = hashlib.sha256(image.read_bytes()).hexdigest()
            result = subprocess.run(["sh", "-c", command, "header-test", str(image)],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(hashlib.sha256(image.read_bytes()).hexdigest(), before)
            self.assertEqual(result.returncode, 1 if pending else 0, result.stderr)
            if pending:
                self.assertIn("EXT4_RECOVERY_OR_STATE_REVIEW_REQUIRED:", result.stderr)

    def test_zero_exit_with_counter_diagnostics_blocks_boot(self):
        self.configure(counter_warning=True)
        result = self.run_script("--prepare")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("READONLY_FSCK_DIAGNOSTICS_REVIEW_REQUIRED:", result.stderr)
        self.assertEqual((self.root / "dev/mmcblk0p4").read_bytes(), b"linux-boot")
        self.assertFalse((self.boot / "RGSP_ANDROID_TRY.ONCE").exists())

    def test_bad_mode_stops_before_probes(self):
        self.assertEqual(self.run_script("--force").returncode, 2)
        self.assertEqual(json.loads(self.state.read_text())["calls"], [])

    def test_unknown_profile_stops_before_probes(self):
        self.assertEqual(self.run_script("--prepare", "anything").returncode, 2)
        self.assertEqual(json.loads(self.state.read_text())["calls"], [])

    def test_codec_profile_is_explicit_and_exact(self):
        self.assertNotEqual(self.run_script("--prepare", "codec").returncode, 0)
        self.assertEqual((self.root / "dev/mmcblk0p4").read_bytes(), b"linux-boot")
        (self.root / "dev/mmcblk1p3").write_bytes(b"codec-vendor")
        self.assertNotEqual(self.run_script(vendor=b"codec-vendor").returncode, 0)
        result = self.run_script("--prepare", "codec", vendor=b"codec-vendor")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("FIX72_BOOT_PROFILE=codec", result.stdout)
        self.assertEqual((self.root / "dev/mmcblk0p4").read_bytes(), b"new-boot")

    def test_local_boot_rebuild_matches_hardware_verified_fix67(self):
        payload = ROOT / "out/h700-android10-b2"
        template = payload / "h700-android10-b3-diag3-boot.img.gz9"
        ramdisk = payload / "ramdisk-a10-handoff-fix67.gz"
        if not template.is_file() or not ramdisk.is_file():
            self.skipTest("Local proprietary boot inputs are not distributed")
        self.assertEqual(hashlib.sha256(template.read_bytes()).hexdigest(),
                         "6f65dd6571f80b07beb1329b058bb1f0b113c94f8d4f9f153fbd9f9274c2eb37")
        self.assertEqual(hashlib.sha256(ramdisk.read_bytes()).hexdigest(),
                         "8160e3a4f4f96a9b6985969003529263ce98a7719c6eb729b0a790a4bc16babd")
        boot = self.root / "actual-boot.img"
        boot.write_bytes(gzip.decompress(template.read_bytes()))
        code = SOURCE.read_text().split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
        result = subprocess.run([sys.executable, "-", str(boot), str(ramdisk)],
                                input=code, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(hashlib.sha256(boot.read_bytes()).hexdigest(),
                         "c3745e62bf2e965d7f798c7f2fa851ab43e67bcb463998156a9ccdcc59d06662")

    def test_audio_profile_requires_exact_image_and_is_check_only_by_default(self):
        self.assertNotEqual(self.run_script("--prepare", "audio").returncode, 0)
        (self.root / "dev/mmcblk1p3").write_bytes(b"audio-vendor")
        for args in ((), ("--prepare", "codec")):
            self.assertNotEqual(self.run_script(*args, vendor=b"audio-vendor").returncode, 0)
        result = self.run_script("--check", "audio", vendor=b"audio-vendor")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("FIX72_BOOT_PROFILE=audio", result.stdout)
        self.assertEqual((self.root / "dev/mmcblk0p4").read_bytes(), b"linux-boot")
        self.assertFalse((self.boot / "RGSP_ANDROID_TRY.ONCE").exists())
        result = self.run_script("--prepare", "audio", vendor=b"audio-vendor")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "dev/mmcblk0p4").read_bytes(), b"new-boot")

    def test_audio_profile_keeps_filesystem_and_rollback_guards(self):
        (self.root / "dev/mmcblk1p3").write_bytes(b"audio-vendor")
        self.configure(recovery_part="mmcblk1p4")
        result = self.run_script("--prepare", "audio", vendor=b"audio-vendor")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("EXT4_RECOVERY_OR_STATE_REVIEW_REQUIRED", result.stderr)
        self.assertEqual((self.root / "dev/mmcblk0p4").read_bytes(), b"linux-boot")
        self.configure(recovery_part=None, fail_boot_write=True)
        result = self.run_script("--prepare", "audio", vendor=b"audio-vendor")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("LINUX_BOOT_ROLLBACK_OK", result.stderr)
        self.assertEqual((self.root / "dev/mmcblk0p4").read_bytes(), b"linux-boot")


if __name__ == "__main__":
    unittest.main()

"""Local fixture tests. No physical devices, Android services or real mounts."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/probe_rgsp_software_codecs.sh"
MOCK = r'''#!/usr/bin/python3
import json, os, sys
from pathlib import Path
state = Path(os.environ["CODEC_STATE"])
s = json.loads(state.read_text())
root = Path(s["root"])
name, a = Path(sys.argv[0]).name, sys.argv[1:]
s["calls"].append([name] + a)
out, rc = "", 0
if name == "id":
    out = "0"
elif name == "getprop":
    out = s.get("product", "rgsp") if a[0] == "ro.product.device" else (
        "1" if a[0] == "sys.boot_completed" else "running")
elif name == "pidof":
    out = str(s.get("omx_pid", 1538)) if a == ["media.codec"] else "1498 1520 1937"
elif name == "mount":
    if s.get("mount_fail"):
        rc = 1
    else:
        with (root / "mounts").open("a") as f:
            f.write("rgsp-codec-probe " + str(root / "odm") + " tmpfs rw 0 0\n")
elif name == "umount":
    if s.get("umount_fail"):
        rc = 1
    else:
        f = root / "mounts"
        f.write_text("".join(x for x in f.read_text().splitlines(True)
                             if not x.startswith("rgsp-codec-probe ")))
        for f in (root / "odm").iterdir():
            if f.name != "build.prop":
                f.unlink()
elif name == "setprop":
    if a[-1] == "vendor.media.omx":
        s["omx_pid"] = s.get("omx_pid", 1538) + 1
elif name == "dumpsys":
    out = "mCurrentFocus=" + ("com.overdevs.at4k" if s.get("browser_fail") else
                              "org.chromium.webview_shell")
elif name in ("screencap", "uiautomator"):
    p = Path(a[-1])
    if not p.is_relative_to(root):
        raise RuntimeError("Non-fixture output")
    p.write_text("diagnostic")
elif name in ("am", "sleep"):
    pass
else:
    rc = 99
state.write_text(json.dumps(s))
if out:
    print(out)
sys.exit(rc)
'''


class CodecProfileTest(unittest.TestCase):
    def test_profile_only_imports_reviewed_software_catalogs(self):
        root = ET.parse(ROOT / "android/h700-android10/device/roc/rgsp/configs/media_codecs.xml").getroot()
        self.assertEqual(root.tag, "MediaCodecs")
        self.assertEqual([(e.tag, e.attrib) for e in root], [
            ("Include", {"href": "media_codecs_google_audio.xml"}),
            ("Include", {"href": "media_codecs_google_video.xml"}),
        ])

    def test_product_installs_catalog_and_both_includes(self):
        product = (ROOT / "android/h700-android10/device/roc/rgsp/h700_rgsp.mk").read_text()
        for source, name in (
            ("device/roc/rgsp/configs", "media_codecs.xml"),
            ("frameworks/av/media/libstagefright/data", "media_codecs_google_audio.xml"),
            ("frameworks/av/media/libstagefright/data", "media_codecs_google_video.xml"),
        ):
            self.assertIn(f"{source}/{name}:$(TARGET_COPY_OUT_VENDOR)/etc/{name}", product)
            self.assertEqual(product.count(f":$(TARGET_COPY_OUT_VENDOR)/etc/{name}"), 1)


class CodecProbeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in ("bin", "data", "dev", "odm", "sys/mmcblk0/device", "sys/mmcblk1/device"):
            (self.root / rel).mkdir(parents=True, exist_ok=True)
        (self.root / "odm/build.prop").write_text("original-build-properties\n")
        (self.root / "sys/mmcblk0/device/cid").write_text("1d414455534400002000009f9401a1e7")
        (self.root / "sys/mmcblk1/device/cid").write_text("fe3432534400000020000005bc01896b")
        (self.root / "mounts").write_text(f"{self.root}/dev/mmcblk1p3 /vendor ext4 ro,relatime 0 0\n")
        self.state = self.root / "state.json"
        self.state.write_text(json.dumps({"root": str(self.root), "calls": []}))
        script = SOURCE.read_text()
        script = script.replace("export PATH=/system/bin:/vendor/bin",
                                f"export PATH={self.root}/bin:/usr/bin:/bin")
        for old, new in (("/vendor/odm/etc", self.root / "odm"),
                         ("/data/local/tmp", self.root / "data"),
                         ("/dev/rgsp-codec-probe-build.prop", self.root / "dev/saved"),
                         ("/sys/block", self.root / "sys"),
                         ("/proc/mounts", self.root / "mounts"),
                         ("/dev/mmcblk1p3", self.root / "dev/mmcblk1p3")):
            script = script.replace(old, str(new))
        for name, expected in (
            ("media_codecs.xml", "152e5797f0b9a27101faf43614b438f6b75022e9c24423e333582dccbbaed3b4"),
            ("media_codecs_google_audio.xml", "f33464aee38c30e1fe52764bdb1d98ccd56a8214618d03b061b0fd63c38b0000"),
            ("media_codecs_google_video.xml", "876f5f850cbb5ce4f7a9582654ce006888903e6016dd0b8053e61ab0fd993839"),
        ):
            content = name.encode()
            (self.root / "data" / f"fix72-{name}").write_bytes(content)
            script = script.replace(expected, hashlib.sha256(content).hexdigest())
        self.script = self.root / "probe.sh"
        self.script.write_text(script)
        for name in ("id", "getprop", "pidof", "mount", "umount", "setprop", "dumpsys",
                     "am", "sleep", "screencap", "uiautomator"):
            target = self.root / "bin" / name
            target.write_text(MOCK)
            target.chmod(0o755)

    def configure(self, **changes):
        state = json.loads(self.state.read_text())
        state.update(changes)
        self.state.write_text(json.dumps(state))

    def run_probe(self, *args):
        result = subprocess.run(["sh", str(self.script), *args], capture_output=True,
                                text=True, timeout=15,
                                env={**os.environ, "CODEC_STATE": str(self.state)})
        self.assertEqual((self.root / "odm/build.prop").read_text(), "original-build-properties\n")
        return result

    def assert_restored(self):
        self.assertNotIn("rgsp-codec-probe", (self.root / "mounts").read_text())
        self.assertEqual([p.name for p in (self.root / "odm").iterdir()], ["build.prop"])
        self.assertFalse((self.root / "dev/saved").exists())

    def test_default_is_read_only(self):
        result = self.run_probe()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_restored()
        calls = json.loads(self.state.read_text())["calls"]
        self.assertFalse(any(c[0] in ("mount", "umount", "setprop", "am") for c in calls))

    def test_probe_restores_after_capture(self):
        result = self.run_probe("--probe")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CODEC_PROBE_CAPTURED_REVIEW_REQUIRED", result.stdout)
        self.assertIn("CODEC_PROBE_RESTORED", result.stdout)
        self.assert_restored()

    def test_browser_failure_still_restores(self):
        self.configure(browser_fail=True)
        result = self.run_probe("--probe")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CODEC_PROBE_RESTORED", result.stdout)
        self.assert_restored()

    def test_mount_failure_does_not_unmount_anything(self):
        self.configure(mount_fail=True)
        self.assertNotEqual(self.run_probe("--probe").returncode, 0)
        self.assert_restored()
        self.assertFalse(any(c[0] == "umount" for c in json.loads(self.state.read_text())["calls"]))

    def test_unmount_failure_is_reported_not_hidden(self):
        self.configure(umount_fail=True)
        result = self.run_probe("--probe")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CODEC_PROBE_CLEANUP_FAILED", result.stderr)
        self.assertNotIn("CODEC_PROBE_RESTORED", result.stdout)

    def test_wrong_payload_stops_before_mount(self):
        (self.root / "data/fix72-media_codecs.xml").write_text("wrong")
        self.assertNotEqual(self.run_probe("--probe").returncode, 0)
        self.assert_restored()

    def test_wrong_device_stops_before_mount(self):
        self.configure(product="another-device")
        self.assertNotEqual(self.run_probe("--probe").returncode, 0)
        self.assert_restored()

    def test_existing_config_is_preserved(self):
        extra = self.root / "odm/media_codecs.xml"
        extra.write_text("existing")
        self.assertNotEqual(self.run_probe("--probe").returncode, 0)
        self.assertEqual(extra.read_text(), "existing")
        self.assertNotIn("rgsp-codec-probe", (self.root / "mounts").read_text())

    def test_existing_foreign_mount_is_preserved(self):
        mounts = self.root / "mounts"
        original = mounts.read_text() + f"another-source {self.root}/odm tmpfs rw 0 0\n"
        mounts.write_text(original)
        self.assertNotEqual(self.run_probe("--probe").returncode, 0)
        self.assertEqual(mounts.read_text(), original)
        self.assertFalse(any(c[0] == "umount" for c in json.loads(self.state.read_text())["calls"]))


if __name__ == "__main__":
    unittest.main()

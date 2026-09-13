"""Host-only wallpaper export and firmware/APK contract tests."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEVICE = ROOT / "android/h700-android10/device/roc/rgsp"
IMAGE_SHA = "0d99ad08346620e240fa6eb7e765bb55996d4a311c8141a209626e08cad88997"
APK_SHA = "b2fa0343e903ad01c3854999dba70335ba4df5f5522dd931ed9d7189cf841a7d"


class WallpaperExportTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.storage = self.root / "storage"
        self.storage.mkdir()
        self.destination = self.storage / "Pictures/Wallpapers"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name, text in {
            "getprop": '#!/bin/sh\ncase "$1" in ro.product.device) echo "${MODEL:-rgsp}";; *) echo 1;; esac\n',
            "am": '#!/bin/sh\nif [ "$1" = get-current-user ]; then echo "${OWNER:-0}"; else printf "%s\\n" "$*" >> "$CALLS"; fi\n',
        }.items():
            path = self.bin / name
            path.write_text(text)
            path.chmod(0o755)
        text = (DEVICE / "rgsp-wallpapers.sh").read_text()
        text = text.replace("export PATH=/system/bin:/vendor/bin",
                            f"export PATH={self.bin}:/usr/bin:/bin")
        text = text.replace("/system/media/wallpapers", str(self.source))
        text = text.replace("/storage/emulated/0", str(self.storage))
        self.script = self.root / "export.sh"
        self.script.write_text(text)

    def run_export(self, **env):
        return subprocess.run(["sh", str(self.script)], text=True, capture_output=True,
                              timeout=10, env={**os.environ, "CALLS": str(self.root / "calls"),
                                               **env})

    def test_export_and_scan(self):
        (self.source / "one.jpg").write_bytes(b"original")
        result = self.run_export()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.destination / "one.jpg").read_bytes(), b"original")
        self.assertIn("MEDIA_SCANNER_SCAN_FILE", (self.root / "calls").read_text())
        self.assertFalse(list(self.destination.glob(".wallpaper.*")))

    def test_repeat_preserves_existing_file_and_adds_new_image(self):
        self.test_export_and_scan()
        (self.destination / "one.jpg").write_bytes(b"user version")
        (self.source / "two.jpg").write_bytes(b"second bundled image")
        self.assertEqual(self.run_export().returncode, 0)
        self.assertEqual((self.destination / "one.jpg").read_bytes(), b"user version")
        self.assertEqual((self.destination / "two.jpg").read_bytes(), b"second bundled image")
        self.assertEqual((self.root / "calls").read_text().count("MEDIA_SCANNER_SCAN_FILE"), 2)

    def test_symlink_destination_not_overwritten(self):
        self.destination.mkdir(parents=True)
        (self.source / "one.jpg").write_bytes(b"original")
        target = self.root / "elsewhere"
        target.write_bytes(b"keep")
        (self.destination / "one.jpg").symlink_to(target)
        self.assertEqual(self.run_export().returncode, 0)
        self.assertEqual(target.read_bytes(), b"keep")

    def test_empty_bundle_is_harmless(self):
        self.assertEqual(self.run_export().returncode, 0)
        self.assertFalse((self.root / "calls").exists())

    def test_unmounted_storage_is_not_created(self):
        self.storage.rmdir()
        self.assertEqual(self.run_export().returncode, 0)
        self.assertFalse(self.storage.exists())

    def test_other_model_or_user_rejected(self):
        for env in ({"MODEL": "other"}, {"OWNER": "10"}):
            self.assertNotEqual(self.run_export(**env).returncode, 0)
        self.assertFalse(self.destination.exists())

    def test_bundled_original_and_signed_prebuilt_contract(self):
        self.assertEqual(hashlib.sha256((DEVICE / "wallpapers/IMG_3111.jpg").read_bytes()).hexdigest(),
                         IMAGE_SHA)
        apk = DEVICE / "prebuilt/AT4K/AT4K.apk"
        self.assertEqual(hashlib.sha256(apk.read_bytes()).hexdigest(), APK_SHA)
        with zipfile.ZipFile(apk) as z:
            self.assertEqual(hashlib.sha256(z.read("res/raw/rgsp_wallpaper.jpg")).hexdigest(),
                             IMAGE_SHA)
            for info in z.infolist():
                if info.filename.endswith((".dex", ".so")):
                    self.assertEqual(info.compress_type, zipfile.ZIP_STORED, info.filename)
            dex = z.read("classes.dex")
            self.assertIn(b"Lcom/overdevs/at4k/RgspDefaults;", dex)
            self.assertIn(b"android.resource://com.overdevs.at4k/raw/rgsp_wallpaper", dex)
        self.assertIn("LOCAL_REPLACE_PREBUILT_APK_INSTALLED",
                      (DEVICE / "prebuilt/AT4K/Android.mk").read_text())
        for path in ("tools/set_rgsp_home.sh", "tools/verify_rgsp_compact_image.py",
                     "android/h700-android10/device/roc/rgsp/rgsp-firstboot.sh"):
            self.assertIn(APK_SHA, (ROOT / path).read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)

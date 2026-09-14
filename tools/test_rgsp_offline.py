#!/usr/bin/env python3
"""Host-only tests. Android commands are replaced with stateful temporary mocks."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

from inspect_rgsp_apk import assess, parse_badging
from audit_rgsp_services import package_paths

ROOT = Path(__file__).resolve().parents[1]
LEANBACK = "com.android.inputmethod.leanback/.service.LeanbackImeService"
LATIN = "com.android.inputmethod.latin/.LatinIME"
LAUNCHER = "com.android.launcher3/.Launcher"
AT4K = "com.overdevs.at4k/.MainActivity"

MOCK = r'''#!/usr/bin/python3
import json, os, sys
from pathlib import Path
p = Path(os.environ["MOCK_STATE"])
s = json.loads(p.read_text())
command = Path(sys.argv[0]).name
a = sys.argv[1:]
s["calls"].append([command] + a)
output, rc = "", 0
if command == "getprop":
    output = s["device"] if a[0] == "ro.product.device" else "1"
elif command == "id":
    output = str(s["uid"])
elif command == "am":
    if a[0] == "get-current-user":
        output = str(s["user"])
    else:
        rc = 1 if s.get("fail_launch", False) else 0
        output = "Status: error" if rc else "Status: ok"
elif command == "cmd":
    output = s["home"]
elif command == "settings":
    output = s["ime"]
elif command == "pm":
    if a[0] == "path":
        package = a[1]
        path = s["packages"].get(package, "")
        output = "package:" + path if path else ""
    elif a[0] == "install":
        s["packages"]["com.overdevs.at4k"] = s["at4k"]
        output = "Success"
    elif a[0] == "set-home-activity":
        if s.get("fail_set_home", False) and a[-1] == "com.overdevs.at4k/.MainActivity":
            rc = 1
        else:
            s["home"] = a[-1]
    else:
        rc = 2
elif command == "ime":
    if a[0] == "list":
        output = "\n".join(s["imes"])
    elif a[0] == "set":
        s["ime"] = a[-1]
    elif a[0] != "enable":
        rc = 2
elif command == "mockhome":
    s["home"] = "com.overdevs.at4k/.MainActivity"
    rc = 1 if s["fail_home"] else 0
else:
    rc = 2
p.write_text(json.dumps(s))
if output:
    print(output)
sys.exit(rc)
'''


class FirstbootTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name in ("getprop", "id", "am", "cmd", "settings", "pm", "ime", "mockhome"):
            command = self.bin / name
            command.write_text(MOCK)
            command.chmod(0o755)
        self.apk = self.root / "at4k.apk"
        self.apk.write_bytes(b"test fixture, not an APK")
        self.ime = self.root / "ime.apk"
        self.ime.write_bytes(b"IME fixture")
        self.hashfile = self.root / "ime.sha256"
        self.hashfile.write_text(hashlib.sha256(self.ime.read_bytes()).hexdigest() + "\n")
        self.helper = self.root / "home.sh"
        self.helper.write_text("mockhome\n")
        self.state = self.root / "state.json"
        self.save({"device": "rgsp", "uid": 0, "user": 0, "home": LAUNCHER,
                   "ime": LATIN, "imes": [LEANBACK, LATIN], "fail_home": False,
                   "at4k": str(self.apk), "calls": [], "packages": {
                       "com.android.launcher3": str(self.apk),
                       "com.android.inputmethod.leanback": str(self.ime),
                       "com.overdevs.at4k": str(self.apk)}})
        script = (ROOT / "android/h700-android10/device/roc/rgsp/rgsp-firstboot.sh").read_text()
        self.profile = self.root / "profile"
        self.staged = self.root / "missing-staged.apk"
        for before, after in (
            ("export PATH=/system/bin:/vendor/bin", f"export PATH={self.bin}:/usr/bin:/bin"),
            ("/data/local/rgsp-firstboot", str(self.profile)),
            ("/system/etc/rgsp/leanback.sha256", str(self.hashfile)),
            ("/data/rgsp-persist/provision/AT4K-launcher.apk", str(self.staged)),
            ("/system/bin/set_rgsp_home.sh", str(self.helper)),
            ("700276cb79c1e11e974c3fc10ab2edebbb2d381e5af8c60a241b52d3f6e039af",
             hashlib.sha256(self.apk.read_bytes()).hexdigest()),
        ):
            script = script.replace(before, after)
        self.script = self.root / "firstboot.sh"
        self.script.write_text(script)

    def save(self, state):
        self.state.write_text(json.dumps(state))

    def load(self):
        return json.loads(self.state.read_text())

    def run_script(self, mode="apply"):
        return subprocess.run(["sh", str(self.script), mode], text=True, capture_output=True,
                              timeout=15, env={**os.environ, "MOCK_STATE": str(self.state)})

    def test_success_and_repeat_preserves_later_user_choices(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        state = self.load()
        self.assertEqual(state["home"], AT4K)
        self.assertEqual(state["ime"], LEANBACK)
        self.assertTrue((self.profile / "complete-v1").is_file())
        state.update(home=LAUNCHER, ime=LATIN, calls=[])
        self.save(state)
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(self.load()["home"], LAUNCHER)
        self.assertEqual(self.load()["ime"], LATIN)

    def test_status_makes_no_profile_or_preferences(self):
        self.assertEqual(self.run_script("status").returncode, 0)
        self.assertFalse(self.profile.exists())
        self.assertEqual(self.load()["home"], LAUNCHER)

    def test_wrong_model_user_or_unprivileged_fails(self):
        for field, value in (("device", "another-h700"), ("user", 10), ("uid", 2000)):
            with self.subTest(field=field):
                original = self.load()
                self.save({**original, field: value})
                self.assertNotEqual(self.run_script().returncode, 0)
                self.assertFalse(self.profile.exists())
                self.save(original)

    def test_wrong_ime_hash_fails_before_preferences(self):
        self.ime.write_bytes(b"changed")
        self.assertNotEqual(self.run_script().returncode, 0)
        self.assertEqual(self.load()["ime"], LATIN)
        self.assertFalse((self.profile / "complete-v1").exists())
        self.assertFalse((self.profile / "lock").exists())

    def test_wrong_at4k_hash_fails_before_preferences(self):
        self.apk.write_bytes(b"changed")
        self.assertNotEqual(self.run_script().returncode, 0)
        self.assertEqual(self.load()["ime"], LATIN)

    def test_packaged_at4k_hash_is_accepted(self):
        text = self.script.read_text()
        text = text.replace(
            "b6b2a3db335e5f2a27c284fc48ece6de9ccaf46a8886222aef07c17a26ee5d5b",
            hashlib.sha256(b"packaged APK fixture").hexdigest())
        self.script.write_text(text)
        self.apk.write_bytes(b"packaged APK fixture")
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(self.load()["home"], AT4K)

    def test_missing_at4k_does_not_change_choices(self):
        state = self.load()
        del state["packages"]["com.overdevs.at4k"]
        self.save(state)
        self.assertNotEqual(self.run_script().returncode, 0)
        self.assertEqual(self.load()["ime"], LATIN)

    def test_dock_update_hash_is_accepted(self):
        text = self.script.read_text().replace(
            "8c2a7cc5c7bcf08706ffc13f6a2140bc52305f82299703006bc08a9bc557cf08",
            hashlib.sha256(b"dock APK fixture").hexdigest())
        self.script.write_text(text)
        self.apk.write_bytes(b"dock APK fixture")
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(self.load()["home"], AT4K)

    def test_factory_wallpaper_apk_is_accepted(self):
        text = self.script.read_text().replace(
            "b2fa0343e903ad01c3854999dba70335ba4df5f5522dd931ed9d7189cf841a7d",
            hashlib.sha256(b"factory APK fixture").hexdigest())
        self.script.write_text(text)
        self.apk.write_bytes(b"factory APK fixture")
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(self.load()["home"], AT4K)

    def test_install_local_apk_path(self):
        state = self.load()
        del state["packages"]["com.overdevs.at4k"]
        self.save(state)
        self.staged.write_bytes(self.apk.read_bytes())
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(any(c[:2] == ["pm", "install"] for c in self.load()["calls"]))

    def test_failed_home_rolls_back_both_choices(self):
        state = self.load()
        state["fail_home"] = True
        self.save(state)
        self.assertNotEqual(self.run_script().returncode, 0)
        state = self.load()
        self.assertEqual(state["ime"], LATIN)
        self.assertEqual(state["home"], LAUNCHER)
        self.assertFalse((self.profile / "complete-v1").exists())
        self.assertFalse((self.profile / "lock").exists())


class HomeDefaultsTest(unittest.TestCase):
    setUp = FirstbootTest.setUp
    save = FirstbootTest.save
    load = FirstbootTest.load

    def run_home(self, mode="at4k"):
        script = (ROOT / "tools/set_rgsp_home.sh").read_text()
        script = script.replace("export PATH=/system/bin:/vendor/bin",
                                f"export PATH={self.bin}:/usr/bin:/bin")
        script = script.replace("/data/local/tmp/rgsp-home.", str(self.root / "home."))
        script = script.replace(
            "8c2a7cc5c7bcf08706ffc13f6a2140bc52305f82299703006bc08a9bc557cf08",
            hashlib.sha256(b"test fixture, not an APK").hexdigest())
        path = self.root / "switch-home.sh"
        path.write_text(script)
        return subprocess.run(["sh", str(path), mode], text=True, capture_output=True,
                              timeout=15, env={**os.environ, "MOCK_STATE": str(self.state)})

    def test_home_xml_is_factory_home_only_with_dynamic_candidates(self):
        product = ROOT / "android/h700-android10/device/roc/rgsp"
        root = ET.parse(product / "configs/at4k-home.xml").getroot()
        self.assertEqual(root.tag, "preferred-activities")
        item, = root.findall("item")
        self.assertEqual(item.attrib, {"name": AT4K})
        self.assertEqual(item.findall("set"), [])
        filt, = item.findall("filter")
        self.assertEqual([(e.tag, e.get("name")) for e in filt], [
            ("action", "android.intent.action.MAIN"),
            ("cat", "android.intent.category.HOME"),
            ("cat", "android.intent.category.DEFAULT")])
        self.assertIn("configs/at4k-home.xml:$(TARGET_COPY_OUT_SYSTEM)/etc/"
                      "preferred-apps/at4k-home.xml",
                      (product / "h700_rgsp.mk").read_text())
        self.assertIn("system/etc/preferred-apps/at4k-home.xml",
                      (ROOT / "tools/verify_rgsp_compact_image.py").read_text())

    def test_dock_update_can_be_selected_without_touching_ime(self):
        result = self.run_home()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("HOME_SWITCH_OK", result.stdout)
        self.assertEqual(self.load()["home"], AT4K)
        self.assertEqual(self.load()["ime"], LATIN)
        self.assertIn(["pm", "set-home-activity", "--user", "0", AT4K],
                      self.load()["calls"])

    def test_unrecognized_apk_rejected_before_switch(self):
        self.apk.write_bytes(b"unknown")
        self.assertNotEqual(self.run_home().returncode, 0)
        self.assertEqual(self.load()["home"], LAUNCHER)
        self.assertFalse(any(c[:2] == ["pm", "set-home-activity"]
                             for c in self.load()["calls"]))

    def test_launch_failure_preserves_default(self):
        self.save({**self.load(), "fail_launch": True})
        self.assertNotEqual(self.run_home().returncode, 0)
        self.assertEqual(self.load()["home"], LAUNCHER)

    def test_switch_failure_restores_recovery_home(self):
        self.save({**self.load(), "fail_set_home": True})
        self.assertNotEqual(self.run_home().returncode, 0)
        self.assertEqual(self.load()["home"], LAUNCHER)
        self.assertIn(["pm", "set-home-activity", "--user", "0", LAUNCHER],
                      self.load()["calls"])

    def test_status_does_not_write_default(self):
        self.assertEqual(self.run_home("status").returncode, 0)
        self.assertEqual(self.load()["home"], LAUNCHER)
        self.assertFalse([p for p in self.root.glob("home.*") if p.is_dir()])


class ServiceInventoryTest(unittest.TestCase):
    def test_nested_product_and_module_aliases(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            for name, module, directory in (
                ("Settings", "Settings", "priv-app"),
                ("LatinIME", "LatinIME", "app"),
                ("Launcher3", "Launcher3QuickStep", "priv-app"),
                ("WebView", "webview", "app"),
            ):
                path = root / "system/product" / directory / module / (module + ".apk")
                path.parent.mkdir(parents=True)
                path.write_bytes(b"inventory fixture")
                self.assertEqual(package_paths(root, name), [path])
            (root / "product").symlink_to(root / "system/product", target_is_directory=True)
            self.assertEqual(len(package_paths(root, "Settings")), 1)
            self.assertEqual(package_paths(root, "Missing"), [])


class ApkTest(unittest.TestCase):
    def test_new_target_does_not_mean_new_minimum(self):
        meta = parse_badging("package: name='test.app' versionCode='1'\n"
                             "sdkVersion:'27'\ntargetSdkVersion:'36'\n")
        self.assertTrue(assess(meta, ["armeabi-v7a"])["static_candidate"])

    def test_minimum_abi_split_and_preview_blockers(self):
        for meta, abis in (({"min_sdk": "30"}, []), ({"min_sdk": "29"}, ["arm64-v8a"]),
                           ({"min_sdk": "Q"}, []),
                           ({"min_sdk": "29", "split": "config.en"}, [])):
            self.assertFalse(assess(meta, abis)["static_candidate"])
        self.assertFalse(assess({"min_sdk": "29"}, [], True)["static_candidate"])

    def test_pure_java_and_optional_minimum(self):
        meta = parse_badging("package: name='test.app' versionCode='1'\n")
        self.assertTrue(assess(meta, [])["static_candidate"])

    def test_badging_without_package_rejected(self):
        with self.assertRaises(ValueError):
            parse_badging("not a package")

    def test_indented_feature_groups(self):
        meta = parse_badging("package: name='test.app'\nfeature-group: label=''\n"
                             "  uses-feature: name='android.software.leanback'\n"
                             "  uses-feature-not-required: name='android.hardware.touchscreen'\n")
        self.assertEqual(meta["required_features"], ["android.software.leanback"])


if __name__ == "__main__":
    unittest.main()

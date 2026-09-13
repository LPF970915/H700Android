"""Host-only factory navigation provisioning, with stateful Android mocks."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = "com.roc.rgsp.navtrial/.NavigationService"
MOCK = r'''#!/usr/bin/python3
import json, os, sys
from pathlib import Path
p = Path(os.environ["MOCK_STATE"])
s = json.loads(p.read_text())
name, args = Path(sys.argv[0]).name, sys.argv[1:]
s["calls"].append([name] + args)
out, rc = "", 0
if name == "getprop":
    out = s["device"] if args[0] == "ro.product.device" else "1"
elif name == "am":
    out = str(s["user"])
elif name == "id":
    out = str(s["uid"])
elif name == "pm":
    out = "package:" + s["apk"] if s["apk"] else ""
elif name == "settings":
    action, key = args[2], args[4]
    if action == "get":
        out = s["settings"].get(key, "null")
    elif action == "delete":
        s["settings"].pop(key, None)
    elif s["fail_enable"] and key == "accessibility_enabled" and args[5] == "1":
        rc = 1
    else:
        s["settings"][key] = args[5]
p.write_text(json.dumps(s))
if out: print(out)
sys.exit(rc)
'''


class NavigationDefaultsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        for name in ("getprop", "am", "id", "pm", "settings"):
            path = bin_dir / name
            path.write_text(MOCK)
            path.chmod(0o755)
        app = self.root / "RGSPNavigation"
        app.mkdir()
        apk = app / "RGSPNavigation.apk"
        apk.touch()
        self.state = self.root / "state.json"
        self.save(dict(device="rgsp", user=0, uid=0, apk=str(apk),
                       calls=[], settings={}, fail_enable=False))
        self.profile = self.root / "profile"
        script = (ROOT / "android/h700-android10/device/roc/rgsp/"
                  "rgsp-navigation-defaults.sh").read_text()
        script = script.replace("export PATH=/system/bin:/vendor/bin",
                                f"export PATH={bin_dir}:/usr/bin:/bin")
        script = script.replace("/data/local/rgsp-navigation", str(self.profile))
        script = script.replace("/system/app/RGSPNavigation", str(app))
        self.script = self.root / "defaults.sh"
        self.script.write_text(script)

    def load(self):
        return json.loads(self.state.read_text())

    def save(self, data):
        self.state.write_text(json.dumps(data))

    def run_script(self):
        return subprocess.run(["sh", str(self.script)], capture_output=True, text=True,
                              timeout=15, env={**os.environ, "MOCK_STATE": str(self.state)})

    def test_fresh_enable_and_preserve_user_disable_on_repeat(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.load()["settings"]["enabled_accessibility_services"], COMPONENT)
        self.assertTrue((self.profile / "complete-v1").exists())
        state = self.load()
        state["settings"] = {"enabled_accessibility_services": "other/.Service",
                             "accessibility_enabled": "0"}
        self.save(state)
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(self.load()["settings"], state["settings"])

    def test_existing_service_list_preserved(self):
        state = self.load()
        state["settings"] = {"enabled_accessibility_services": "other/.Service"}
        self.save(state)
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(self.load()["settings"]["enabled_accessibility_services"],
                         "other/.Service:" + COMPONENT)

    def test_already_enabled_component_not_duplicated(self):
        state = self.load()
        state["settings"] = {"enabled_accessibility_services": COMPONENT}
        self.save(state)
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(self.load()["settings"]["enabled_accessibility_services"], COMPONENT)

    def test_failure_rolls_back_and_is_retryable(self):
        self.save({**self.load(), "fail_enable": True})
        self.assertNotEqual(self.run_script().returncode, 0)
        self.assertEqual(self.load()["settings"], {})
        self.assertFalse((self.profile / "complete-v1").exists())
        self.assertFalse((self.profile / "lock").exists())
        self.save({**self.load(), "fail_enable": False})
        self.assertEqual(self.run_script().returncode, 0)

    def test_wrong_model_user_or_uid_refused(self):
        for key, value in (("device", "other"), ("user", 10), ("uid", 2000)):
            with self.subTest(key=key):
                before = self.load()
                self.save({**before, key: value})
                self.assertNotEqual(self.run_script().returncode, 0)
                self.assertFalse(self.profile.exists())
                self.save(before)

    def test_missing_or_data_installed_package_refused(self):
        for apk in ("", "/data/app/unknown.apk"):
            self.save({**self.load(), "apk": apk})
            self.assertNotEqual(self.run_script().returncode, 0)
            self.assertFalse(self.profile.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)

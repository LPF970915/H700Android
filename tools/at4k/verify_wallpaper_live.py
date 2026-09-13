"""Exercise first-theme initialization without clearing launcher data."""
import argparse
from pathlib import Path
import subprocess
import time
import xml.etree.ElementTree as ET

PACKAGE = "com.overdevs.at4k"
PREFS = f"/data/user/0/{PACKAGE}/shared_prefs/launcher_prefs.xml"
REMOTE = "/data/local/tmp/rgsp-at4k-wallpaper-20260914"
URI = "android.resource://com.overdevs.at4k/raw/rgsp_wallpaper"


def values(xml):
    return {e.get("name"): (e.tag, e.get("value"), e.text)
            for e in ET.fromstring(xml)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", required=True)
    parser.add_argument("--device", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    def adb(*command):
        return subprocess.check_output(
            [args.adb, "-s", args.device, *command],
            timeout=30).decode("utf-8")

    def shell(*command):
        return adb("shell", *command)

    shell("am", "start", "-a", "android.settings.SETTINGS")
    shell("am", "force-stop", PACKAGE)
    before = shell("cat", PREFS)
    original = values(before)
    (args.out / "launcher_prefs.before.xml").write_text(before, encoding="utf-8")
    metadata = shell("stat", "-c", "%u:%g:%a", PREFS)
    shell("mkdir", "-p", REMOTE)
    shell("cp", PREFS, REMOTE + "/launcher_prefs.before.xml")
    root = ET.fromstring(before)
    for element in list(root):
        if element.get("name") in ("mode", "custom_wallpaper_uri"):
            root.remove(element)
    trial = args.out / "launcher_prefs.unset-theme.xml"
    ET.ElementTree(root).write(trial, encoding="utf-8", xml_declaration=True)
    adb("push", str(trial), REMOTE + "/launcher_prefs.trial.xml")
    try:
        shell("cp", REMOTE + "/launcher_prefs.trial.xml", PREFS)
        shell("restorecon", PREFS)
        if shell("stat", "-c", "%u:%g:%a", PREFS) != metadata:
            raise ValueError("Preference file ownership changed")
        shell("am", "start", "-n", PACKAGE + "/.MainActivity")
        time.sleep(4)
        after = shell("cat", PREFS)
        (args.out / "launcher_prefs.seeded.xml").write_text(after, encoding="utf-8")
        result = values(after)
        assert result["mode"] == ("string", None, "customi"), result.get("mode")
        assert result["custom_wallpaper_uri"] == ("string", None, URI)
        for key, value in original.items():
            if key not in ("mode", "custom_wallpaper_uri", "overlay_mode", "app_launch_count"):
                assert result[key] == value, key
        shell("screencap", "-p", REMOTE + "/wallpaper-default.png")
        adb("pull", REMOTE + "/wallpaper-default.png",
            str(args.out / "wallpaper-default.png"))
        shell("am", "start", "-a", "android.settings.SETTINGS")
        shell("am", "force-stop", PACKAGE)
        shell("am", "start", "-n", PACKAGE + "/.MainActivity")
        time.sleep(3)
        repeated = values(shell("cat", PREFS))
        assert repeated["mode"] == result["mode"]
        assert repeated["custom_wallpaper_uri"] == result["custom_wallpaper_uri"]
    except Exception:
        shell("am", "start", "-a", "android.settings.SETTINGS")
        shell("am", "force-stop", PACKAGE)
        shell("cp", REMOTE + "/launcher_prefs.before.xml", PREFS)
        shell("restorecon", PREFS)
        shell("am", "start", "-n", PACKAGE + "/.MainActivity")
        raise
    print("PASS: unset theme seeded, unrelated preferences preserved, app restart retained theme")
    print("SCREENSHOT=" + str(args.out / "wallpaper-default.png"))


if __name__ == "__main__":
    main()

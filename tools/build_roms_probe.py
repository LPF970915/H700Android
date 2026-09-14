#!/usr/bin/env python3
"""Build a local-only, ordinary-UID storage acceptance probe with AOSP tools."""
import argparse
import os
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--android", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    java = args.android/"prebuilts/jdk/jdk9/linux-x86"
    sdk = args.android/"prebuilts/sdk"
    jar = sdk/"29/public/android.jar"
    env = {**os.environ, "JAVA_HOME": str(java), "PATH": str(java/"bin")+":"+os.environ["PATH"]}

    def run(*cmd):
        subprocess.run(list(map(str, cmd)), env=env, cwd=out, check=True)

    classes, dex = out/"classes", out/"dex"
    classes.mkdir(exist_ok=True)
    dex.mkdir(exist_ok=True)
    (dex/"classes.dex").unlink(missing_ok=True)
    run(java/"bin/javac", "-source", "8", "-target", "8", "-classpath", jar,
        "-d", classes, *(ROOT/"tools/roms-probe").glob("*.java"))
    run(java/"bin/java", "-cp", sdk/"tools/lib/d8.jar", "com.android.tools.r8.D8",
        "--lib", jar, "--min-sdk-version", "26",
        "--output", dex, *classes.rglob("*.class"))
    unsigned = out/"probe-unsigned.apk"
    run(sdk/"tools/linux/bin/aapt", "package", "-f", "-M",
        ROOT/"tools/roms-probe/AndroidManifest.xml", "-I", jar, "-F", unsigned)
    with zipfile.ZipFile(unsigned, "a") as apk:
        apk.write(dex/"classes.dex", "classes.dex")
    key = out/"probe-debug.jks"
    if not key.exists():
        run(java/"bin/keytool", "-genkeypair", "-keystore", key, "-storepass", "android",
            "-keypass", "android", "-alias", "probe", "-dname", "CN=Local ROMS Probe",
            "-keyalg", "RSA", "-keysize", "2048", "-validity", "3650")
    signer = (java/"bin/java", "-jar", sdk/"tools/linux/lib/apksigner.jar")
    run(*signer, "sign", "--ks", key, "--ks-pass", "pass:android",
        "--key-pass", "pass:android", "--out", out/"RomsProbe.apk", unsigned)
    run(*signer, "verify", "--verbose", out/"RomsProbe.apk")


if __name__ == "__main__":
    main()

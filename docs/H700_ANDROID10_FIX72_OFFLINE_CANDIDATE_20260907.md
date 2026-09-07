# Fix72 Offline Candidate

Date: 2026-09-07. Product: h700_rgsp-eng, current no-stick RGSP only.
Parent Git baseline: `1879f4d` (Fix71).
No UART access, device writes, reboot, credentials or network connection in this batch.

## Build And Scope

The incremental `systemimage vendorimage ramdisk` build completed successfully.
Log: `out/logs/build/h700-low-pressure-20260907-155645.log`.
Service runtime: 4 min 46.613 sec; CPU time: 3 min 23.019 sec.
Memory peak: 5.0 GiB; swap peak: 512 MiB.

All future builds use `tools/build_h700_low_pressure.ps1 -Execute`.
The wrapper enforces CPU 0-1, aggregate CPUQuota=100%, `-j1`, MemoryHigh=5G,
MemoryMax=6G, MemorySwapMax=512M, nice 19 and idle I/O. It refuses insufficient
host RAM/disk and does not relax limits after a failure. Dry-run is the default.
The shell entry checks its cgroup limits and rejects unconstrained invocation.

Integrated into build inputs:

- RGSP compact LeanbackIME and calibrated A/DPAD editing adaptation from Fix71.
- Hash-checked local Fix67 Mali module and graphics init; automatic diagnostic
  screenshots disabled to avoid capturing later password entry.
- RGSP 720x480 display configuration; not a universal H700 profile.
- DocumentsUI and PackageInstaller; LatinIME and Launcher3 remain available.
- RGSP-only, explicit opt-in first-run helper and HOME helper.

This remains a build plus deployment-repair workflow, not two clean builds or
proof that unpatched build images reproduce the running device.

## Candidate

Fresh build staging: `out/rgsp-fix72-preflight/`.
Final candidate: `out/rgsp-fix72-wifi-profile/`.
The Fix70 package is unchanged. Only regular local image files were mounted.
An initial non-root mount attempt failed before patching; the incomplete copies
were discarded and packaging completed under WSL root.

Reproduce the final packaging from a new output directory:

```powershell
wsl.exe -d Ubuntu -u root -- taskset -c 0 nice -n 19 ionice -c 3 python3 /mnt/d/Works/H700Android/tools/prepare_rgsp_wifi_deployment.py --workspace /mnt/d/Works/H700Android --output /mnt/d/Works/H700Android/out/rgsp-fix72-wifi-profile --preflight /mnt/d/Works/H700Android/out/rgsp-fix72-preflight --wifi-fix70 /mnt/d/Works/H700Android/out/rgsp-fix70-wifi-home --include-profile
```

Final artifacts:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| system.raw.img | 8589934592 | `199c03bf5b46a81e26aab133d8310ae576690c99c926b1835d5f3e8ac3115faa` |
| vendor.raw.img | 2147483648 | `cb65140203807d0d80408e314f0c76554f2f81cd13fc76bf8ef07a4e46243c34` |
| ramdisk-a10-handoff-fix67.gz | 2605108 | `8160e3a4f4f96a9b6985969003529263ce98a7719c6eb729b0a790a4bc16babd` |
| AT4K-launcher.apk | 8374207 | `1315ef01d56511a80cb6bb4b9c58bfd3233c0e84cc1e82254cd0898d5dd26ca9` |

`DEPLOYMENT_MANIFEST.json` records `writes_performed=false`, parent hashes,
Fix70 hashes and the opt-in profile boundary. Both final ext4 checks passed.
`CONTENT_CHECKS.json` records 17 component hashes, including the keyboard,
installation components, first-run helpers and Wi-Fi/graphics assets.

Verification: 21 host-only tests passed (14 first-run/APK/inventory and seven
existing deployment-helper tests). Android 10 `host_init_verifier` accepted the
new first-run rc. Shell, Python and PowerShell syntax checks passed. Final raw
image and handoff hashes were re-read and matched the deployment manifest.
These tests use mocks for Android commands; no physical input result is implied.

The fresh build `ramdisk.img` is retained only in preflight. Deployment keeps
the verified Fix67 protected handoff. This package does not write TF1, U-Boot,
the partition table or data, and is NOT a standalone TF2 disk image.

## First-Run Contract

After boot completion, an operator can explicitly run
`sh /system/bin/rgsp-firstboot.sh apply` or request `sys.rgsp.firstboot=1`.
The default `status` mode is read-only. No automatic provisioning is enabled.

Apply requires RGSP, primary user, root, known IME/APK hashes, LatinIME and
Launcher3 recovery entries. If AT4K is absent, the operator must stage the known
APK at `/rgsp-persist/provision/AT4K-launcher.apk`; the helper installs it as
an ordinary app, selects LeanbackIME and requests AT4K HOME.
It saves previous selections and attempts rollback on preference failure.
After a successful completion marker, subsequent calls preserve user choices.

It does not supply network credentials, grant accessibility, disable installer
security or edit launcher licensing/private preferences. The layout workaround
remains AT4K Appearance / Desktop cards / Hide desktop cards. Existing app data
retains it; blank-data setup still requires that explicit UI step.
The helper and init are offline-tested, not yet qualified on the device.

## Services And APK Limits

The service audit inventories build files, not running services. It checks
system/product as well as top-level partitions and recognizes Launcher3QuickStep
and lowercase webview; the initial report missed these module paths.
The corrected report is `out/rgsp-fix72-services-reviewed.json`.
Presence of legacy power/vibrator libraries is not proof of a working backend.
Bluetooth/light/power/vibrator are absent from the main HIDL manifest inventory;
runtime service registration and real hardware behavior remain unqualified.
Audio policy includes resolve, but donor mixer values still need RGSP matching.
Inherited feature claims such as touch/camera/sensors also need hardware review.

`tools/inspect_rgsp_apk.py` provides API29/ARM32/split triage without installation.
AT4K 1.2 has minSdk 27 and ARM32 code; its targetSdk 36 is not its minimum OS.
Static candidacy is not signature verification or runtime compatibility.
ARM64-only, newer-minSdk and incomplete split packages cannot be treated as
installable single-APK candidates. GMS, DRM, WebView, touch-only UI, audio and
1 GiB memory remain per-app qualification items.

## Next Gates

1. Preserve rollback/data and qualify this candidate through protected handoff.
2. Physical keyboard A/DPAD/B/X and symbols; private password entry.
3. WPA2 authentication, DHCP, DNS, HTTPS, reconnect and reboot persistence.
4. DocumentsUI -> installer -> permission confirmation -> app -> AT4K with keys.
5. Blank-data first-run testing, then a separate TF2-independent boot design/test.
6. Real audio, battery/charging, brightness/power, Bluetooth and input fallback.
7. Sixty-minute stability, ten cold boots and two clean-build reproducibility.

Do not repeat long-press calibration now. Other H700 models must select/calibrate
their own profile before normal desktop use; analog-stick models need separate
axis calibration. APKs, proprietary inputs, images and private logs stay out of
this source/documentation commit.

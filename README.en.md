# ROC OS · H700 Android 10

**Android 10 adapted for H700 handhelds, with physical controls for devices without a touchscreen.**

[中文](README.md) · [Current status](docs/CURRENT_STATUS.md) · [Downloads and hashes](docs/PUBLIC_DOWNLOADS.md) · [Build guide](docs/PUBLIC_BUILD.md)

Updated **November 17, 2026**. The current release is **0.0.3**, one full-card image with a startup menu for twelve H700 models. It retains the Test11 stick repair, which the user confirmed works on **RG35XX H**. The 0.0.3 package is delivered locally; the public external download remains **0.0.1**, and the new package has not been uploaded.

## Current features

ROC OS provides D-pad navigation, a virtual mouse, a small-screen desktop, brightness and lid services, TF1 internal storage and TF2 external storage. It is an ARM64 Android 10 user build with ARM32 application support, SELinux Enforcing, production signing and authenticated USB ADB.

- Twelve-model startup selection with the corresponding resolution, saved defaults and reselection. RAM size and stick count do not block Android startup.
- Three panel trials and a loading message after confirmation.
- Navigation18 and framework guards for screen recovery, release/neutral input and held-key repeats, with limits on continuous navigation sessions.
- A shared stick driver with corrected ADC mode checks, separate directional and L3/R3 handling, calibration and resume neutral guards.
- Default 2GiB TF1 swap, the Lid4 service and a default time server.

Some third-party apps may still need the virtual mouse, and swap cannot resolve every application crash. The RG35XX H result does not establish hardware acceptance of all twelve models.

## Model selection

| Resolution | Models |
| --- | --- |
| 720×480 | 34XX, 34XXSP, RGSP |
| 720×720 | CubeXX |
| 640×480 | 35XX Plus, 35XX+ / 35XX 2025, 28XX, 35XX H, 40XX H, 40XX V, 35XXSP, 35XX Pro |

Lid handling is enabled for 34XXSP, RGSP and 35XXSP. Each model uses its own stick count and panel configuration; 28XX retains its rotated portrait-panel setup. All menu entries are enabled. Complete hardware coverage remains in progress.

On first boot, press power normally to enter the menu. The initial panel trial uses the 35XX H 640×480 configuration. If it is unreadable, press and fully release Volume Down to cycle **35XX H 640×480 → 34XXSP 720×480 → CubeXX 720×720**, rebooting back to the menu; Volume Up cycles in reverse. Once readable, choose the actual model. Saving a default skips the menu on later boots; Power + Volume Down opens reselection.

## Image and verification

| Item | Current status |
| --- | --- |
| Release file | `ROC_OS_ARM64_ver0.0.3.img.gz` |
| Compressed size | 591,772,793 bytes |
| gzip SHA256 | `34dcf5f43c0a75675530ff9b6c052351985d51b379a6e6189b388f331c6aaa52` |
| Expanded size | 32,434,554,368 bytes |
| Embedded version | `ROC_OS_ARM64_ver0.0.3` / `ro.roc.os.version=0.0.3` |
| Hardware evidence | The user confirmed the Test11 stick repair on RG35XX H; the newly packaged 0.0.3 image has not had a separate hardware acceptance run |
| Public download | External storage still hosts 0.0.1; see [downloads and exact file identity](docs/PUBLIC_DOWNLOADS.md) |

Use a TF1 card of at least 64GB and leave TF2 empty for the first test. Initial userdata preparation and allocation of the 2GiB swap file take time; later boots reuse it. See the [0.0.3 release notes](docs/ROC_OS_0.0.3_20261117.md) for the package changes, complete verification and hardware scope.

Navigation after resume, startup and sticks on other models, and power/USB behavior continue to be assessed from actual feedback. Historical test failures and their evidence remain in their dated records. See [current status](docs/CURRENT_STATUS.md).

## Source and community builds

The repository contains the H700 adaptation layer, source overlays, build and verification tools, and public engineering records. Large base archives and images use external storage. The current public Android overlay has **1,759 targets and 626 repository inputs**, including Navigation18 and the ViewRoot navigation guards.

A real production build of the framework, ART for both ABIs and dependent preopt has completed; its artifacts remain included in 0.0.3. The public build entry still extracts the **kernel, DTB, bootloader and base ramdisk from the pinned 0.0.1 image**. The scope of that Android userspace build and the author's incremental whole-card packaging is described in [build validation status](docs/PUBLIC_BUILD_STATUS.md). Current component sources and dependencies are listed in the [source map](docs/TEST10_SOURCE_MAP.md).

- [Public build guide](docs/PUBLIC_BUILD.md)
- [H616 base source provenance](docs/H616_ANDROID10_PROVENANCE_20260902.md)
- [Third-party sources and licenses](docs/THIRD_PARTY_INPUTS.md)
- [Version history](docs/HISTORY.md) and [tool index](tools/README.md)

Builders use their own signing keys. Official private keys, device identities and raw runtime logs are not published. The repository contains no game ROMs or commercial game resources; third-party components retain their own licenses.

## Feedback

Use [Issues](https://github.com/LPF970915/H700Android/issues) to report the model, full image filename/hash, reproduction steps, whether screen-off or lid closure preceded the issue, and available logs. Remove device identifiers, account and network information. Temporary recovery after a reboot does not establish a fix.

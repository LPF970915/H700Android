# ROC OS · H700 Android 10

**Android 10 adapted for H700 handhelds, with physical controls for devices without a touchscreen.**

[中文](README.md) · [Current status](docs/CURRENT_STATUS.md) · [Downloads and hashes](docs/PUBLIC_DOWNLOADS.md) · [Build guide](docs/PUBLIC_BUILD.md)

Updated **November 17, 2026**. The latest local test image is **0.0.2 Test10**, one full-card image with a menu for twelve H700 models. Packaging, complete independent verification and Windows SHA256 checks passed. Stick recovery and full model coverage on this image still need hardware confirmation. The public external download remains **0.0.1**; Test10 has not been uploaded.

## Current features

ROC OS provides D-pad navigation, a virtual mouse, a small-screen desktop, brightness and lid services, TF1 internal storage and TF2 external storage. It is an ARM64 Android 10 user build with ARM32 application support, SELinux Enforcing, production signing and authenticated USB ADB.

Test10 includes:

- Twelve-model startup selection with the corresponding resolution, saved defaults and reselection; RAM size and stick count do not block Android startup.
- Three panel trials and a loading message after confirmation.
- Navigation18 and framework navigation guards for screen recovery, release/neutral input, held-key repeats and session duration.
- A shared stick recovery candidate that separates ADC handling from L3/R3 clicks and preserves calibration and resume neutral guards.
- Default 2GiB TF1 swap, the Lid4 service and a default time server.

Inclusion in an image does not establish complete hardware acceptance. Some third-party apps still need the virtual mouse, and swap cannot resolve every application crash.

## Model selection

| Resolution | Models |
| --- | --- |
| 720×480 | 34XX, 34XXSP, RGSP |
| 720×720 | CubeXX |
| 640×480 | 35XX Plus, 35XX+ / 35XX 2025, 28XX, 35XX H, 40XX H, 40XX V, 35XXSP, 35XX Pro |

Lid handling is enabled for 34XXSP, RGSP and 35XXSP. Each model uses its own stick count and panel configuration; 28XX retains its rotated portrait-panel setup. All menu entries are enabled, while physical validation of all twelve models remains incomplete.

On first boot, press power normally to enter the menu. The initial panel trial uses the 35XX H 640×480 configuration. If it is unreadable, press and fully release Volume Down to cycle **35XX H 640×480 → 34XXSP 720×480 → CubeXX 720×720**, rebooting back to the menu; Volume Up cycles in reverse. Once readable, choose the actual model. Saving a default skips the menu on later boots; Power + Volume Down opens reselection.

## Image and verification

| Item | Current status |
| --- | --- |
| Latest local test file | `ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test10_StickRecovery_20261117.img.gz` |
| Compressed size | 591,771,367 bytes, approximately 592MB |
| gzip SHA256 | `ad6cec97dafc641cc4729273f3aea40dc4a4047cef32080bbbfbb88b056f8535` |
| Whole-card verification | All 32,434,554,368 expanded bytes compared; GPT, boot components, partitions and file metadata passed checks |
| Hardware status | Test10 sticks, navigation after resume, swap and full model coverage await confirmation |
| Public download | Still 0.0.1; see [downloads, exact identity and scope](docs/PUBLIC_DOWNLOADS.md) |

Use a TF1 test card of at least 64GB, leave TF2 empty and check the target card before writing. Initial userdata preparation and allocation of the 2GiB swap file take time; subsequent boots reuse it. See [Test10 engineering notes](docs/ROC_OS_H700_STICK_RECOVERY_TEST10_20261117.md) for test steps and the raw image hash.

The immediate checks are 34XXSP / 35XX H sticks, navigation after screen-off/unlock, display and swap on the same image. Wi-Fi, lid/suspend, USB recovery, automatic time/RTC retention and rare flicker require separate confirmation on this build. Older test-system issues remain in their historical records instead of being presented as confirmed Test10 defects. See [current status](docs/CURRENT_STATUS.md) and the [release overview](docs/RELEASE_OVERVIEW.md).

## Source and community builds

The repository contains the H700 adaptation layer, source overlays, build and verification tools, and public engineering records. Large base archives and images use external storage. The current public Android overlay has **1,759 targets and 626 repository inputs**, including Navigation18 and the ViewRoot navigation guards.

A real production build of the framework, ART for both ABIs and dependent preopt has completed and is included in Test10. The public build entry still extracts the **kernel, DTB, bootloader and base ramdisk from the pinned 0.0.1 image**. Rebuilding Android userspace with that guide does not reproduce the author's incremental Test10 boot/packaging chain from a clean clone in one step. Locations of the latest selector, model table, sticks, swap and packaging sources are listed in the [Test10 source map](docs/TEST10_SOURCE_MAP.md).

- [Public build guide](docs/PUBLIC_BUILD.md) and [validation scope](docs/PUBLIC_BUILD_STATUS.md)
- [H616 base source provenance](docs/H616_ANDROID10_PROVENANCE_20260902.md)
- [Third-party sources and licenses](docs/THIRD_PARTY_INPUTS.md)
- [Version history](docs/HISTORY.md) and [tool index](tools/README.md)

Builders use their own signing keys. Official private keys, device identities and raw runtime logs are not published. The repository contains no game ROMs or commercial game resources; third-party components retain their own licenses.

## Feedback

Use [Issues](https://github.com/LPF970915/H700Android/issues) to report the model, full image filename/hash, reproduction steps, whether screen-off or lid closure preceded the issue, and available logs. Remove device identifiers, account and network information. Temporary recovery after a reboot does not establish a fix.

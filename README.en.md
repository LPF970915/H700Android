# ROC OS · H700 Android 10

**Android 10 adapted for H700 handhelds, with physical controls for devices without a touchscreen.**

[中文](README.md) · [Current status](docs/CURRENT_STATUS.md) · [Downloads and hashes](docs/PUBLIC_DOWNLOADS.md) · [Build guide](docs/PUBLIC_BUILD.md)

**Current release 0.0.4 · November 22, 2026.** One TF1 card image supports twelve H700 models. From a fresh card, press Power and wait for the selector. Each Volume press and release switches panels and restarts the menu. Wait for the menu to start again between presses.

| Model | Volume key from a fresh boot |
| --- | --- |
| 35XX H, Plus, 2025, 28XX, 35XX Pro, 35XX SP | None |
| 40XX V, 40XX H | Down once |
| 34XX SP, RGSP | Down twice |
| 34XX (horizontal) | Up twice |
| CubeXX | Up once |

Choose your exact model with Left or Right. Press Down twice and A to start Android. To save the model for later boots, press Down, A, Down, A. This release also includes the standard Android A button mapping, digital trigger axes, an offline Pinyin keyboard, USB peripheral mode and a built-in gamepad checker.

[Boot guide in Chinese](docs/H700_BOOT_GUIDE_0.0.4_zh-CN.md) · [Release notes and checksums](docs/ROC_OS_0.0.4_20261122.md) · [Download share](docs/PUBLIC_DOWNLOADS.md)

## Source and community builds

The repository contains the H700 adaptation layer, source overlays, build and verification tools, and public engineering records. Large base archives and images use external storage. The current public Android overlay has **1,766 targets and 633 repository inputs**, including Navigation18 and the ViewRoot navigation guards.

A real production build of the framework, ART for both ABIs and dependent preopt has completed; its artifacts remain included in 0.0.4. The public build entry still extracts the **kernel, DTB, bootloader and base ramdisk from the pinned 0.0.1 image**. The scope of that Android userspace build and the author's incremental whole-card packaging is described in [build validation status](docs/PUBLIC_BUILD_STATUS.md). Current component sources and dependencies are listed in the [source map](docs/TEST10_SOURCE_MAP.md).

- [Public build guide](docs/PUBLIC_BUILD.md)
- [H616 base source provenance](docs/H616_ANDROID10_PROVENANCE_20260902.md)
- [Third-party sources and licenses](docs/THIRD_PARTY_INPUTS.md)
- [Version history](docs/HISTORY.md) and [tool index](tools/README.md)

Builders use their own signing keys. Official private keys, device identities and raw runtime logs are not published. The repository contains no game ROMs or commercial game resources; third-party components retain their own licenses.

## Feedback

Use [Issues](https://github.com/LPF970915/H700Android/issues) to report the model, full image filename/hash, reproduction steps, whether screen-off or lid closure preceded the issue, and available logs. Remove device identifiers, account and network information. Temporary recovery after a reboot does not establish a fix.

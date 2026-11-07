# ROC OS · H700 Android 10

**Android 10 adapted for H700 handhelds, with physical controls for devices without a touchscreen.**

[中文](README.md) · [Release status and known issues](docs/RELEASE_OVERVIEW.md) · [Project story and video outline](docs/PROJECT_STORY.md) · [Development branch](https://github.com/LPF970915/H700Android/tree/codex/rg34xxsp-at4k-input-lockscreen)

ROC OS began with Android boot and display bring-up on H700 hardware. It now includes controller navigation, a virtual mouse, a small-screen desktop, brightness and lid services, storage integration, and an ARM64 user build with production-signed candidate images. The main development and test device is the **RG34XXSP with H700, 2GB RAM and dual sticks**; earlier work also used the separate ANBERNIC RG SP model. **The project goal is one image usable across all H700 devices. Current RC5 hardware results cover only the RG34XXSP 2GB configuration; Bootfix1 is not yet hardware-tested, and universal H700 compatibility has not been achieved.**

**Status as of November 7, 2026: preparing for release. RC5 passed fresh-boot checks on hardware but still has four known functional issues. RC5 Bootfix1 passed offline packaging checks only and has not been flashed. A completed stable release has not been announced.**

## Hardware compatibility

Moving the current system card to the earlier development device, **ANBERNIC RG SP**, left it at the manufacturer logo with no Android USB/ADB detected by the computer. RG SP is a separate model, not shorthand for RG35XXSP. Its [official specifications](https://anbernic.com/products/rg-sp) list H700, 1GB RAM and a stickless design. Earlier RG SP results with older images do not establish compatibility with current candidates.

The source contains a blocking condition: startup requires the RG34XXSP stick module to load, while that module rejects devices with less than 1.5GiB RAM. This is consistent with the early stop, but no boot log was obtained; the actual stopping point and sole cause have not been proven. The internal `ro.product.device=rgsp` is a historical identifier, not RG SP autodetection or support. This compatibility failure is separate from the four RG34XXSP usage issues below.

A read-only audit found no device-serial or card-CID binding in the inspected growth script and layout; first-boot growth handles GPT/userdata, filesystem checks and resizing. Later adaptation fixed the global profile to `rg34xxsp` and made the previously model-optional stick module mandatory before Android init, narrowing compatibility. Under this source condition, a fresh card first booted in a 1GB RG SP would also be blocked; prior expansion on an RG34XXSP is not required. Restoring model-aware startup remains unfinished and should select modules by verified board capabilities while retaining GPIO/ADC and memory guards.

## Features

| Area | Implementation and scope |
| --- | --- |
| Physical controls | D-pad, confirm/back, Home quick settings and a Select-hold virtual mouse. Basic navigation passed on a fresh RC5 boot; intermittent focus issues after recovery remain open |
| Small-screen interface | Simplified Chinese defaults, AT4K desktop, landscape and system interface adaptations. Some third-party apps still need the virtual mouse |
| ARM64 | Complete ARM64 user build with an ARM32 application runtime. Actual 64-bit execution and Mali-G31 GLES verified; application compatibility varies |
| Storage | Unified TF1 internal storage and TF2 external storage implemented. Expansion, file persistence and TF2 checks exist for the Source64 engineering stage; the final user candidate needs scoped revalidation |
| Hardware | Brightness, Hall lid service, audio and Thermal HAL. Five temperature readings and speaker/headphone switching checked. Normal deep sleep, lid-open recovery and full power protection remain incomplete |
| Release engineering | User build, SELinux Enforcing, dedicated production signing, authenticated USB ADB, and partition, dependency, signature and whole-card SHA-256 checks |

The current desktop exposes seven entries: **AT4K, Gallery, Files, Settings, Calendar, Clock and Music**. Hidden launcher entries retain required components such as the WebView engine and content providers. Emulators, readers and media apps tried earlier are not the current clean candidate's bundled app list; optional apps are handled separately.

## Versions and known issues

| Version | Status |
| --- | --- |
| RC4 | Frozen controlled internal-test baseline, retained for comparison and rollback; not a stable release |
| RC5 | Current hardware-tested version. Fresh boot, seven desktop entries, basic navigation, five temperatures and release of the fixed bring-up wake lock passed their respective checks |
| RC5 Bootfix1 | Latest offline candidate, restoring the startup umask while retaining RC5 system/vendor. Hardware validation pending |

Four RC5 issues remain open:

- **Wi-Fi persistence:** saving failed on a clean first boot, and the user still had to re-enter the password after reboot. The cause is identified and Bootfix1 contains a targeted change; its hardware result is pending.
- **Lid-open wake:** the screen may remain black after screen-off/lid recovery. A short power-button press woke it in this test.
- **USB recovery:** the computer may stop enumerating the device after recovery, even after reconnecting the cable. A normal menu reboot temporarily restored USB in this test.
- **Settings focus jumps:** pressing Down may move focus back to the upper-right corner. Reboot temporarily suppressed the symptom; the cause remains unknown.

Release metadata, public debug defaults, redistribution permissions, real-card recovery/upgrade, final same-image validation and rebuild comparison still need completion. The diagnostic configuration retains a preauthorized workstation public key; authentication is enabled, root is refused and network ADB is disabled. All 116 APKs were checked against project production signing roles; the remaining `dev-keys` metadata does not mean they use public test private keys.

See the bilingual [release overview](docs/RELEASE_OVERVIEW.md) for image identities and validation boundaries.

## Images and installation

This repository contains adaptation code, configuration, build/checking tools and public engineering records. **This page does not yet designate a public image download.** Use the version notes, supported hardware, filename and SHA-256 explicitly provided in a future [Release](https://github.com/LPF970915/H700Android/releases). A source commit or documentation update does not mean an image has been uploaded.

Test images have been written with Rufus 4.7 to dedicated TF1 cards of at least 64GB. Whole-card flashing overwrites the target card: back up your data and verify the target disk. Do not assume the same image supports other H700 devices. Follow the exact image instructions for first boot, TF2 and upgrades.

## Source and scope

- This is an **H700 adaptation layer and engineering record** built on AOSP / Allwinner vendor foundations. Full AOSP/Longan trees, large vendor inputs and some graphics prebuilts are external. Cloning this repository alone is insufficient for a complete rebuild.
- The kernel, DTB and some vendor components are retained verified inputs. The project does not claim every component was written from scratch or rebuilt from open source.
- The default `main` code remains an older frozen layer. Newer adaptation source and RC4 records are on the [development branch](https://github.com/LPF970915/H700Android/tree/codex/rg34xxsp-at4k-input-lockscreen) and [RC4 tag](https://github.com/LPF970915/H700Android/tree/baseline/roc-os-user-rc4-pilot-20261107). Local RC5/Bootfix1 progress does not mean all corresponding source changes have been pushed.
- Images, signing private keys, device identifiers, raw device logs and Wi-Fi/account data are excluded from this documentation publication. The repository does not provide game ROMs or commercial game assets.
- Components retain their respective licenses and notices. No single license grants rights to all third-party content. See [third-party inputs](docs/THIRD_PARTY_INPUTS.md).

## Documentation and feedback

- [Bilingual release overview and known issues](docs/RELEASE_OVERVIEW.md)
- [Project story, video outline and narration draft, primarily Chinese](docs/PROJECT_STORY.md)
- [Historical versions](docs/HISTORY.md)
- [Early v5i source restoration and build notes](docs/REPRODUCE_BASELINE_20261028.md), a historical guide rather than an RC5 build recipe
- [Tool index](tools/README.md)

For [issue reports](https://github.com/LPF970915/H700Android/issues), include your model, image version/hash, reproduction steps, whether screen-off or lid recovery occurred, and whether the issue persists after reboot. Remove device identifiers, network names, IP addresses and account information from public logs.

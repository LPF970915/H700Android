# ROC OS · H700 Android 10

**Android 10 adapted for H700 handhelds, with physical controls for devices without a touchscreen.**

[中文](README.md) · [Release status and known issues](docs/RELEASE_OVERVIEW.md) · [Project story and video outline](docs/PROJECT_STORY.md) · [Development branch](https://github.com/LPF970915/H700Android/tree/codex/rg34xxsp-at4k-input-lockscreen)

ROC OS began with Android boot and display bring-up on H700 hardware. It now includes controller navigation, a virtual mouse, a small-screen desktop, brightness and lid services, storage integration, and an ARM64 user build with production-signed candidate images. The main development and test device is the **RG34XXSP with H700, 2GB RAM and dual sticks**; earlier work also used the separate ANBERNIC RG SP model. **The project goal is one image usable across all H700 devices. RC5 was tested on RG34XXSP 2GB; Universal Test1 passed fresh boot and basic controls on the original 1GB stickless RG SP. The full H700 model matrix remains incomplete.**

**Withdrawal, November 8, 2026: DisplayAuto Test2 is rejected following a physical display regression. It is no longer recommended and should not be flashed for further trials.** It passed offline checks, but selected 640×480 for the original RG SP 720 panel, causing corruption/ghosting; RG35XX H and RG34XXSP also have failure reports. `old`/`boe` alone cannot identify resolution. No replacement has passed this display validation. The incorrect criterion is being reverted while reliable identification is investigated. Earlier Universal Test1 RG SP results and the four RC5 issues retain their scope.

## Hardware compatibility

The older RC5/Bootfix1 startup path stopped at the logo when moved to the separate **ANBERNIC RG SP**. **Universal Test1 has now been flashed directly to that original RG SP and booted successfully**, without prior initialization or expansion on an RG34XXSP. Authenticated ADB confirmed approximately 1GB RAM, user/Enforcing and PID1 umask0000. Android continued with the specialized stick module unloaded. The user confirmed the system display, A unlock, Home quick settings, Select mouse and D-pad operation. Mali, five Thermal readings and 11 critical-file hashes passed checks. Android first appeared after about 122 seconds; the initial logo report for this new boot was followed by successful startup, not another failure.

RG SP is a separate model, not shorthand for RG35XXSP; its [official specifications](https://anbernic.com/products/rg-sp) list H700, 1GB RAM and no sticks. The older image required the RG34XXSP stick module, which rejects devices below 1.5GiB RAM. Universal Test1 removes that dependency from base startup while retaining module safety guards. The internal `ro.product.device=rgsp` is historical, not model autodetection. **Universal Test1 still needs RG34XXSP stick revalidation and other H700 coverage; the four existing runtime issues remain open.**

A read-only audit found no device-serial or card-CID binding in the inspected growth script and layout; first-boot growth handles GPT/userdata, filesystem checks and resizing. Later adaptation fixed the global profile to `rg34xxsp` and made the previously model-optional stick module mandatory before Android init, narrowing compatibility. Under this source condition, a fresh card first booted in a 1GB RG SP would also be blocked; prior expansion on an RG34XXSP is not required. **H700 Universal Test1 has completed offline verification.** Its separate boot layer makes the stick module optional: no sticks, 1GB memory, module refusal/absence, hash mismatch or ABI mismatch skips the extension, retains the original controller and continues Android. Module GPIO/ADC and memory guards remain intact; extension failure no longer gates system startup. The old mandatory-stop negative case and ten new shell-path checks passed; the actual packaged init/helper, 37 startup roots, ten paired ELFs, 116 APK signatures, full image ranges and gzip checks also passed. Original RG SP fresh boot passed; other models and same-image RG34XXSP stick revalidation remain pending. It reuses RC5 images18 system/vendor, the existing kernel/DTB and the umask000 correction without a full Android rebuild.

**Display compatibility limitation: Universal Test1 showed a black screen on RG35XX H; the subsequent DisplayAuto Test2 is now rejected for a regression.** The user reported no obvious power-on response on RG35XX H and a logo flash followed by black on RG34XXSP. On the original RG SP, authenticated ADB confirmed boot_completed=1 and user/Enforcing, but actual HWC output was 640×480/59.941Hz with corruption/ghosting on the physical 720 panel. This proves `lcd_type=old` does not establish a 640 panel. The new selection logic introduced this regression; there is no replacement display image or request for another blind flash. Offline checks do not establish runtime display acceptance, and the Hall initial-sample guard does not close suspend/resume issues. See the [withdrawal status and compatibility matrix](docs/RELEASE_OVERVIEW.md).

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
| RC5 | Earlier RG34XXSP hardware-tested version. Fresh boot, seven desktop entries, basic navigation, five temperatures and release of the fixed bring-up wake lock passed their respective checks |
| RC5 Bootfix1 | Completed offline startup candidate, restoring the umask while retaining RC5 system/vendor. Hardware validation pending |
| H700 Universal Test1 | Earlier universal-startup candidate with an optional stick extension. Whole-card and independent verification passed; original 1GB stickless RG SP fresh boot/basic controls passed; other models pending |
| H700 DisplayAuto Test2 | **Rejected / no longer recommended**: offline checks passed historically; incorrect panel selection caused a physical display regression. No replacement has passed display validation |

Four issues confirmed on RC5 remain open in later candidates:

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

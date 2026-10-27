# H700 Android 10 Development Kit

RGSP/H700 Android 10 porting workspace. The active branch targets the current
no-stick RGSP test unit first; other H700 devices require their own display and
input profiles.

## Current Baseline

- Current integration baseline: v5f ROMSPublic. AT4K is the factory HOME,
  with the corrected bottom shortcut row, menu scrolling and IMG_3111 as its
  initial custom-image wallpaper. Other bundled images can be added later.
- Accepted keyboard/Settings behavior, built-in gray focus navigation and
  the single-console fix are retained. AT4K layout/wallpaper and injected
  menu-navigation checks passed on the live device; complete fresh-flash
  and physical-key acceptance still require testing.
- The new ramdisk includes checked dirty-FAT/stale-FSInfo recovery.
  Earlier v5d physically failed a reboot and must not be treated as reboot
  qualified. v5f still needs two normal physical reboot checks after flashing.
- ROMS is now a visible portable volume managed by protected vold. The live
  device passed ordinary-app SAF read/write/rename/delete and remount
  persistence checks, showing about 96.91 GB for ROMS on the tested card.
  Internal app storage remains separate; its nominal 32 GB summary is not
  whole-card capacity. New ramdisk logs use private data instead of ROMS.
- This is a development integration checkpoint, not a production release.
  The v5f baseline manifest is authoritative for offline verification status;
  it does not establish physical boot qualification.
- Archived Fix72 and failed September 11 card records remain historical
  evidence. The old 8 MiB writer/finalizer remain quarantined.
- The Android 11 bring-up work is historical evidence only. Do not restart its
  framework-bypass patch chain.

Read these documents before changing images or device state:

- `docs/H700_V5F_ROMS_BASELINE.md`
- `docs/baselines/h700-v5f-roms/README.md`
- `docs/H700_ROMS_PUBLIC_STORAGE_20260914.md`
- `docs/H700_STORAGE_RUNTIME_DIAGNOSIS_20260914.md`
- `docs/H700_V5E_AT4K_BASELINE.md`
- `docs/baselines/h700-v5e-at4k/README.md`
- `docs/H700_AT4K_DEFAULT_HOME_20260914.md`
- `docs/H700_AT4K_DOCK_PATCH_20260913.md`
- `docs/H700_V5D_REBOOT_AND_VIDEO_20260913.md`
- `docs/H700_V5C_USER_ACCEPTANCE_20260913.md`
- `docs/H700_V5C_RUFUS_BOOT_HANDOFF_20260913.md`
- `docs/baselines/h700-v5c-20260913/README.md`
- `docs/H700_SINGLE_CARD_V5_BUILD_AND_ACCEPTANCE_20260912.md`
- `docs/H700_ANDROID10_FIX72_OFFLINE_CANDIDATE_20260907.md`
- `docs/H700_ANDROID10_FIX70_WIFI_HOME_20260907.md`
- `docs/H700_ANDROID10_FIX71_INPUT_DISPLAY_20260907.md`
- `docs/RGSP_INPUT_CALIBRATION_20260906.md`
- `docs/H700_ANDROID10_TV_NETWORK_PLAN_20260906.md`
- `docs/H700_FIX72_BASELINE_CLEANUP_20260907.md`
- `docs/H700_ANDROID10_RELEASE_READINESS_20260911.md`

## Working Boundaries

- Build only through `tools/build_h700_low_pressure.ps1 -Execute`. It constrains
  compilation to CPU 0-1, aggregate one CPU, `-j1`, 6 GiB RAM and 512 MiB swap.
- The old TF2 guarded deployment tool is for the historical dual-card layout,
  not the current eight-partition single-card product. Diagnose and validate
  reversible runtime changes first; rebuild and flash only after acceptance.
  Do not write boot0, U-Boot, GPT or device data through ad hoc commands.
- Retain `out/rgsp-fix72-wifi-profile/`, `out/rgsp-fix70-wifi-deployment/`,
  `out/tf2-deploy-20260907/`, `out/h700-android10-preflight/`, and the Fix67
  payloads where retained. Preserve the v5d packaging input, v5e/v5f outputs,
  manifests, WSL source/build outputs and all available rollback inputs.
  The old v5c image is no longer present locally.
- Full upstream sources, complete images, private logs, signing keys and the
  WSL VHDX remain local. The selected product APK, bundled wallpapers and
  sanitized image manifests are versioned with the integration source.

## Active Tooling

```powershell
# Inspect a boot image without modifying it.
py -3 .\tools\android_bootimg.py inspect .\input\boot.img

# Dry-run the low-pressure Android build wrapper.
.\tools\build_h700_low_pressure.ps1

# Inspect an APK for API29/ARM32/split-package candidacy.
py -3 .\tools\inspect_rgsp_apk.py "C:\path\to\app.apk"

# Capture or apply only the explicit per-device input calibration flow.
.\tools\capture_rgsp_input_calibration.ps1
```

The current RGSP profile supports basic UI navigation only. Long-press behavior,
analog axes, model-specific mapping selection, and virtual-mouse fallback remain
separate follow-up work.

## Release Boundary

The current priority is to qualify the Scheme-A single-card Android image on
the original RGSP. The compact image requires at least 32,434,554,368 actual
bytes and targets 64 GB or larger supported cards. It contains the H700 boot
payload, Android boot/system/vendor/data, and a FAT32 `ROMS` partition.
Actual boot-area contents must be read back before another write. The second TF
slot is expected to remain optional expansion storage, but that behavior must
be verified on hardware.

Do not publish until the release-readiness checklist is closed. In particular,
single-card boot success alone does not prove cold-boot reliability, suspend
resume, physical-button APK workflows, audio/power acceptance, or reproducible
image production.

## Storage And Recovery

The project keeps large files under `D:\Works\H700Android`; WSL lives in
`.wsl\Ubuntu\`. The 2026-09-07 cleanup removed only checked historical outputs
and superseded scripts. The cleanup record explains what was removed and how to
regenerate raw preflight images when required.

`reference/` contains selected external references rather than full AOSP
checkouts. The authoritative Android 10 planning/history set is under `docs/`;
Fix64 through Fix72 are the current implementation evidence.

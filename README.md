# H700 Android 10 Development Kit

RGSP/H700 Android 10 porting workspace. The active branch targets the current
no-stick RGSP test unit first; other H700 devices require their own display and
input profiles.

## Current Baseline

- Frozen source baseline: `baseline/rgsp-fix72-offline-20260907`
  (`e3566a9cfbf0d86dbb576631497adc6ea5ee94ce`).
- Current candidate: Fix72 offline package. It includes the Fix70 Wi-Fi/HOME
  deployment path and Fix71 calibrated basic A/DPAD behavior.
- Hardware qualification is still pending. Fix72 is not a standalone TF2 boot
  system and has not yet proven Wi-Fi authentication, APK installation, or
  long-run stability on the RGSP.
- The Android 11 bring-up work is historical evidence only. Do not restart its
  framework-bypass patch chain.

Read these documents before changing images or device state:

- `docs/H700_ANDROID10_FIX72_OFFLINE_CANDIDATE_20260907.md`
- `docs/H700_ANDROID10_FIX70_WIFI_HOME_20260907.md`
- `docs/H700_ANDROID10_FIX71_INPUT_DISPLAY_20260907.md`
- `docs/RGSP_INPUT_CALIBRATION_20260906.md`
- `docs/H700_ANDROID10_TV_NETWORK_PLAN_20260906.md`
- `docs/H700_FIX72_BASELINE_CLEANUP_20260907.md`

## Working Boundaries

- Build only through `tools/build_h700_low_pressure.ps1 -Execute`. It constrains
  compilation to CPU 0-1, aggregate one CPU, `-j1`, 6 GiB RAM and 512 MiB swap.
- Use `tools/invoke_rgsp_tf2_guarded_deploy.ps1` for device deployment. Do not
  write TF1, U-Boot, boot0, GPT, or device data through ad hoc commands.
- Retain `out/rgsp-fix72-wifi-profile/`, `out/rgsp-fix70-wifi-deployment/`,
  `out/tf2-deploy-20260907/`, `out/h700-android10-preflight/`, and the Fix67
  payloads. They are the current candidate, rollback inputs, and protected
  handoff chain.
- Full sources, images, private logs, APK inputs, and the WSL VHDX remain local
  and are intentionally excluded from Git.

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

## Storage And Recovery

The project keeps large files under `D:\Works\H700Android`; WSL lives in
`.wsl\Ubuntu\`. The 2026-09-07 cleanup removed only checked historical outputs
and superseded scripts. The cleanup record explains what was removed and how to
regenerate raw preflight images when required.

`reference/` contains selected external references rather than full AOSP
checkouts. The authoritative Android 10 planning/history set is under `docs/`;
Fix64 through Fix72 are the current implementation evidence.

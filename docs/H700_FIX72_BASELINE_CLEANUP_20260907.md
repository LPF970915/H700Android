# Fix72 Baseline Cleanup

Date: 2026-09-07. Scope: local workspace storage cleanup after the source
baseline was frozen. No device, TF card, serial connection, U-Boot, GPT, or
Android image was written by this maintenance operation.

## Frozen Source Point

- Annotated Git tag: `baseline/rgsp-fix72-offline-20260907`
- Commit: `e3566a9cfbf0d86dbb576631497adc6ea5ee94ce`
- Remote: `origin/main` and the tag were pushed before cleanup.

Fix72 remains an offline candidate, not a hardware-qualified release and not a
standalone TF2 boot system. Fix70 is the prior Wi-Fi/HOME deployment package;
Fix71 is the physical input/display integration trial.

## Outcome

The guarded cleanup script removed 155 explicitly selected regular files. It
freed 32,940,679,168 bytes (30.678 GiB). Before deletion it rechecked the
required size and SHA-256 values for Fix72, Fix70, the actual TF2 pre-write
recovery material, retained Fix72 sparse images/APK/ramdisk, and all Fix67
pinned payloads. All checks passed.

Machine-generated local report:

```text
out/cleanup-fix72-20260907/cleanup-20260907-174450.json
```

The report is local output and intentionally not committed.

## Retained Material

- `out/rgsp-fix72-wifi-profile/`: final current candidate.
- `out/rgsp-fix70-wifi-deployment/`: prior Wi-Fi/HOME deployment package.
- `out/tf2-deploy-20260907/` and `out/tf2-deploy-20260907-boot-locked/`:
  actual TF2 recovery/deployment material.
- `out/h700-android10-preflight/`: default tooling input and APK source.
- `out/h700-android10-b2/` payloads pinned by
  `docs/baselines/fix67-payload.sha256`.
- Fix72 preflight sparse `system.img`, `vendor.img`, ramdisk, manifests, and
  checks.

## Removed Material

- Generated B2, Fix69, and Fix72-preflight `system.raw.img`/`vendor.raw.img`
  copies where an equivalent retained sparse source exists.
- Nine uncompressed early B3 diagnostic boot images; their required compressed
  current-chain payload remains.
- 140 root-level Fix4-Fix50 historical serial/logcat diagnostic logs.
- Superseded, untracked B3 diagnostic and Fix41-Fix61 preparation scripts, old
  handoff scripts, and the obsolete unguarded TF2 writer.
- Historical Android 11 headless/Fix41-Fix44 notes, obsolete Fix56/Fix57 status,
  and the superseded B3 Path1 status document.

The deleted source-controlled documents can be restored from the frozen tag:

```powershell
git restore --source baseline/rgsp-fix72-offline-20260907 -- docs
```

The deleted old logs and untracked scripts were not Git source artifacts and
were deliberately not retained as an archive. They described abandoned paths;
current evidence is retained in Fix64-Fix72 documentation and protected outputs.

## Regenerating Raw Preflight Images

Do not regenerate images merely to restore old directory shape. When a
preflight-only workflow requires raw ext4 images, regenerate them one at a time:

```powershell
wsl.exe -d Ubuntu -- taskset -c 0 nice -n 19 ionice -c 3 python3 /mnt/d/Works/H700Android/tools/android_sparse_to_raw.py /mnt/d/Works/H700Android/out/rgsp-fix72-preflight/system.img /mnt/d/Works/H700Android/out/rgsp-fix72-preflight/system.raw.img
wsl.exe -d Ubuntu -- taskset -c 0 nice -n 19 ionice -c 3 python3 /mnt/d/Works/H700Android/tools/android_sparse_to_raw.py /mnt/d/Works/H700Android/out/rgsp-fix72-preflight/vendor.img /mnt/d/Works/H700Android/out/rgsp-fix72-preflight/vendor.raw.img
```

Recheck size and SHA-256 against the retained preflight manifest before any
deployment use. The final Fix72 deployment package already retains its verified
raw images and does not need this restoration step.

## Guarded Maintenance Tool

`tools/cleanup_rgsp_fix72.ps1` defaults to dry-run. `-Execute` requires the
frozen tag to resolve to the recorded commit, rejects tracked files and reparse
points, validates protected artifacts, and writes a local JSON report. It should
only be extended with individually reviewed paths.

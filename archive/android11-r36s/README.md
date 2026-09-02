# Android 11 Archive

Status: frozen on 2026-09-02 after fix58 was installed for one final cold-boot
validation.

Canonical full-system reference:

`out/rgsp-android11-alpha/rgsp-android11-system-alpha.img.gz`

Keep for comparison:

- `work/rgsp-android11-alpha/reference-configs/`
- fix51-fix58 payloads and provenance
- UART, logcat, logdw, kmsg and tombstone evidence
- boot handoff, rollback and verification scripts

Archived source-controlled material:

- `device/`: 121 fix, preparation, install and diagnostic scripts;
- `tools/`: 24 Android 11 framework/service build and serial deployment tools;
- `ramdisk/`: the old Android 11 handoff/probe ramdisk files;
- `../../android/legacy-android11/`: the frozen R36S-derived product overlay.

Discarded duplicates are listed in `docs/H700_ANDROID10_MIGRATION_CLEANUP_20260902.md`.
The original R36S identity (`r36s`, `rk3326`, `rk30board`) must never become a
dependency of the Android 10 mainline.

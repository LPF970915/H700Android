# RGSP 720x480 Launcher

Date: 2026-09-07. Device profile: current RGSP no-stick handheld, 720x480,
213dpi, Android 10.

## AT4K Finding

The observed AT4K rows were drawn at approximately y=147, y=286 and y=405.
Pressing DPAD_DOWN changed the focused item without visible scrolling in that
test. This observation alone does not establish the intended layout.

Correction after APK inspection: the built-in help explicitly describes a
bottom-pinned favorites mode, controlled by `keep_dock_bottom`. On the device,
`hide_watch_next` is true but `keep_dock_bottom` has no saved value; the inspected
code defaults the latter to false. The user's interpretation of a bottom dock
therefore has support, although its actual scrolling behavior remains untested.

The top-right options popup has a fixed height. Its first three choices are
visible, while the fourth choice is clipped at the bottom. DPAD_DOWN changed
focus inside the popup without visible scrolling during the test. This is a
layout/accessibility symptom, not yet proof that every relevant container has
a fixed height or that key handling plays no part.

AT4K remains installed and is still the current default HOME until the
replacement is built and physically verified.

## Replacement

PAUSED by user request. Do not build, install, or select this replacement as a
consequence of this plan. See `H700_LAUNCHER_LAYOUT_AUDIT_20260907.md` for the
subsequent AT4K inspection and source-verified alternative candidates.

`device/roc/rgsp/RGSPLauncher` is a small native Java HOME for this RGSP
profile. It is included in `h700_rgsp.mk` but is not automatically selected as
the default HOME.

The first implementation provides:

- a complete 720x480 home layout with a fixed bottom key-hint bar;
- fixed Settings, Files and AT4K entries;
- application discovery through standard `CATEGORY_LAUNCHER` intents;
- L/R or page keys for application pages;
- a five-item options popup whose focus scrolls inside the popup;
- Launcher3 as an explicit recovery entry.

`tools/set_rgsp_home.sh rgsp` supports selecting it after package installation.
The existing `at4k` and `launcher3` modes remain available.

## Build Gate

The supported focused build is:

```powershell
.\tools\build_h700_low_pressure.ps1 -Targets RGSPLauncher -Execute
```

On 2026-09-07 the first invocation spent its time generating the Android 10
Soong graph and was stopped after more than 22 minutes before target
compilation. The next invocation was rejected by the existing host-memory
guard because available physical memory was 5.72 GiB, below the required
6 GiB. No system, vendor, ramdisk or device files were written by this
attempt.

Physical installation, HOME switching and screenshot verification remain
pending until the focused APK build succeeds.

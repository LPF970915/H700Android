# RGSP 720x480 Launcher

Date: 2026-09-07. Device profile: current RGSP no-stick handheld, 720x480,
213dpi, Android 10.

## AT4K Finding

The AT4K desktop is a TV-oriented fixed grid. On the RGSP panel its rows are
drawn at approximately y=147, y=286 and y=405. Pressing DPAD_DOWN changes the
focused item but does not scroll the desktop, so the third row is not a hidden
scrollable bottom dock. The row is simply placed too low for the panel.

The top-right options popup has a fixed height. Its first three choices are
visible, while the fourth choice is clipped at the bottom. DPAD_DOWN changes
focus inside the popup but does not scroll it. This confirms a layout
compatibility problem rather than a missing key mapping.

AT4K remains installed and is still the current default HOME until the
replacement is built and physically verified.

## Replacement

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

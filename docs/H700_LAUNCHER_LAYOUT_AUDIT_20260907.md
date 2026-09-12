# H700 Launcher Layout Audit

Audit date: 2026-09-07.

Follow-up: the user chose to retain AT4K and requested code analysis before
deciding on modifications. `AT4K_LAYOUT_CODE_MAP_20260907.md` contains the
located menu constants, desktop padding, dock spacer branches, and icon
geometry. The alternatives below are historical research, not the active plan.

## Scope and Status

The user prefers retaining the supplied localized AT4K APK, with layout-only
changes. If that becomes invasive, investigate open-source launchers usable
with a D-pad and ABXY. No replacement launcher, global DPI change, firmware
change, or license-state change is authorized by this audit.

Completed: local APK decoding, source inspection of two alternatives, and
read-only device configuration checks. No APK was rebuilt or installed and no
device preferences were changed. AT4K remains HOME. Prior RGSPLauncher work
remains paused.

## AT4K Evidence

Input: `out/h700-android10-preflight/AT4K-launcher.apk`.
SHA-256: `1315ef01d56511a80cb6bb4b9c58bfd3233c0e84cc1e82254cd0898d5dd26ca9`.
Package: `com.overdevs.at4k`, versionName 1.2, versionCode 17.

Decoded successfully with Apktool 3.0.3 into `.tmp/at4k-layout-audit`.
This establishes that decoding works, not that rebuilding or runtime patching
works. The original input APK was not modified.

MainActivity creates the Compose content via obfuscated classes. The
application UI code includes large generated/obfuscated methods under `R3`;
`res/values/dimens.xml` largely exposes library dimensions, not a clear set
of launcher sizing controls. Presence of RecyclerView or Leanback resources
does not prove the home grid uses those implementations.

The preference loader in `smali/R3/J7.smali` exposes:

- `apps_per_row`, default 5.
- `hide_watch_next`, default false.
- `keep_dock_bottom`, default false.
- `show_all_apps_button`, default false.

The embedded help describes bottom-pinned favorites when featured cards are
hidden. The earlier claim that this design did not exist was incorrect.
Existence of this option does not establish how all-apps scrolling behaves.

Read-only COM4 checks returned:

```text
Physical size: 720x480
Physical density: 213
settings get system font_scale: null
hide_watch_next: true
keep_dock_bottom: no saved entry
apps_per_row: no saved entry
show_all_apps_button: no saved entry
```

`null` means the setting is absent, not evidence of an abnormally large user
font setting. The missing preference keys use the inspected code defaults.
No Wi-Fi credentials or unrelated app preferences were retrieved.

## AT4K Decision

Do not edit arbitrary library dimensions or globally shrink every app.
First distinguish three independent issues: bottom-dock configuration,
visual sizing, and focus-driven scrolling.

A launcher-only density/context experiment is a possible bounded approach,
but has not been implemented or verified. A scale reduction cannot by itself
guarantee access to off-screen options or correct a changed aspect ratio.
Adding scrolling to obfuscated Compose code is a separate, higher-risk task.

The official downloaded v1.2 APK has versionCode 19, not 17. Differences from
that binary cannot be attributed solely to localization. No changes to signing,
billing, premium flags, or authorization behavior are part of layout work.

## Candidate 1: Ox Shell

Upstream: `https://github.com/oxters168/oxshell`
Local checkout: `.tmp/oxshell-upstream`.
Inspected HEAD: `c79fbad16ca72e2c0c5aa91cfebc7b0434ab0d59`, dated 2024-02-08.
License file: GPLv3. Android Java source and Gradle build files are present.
The inspected build uses minSdk 26, so Android 10 clears that version floor.

Relevant source: `app/src/main/java/com/OxGames/OxShell/Data/SettingsKeeper.java`.
It exposes independent UI and text scaling plus configurable controls.
Default actions include:

- D-pad: navigation.
- A, Enter, or D-pad center: primary action.
- B or Back: cancel.
- Y: secondary action.
- X: selection in the file explorer.
- Select+B / Select+X: HOME / recents shortcuts.

The repository includes an app launcher and file explorer, not just a ROM
library. This makes it the strongest source-level match for the user's
handheld control requirements. System-wide shortcuts require separate setup;
they do not make arbitrary touch-only app interfaces controller-accessible.

Risks: the inspected upstream commit is old; small-screen visual quality,
Chinese text, memory use, global shortcut permissions, and build dependencies
are unverified on this device. Use static wallpaper during an initial test.
Do not describe it as a validated 720x480 solution yet.

## Candidate 2: FLauncher

Upstream: `https://gitlab.com/flauncher/flauncher`
Local checkout: `.tmp/flauncher-upstream`.
Inspected HEAD: `4930cd738a5ab32967953fe8b12790bc4b452872`, dated 2023-03-03.
Source headers permit GPLv3 or later. Flutter/Dart and Android source is present.
The inspected Android build has minSdk 21.

Source-verified features include configurable category grids, non-TV apps,
A/Enter activation on app cards, and B dismissal/back actions. The
`EnsureVisible` widget scrolls focused content into view; the settings panel
uses a scroll container. These are relevant foundations for the current
off-screen-focus problem.

Risks: no complete X/Y workflow was established; TV-sized spacing still needs
measurement at 720x480. The checkout has an older Dart/Flutter toolchain and
Firebase integrations. Its README itself notes limited device testing.

## Recommendation and Acceptance Gate

Keep AT4K as the baseline. Its existing dock setting should be tested before
redesigning the home layout. If layout work needs invasive Compose patching,
prefer an isolated Ox Shell trial; FLauncher is the second choice for a
traditional TV app-grid appearance. Neither alternative was built or installed
as part of this audit.

Before selecting any modified or alternative launcher as HOME:

1. Back up the current APK, app settings, and HOME selection.
2. Verify icon labels and all menu entries at the physical 720x480 resolution.
3. Reach every launcher screen using D-pad and available confirmation/back keys.
4. Verify scroll follows focus and preserves a usable selection when returning.
5. Launch representative installed apps, return HOME, and open system settings.
6. Check cold-start and runtime memory on H700; retain Launcher3 recovery.

Existing device keylayout source maps the primary button to ENTER and keeps
B/X/Y as gamepad buttons. Both candidate sources accept ENTER for primary
activation. Physical ABXY label-to-keycode mapping still needs a real-device
test; do not remap those buttons globally and risk changing emulator controls.

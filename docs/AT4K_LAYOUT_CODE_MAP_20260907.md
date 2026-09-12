# AT4K Layout Code Map

Date: 2026-09-07. Scope: inspect the supplied localized APK only; do not modify,
rebuild, sign, install, change preferences, or select another launcher.

## Result

The main layout functions and several useful dimension constants are now
located. A first pass limited to typography, padding, and spacing is more
tractable than the earlier broad "high difficulty" assessment suggested.
Reliable focus-following scrolling remains a separate task.

This is a static analysis result, not a tested layout patch.

## Inputs and Inspection Outputs

- Input: `out/h700-android10-preflight/AT4K-launcher.apk`.
- Package: `com.overdevs.at4k`, versionName 1.2, versionCode 17.
- SHA-256: `1315ef01d56511a80cb6bb4b9c58bfd3233c0e84cc1e82254cd0898d5dd26ca9`.
- Existing Apktool 3.0.3 output: `.tmp/at4k-layout-audit/`.
- New JADX 1.5.6 reading copies: `.tmp/at4k-java/J7.java`,
  `.tmp/at4k-java/T5.java`, and `.tmp/at4k-java/Z4.java`.

JADX reported 16, 6, and 2 errors respectively. It produced useful partial
output, but some methods contain duplicated branches, unresolved variables,
or a non-decompiled placeholder. These files are NOT recovered buildable source.
The findings below were checked against corresponding Smali instructions.
Java was limited to a 768 MiB heap and two processors; no Android OS build ran.

## Entry and Call Map

```text
MainActivity.onCreate
  R3.V3 (Compose lambdas)
    R3.J7.p              main state and composition setup
      R3.T5.h            main desktop container
        R3.J7.x          top/status bar
        d3.a.d           favorites section
        d3.a.p           remaining apps section
          R3.J7.d
            R3.Z4.h      row/column geometry and focus callbacks

R3.J7.C                  settings overlay and right-hand panel
  R3.J7.G                settings category list
```

Reference locations in the decoded tree:

- `smali/com/overdevs/at4k/MainActivity.smali:93`.
- `smali/R3/J7.smali:48239` (`p`) and `:16455` (`d`).
- `smali/R3/J7.smali:4288` (`C`) and `:8706` (`G`).
- `smali/d3.1/a.smali:2021` (favorites) and `:13309` (remaining apps).

Windows case collisions matter: raw class `Ld3/a;` is in `d3.1/a.smali`,
not `d3/a.smali`. Likewise `LR3/r7;` is in `R3/r7.1.smali`.
Resolve future edits by the `.class` declaration, not case-insensitive filenames.

## Settings Panel: Bounded Changes

The right-side panel is full-height, half-width, with 16 dp outer padding.
Inside it, `J7.G` builds an ordinary Column of category entries. The inspected
function does not add a scroll modifier, scroll state, or lazy list.

| Control | Existing value | Raw location |
| --- | --- | --- |
| Panel width fraction | 0.5 | `J7.smali:7226` |
| Category content padding | 32 dp on all sides | `J7.smali:8802` |
| Vertical item spacing | 12 dp | `J7.smali:8808` |
| Settings title | 26 sp | `J7.smali:8894` |
| Space below title | 24 dp | `J7.smali:8902` |
| Padding inside each entry | 10 dp | `J7.smali:9319` |
| Entry text | 20 sp | `J7.smali:9416` |
| Focused entry scale | 1.05 | `J7.smali:9054` |

Reading copy: `J7.java:1519` through the end of `G`.
The category list is assembled in `C` (professional, theme, appearance,
controls, backup, about, help). A permission-related conditional may affect
which categories are present.

At the previously measured 213 dpi, 32 dp is approximately 43 pixels. Combined
with the outer 16 dp, this explains the large insets visible in the recorded
720x480 UI dump. It is not merely a font-scale setting.

First-test candidates, NOT changes already made: title 18-20 sp, entries
14-16 sp, content padding 12 dp, entry padding 6 dp, item spacing 6 dp,
and title-bottom spacing 8 dp. Measure every category at runtime before
claiming this fits. Smaller text alone does not create scrolling.

Important patch hazard: the register containing 32 is initially used as a
Compose change-mask value and later converted to a padding float. Do not
replace every literal `0x20` or alter its initial definition indiscriminately.
A later override immediately before the padding conversion would separate
layout tuning from change detection.

Assessment: low-to-medium for local sizing; medium-to-high for adding and
validating focus-aware scrolling throughout nested settings pages.

## Desktop Insets and Dock Position

Reading copy: `T5.java:382` and `:393`.
The desktop attaches the existing scroll state through `r4.a.P`, then applies
padding of left/right 10 dp, top 24 dp, and bottom 68 dp.

Raw references:

- `R3/T5.smali:828`: desktop padding values.
- `r4.1/a.smali:3331`: scroll modifier helper.
- `androidx/compose/foundation/f.smali`: adds `ScrollSemanticsElement`
  and `ScrollingLayoutElement`.

This corrects the early suggestion that the home screen contains no scrolling
implementation. Static presence does not prove directional focus reveals every
off-screen item in the current configuration.

Dock positioning includes fixed-height Spacer branches in `T5`:

```text
normal icons + keep_dock_bottom + hidden featured area:
    spacer = 288 dp + (apps_per_row - 5) * 20 dp

mini-mode branch with hidden featured area:
    one branch uses a 350 dp spacer
    other branches use 50 dp
```

These branches have additional state conditions; do not apply all constants to
the current screen unconditionally. See `T5.java:707` and Smali near `:2028`.
In particular, enabling mini mode or bottom-dock mode is not itself a proven
small-screen fix. 288 dp alone is about 383 pixels at the recorded density.
The screen-height-aware alternative needs to reserve the measured top bar,
dock, and focus enlargement before choosing the remaining spacer height.

Preference mapping verified through `W3` writes and `T3` getters:

- `T3.f()` = apps per row.
- `T3.m()` = `hide_watch_next`.
- `T3.q()` = `keep_dock_bottom`.
- `T3.s()` = `mini_mode`.

Assessment: medium for reducing desktop whitespace; medium-to-high for a
reliable bottom-position formula covering the supported mode combinations.

## Icon Geometry

Reading copy: `Z4.java:177`.
Raw calculation: `R3/Z4.smali:244` onward.
This is constrained-width layout, not a hardcoded 1920-pixel desktop.

```text
normal mode:
    horizontal gap = 22 dp
    card width = (available width - (columns - 1) * gap) / columns
    card height = card width * 0.56578946

mini-mode path:
    horizontal gap = 12 dp
    card width = card height = 56 dp

inter-row spacing = 18 dp
```

The Boolean selecting this geometry is passed by the caller. The favorites
and remaining-apps wrappers do not necessarily use the same mode, so do not
assume the square-icon branch changes every row.

Counterintuitively, shrinking horizontal gaps with an unchanged column count
makes the normal cards wider, hence taller. To shrink icons coherently, adjust
the size constraint/column policy as well as spacing; do not distort the
artwork by blindly changing the aspect ratio.

`Z4` already allocates focus requesters and attaches row-direction callbacks
(`W4`, `X4`, `Y4`). Preserve these during a first sizing-only test.
Reordering, drag/move mode, folders, and returning from launched apps broaden
the test surface of any navigation changes.

Assessment: medium for geometry tuning while preserving the visual style;
medium-to-high when changing row structure or focus/scroll behavior.

## Suggested Decision

The evidence supports a small AT4K-only experiment, not a rewrite or another
launcher. Suggested order after the user's decision:

1. Category menu typography and spacing, preserving colors and focus effects.
2. Desktop top/bottom whitespace and row spacing.
3. Dock placement based on actual available height.
4. Only then address remaining focus/scroll failures.

Do not globally change Android DPI, bulk-replace dimensions, alter licensing,
or attempt to recompile the imperfect JADX Java as an Android project.
Use exact, input-hash-pinned Smali edits if implementation is approved.
Rebuild/signature compatibility and on-device startup remain untested.

No APK/Smali changes, rebuilding, installation, live UI actions, or device
configuration changes were performed in this follow-up analysis.

# Fix71 RGSP Keyboard And AT4K Layout

Date: 2026-09-07. Device: current RGSP, no sticks, 720x480, 213dpi.

## User-Reported Blockers

The user could not open an operable keyboard with A in the Wi-Fi password
field, and AT4K content appeared cropped on the 3:2 panel.

Read-only IME state and a diagnostic screenshot confirmed that LatinIME was
installed and could render after an explicit touch request. It was not an
absent keyboard service: the touch-oriented keyboard lacked the required
DPAD editing workflow. The existing A-to-ENTER mapping is retained for
desktop and lock-screen compatibility.

AT4K's manifest specifies landscape and large/xlarge screen support, not a
literal 1920x1080 framebuffer. The initial screenshot showed an empty
recommendation area occupying roughly y=118..398 and application icons
starting at y=464, mostly outside the 480-pixel screen.

## AT4K Configuration Fix

Used the launcher's own preferences UI:

1. Preferences (top-right sliders icon).
2. Appearance / 外观.
3. Desktop cards / 桌面卡片.
4. Enable Hide desktop cards / 隐藏桌面卡片.

The application saved `hide_watch_next=true` in its own preferences.
The widgets option was briefly inspected and restored to disabled, its
original effective state. No premium/license flag was changed.

With recommendation cards hidden, the application row moved to y=141..205
and the Settings icon is visible in the next row at y=286..381.
This is a reversible layout workaround, not proof of full responsive support
across every AT4K page. Physical screen size and density remain unchanged.
AT4K is still the default HOME and Launcher3 remains the recovery launcher.

Local screenshots:

| Screenshot | SHA-256 |
| --- | --- |
| `out/rgsp-fix71-input-display/at4k-before.png` | `b70a57d9d76d6a97e1f808a2a39ddd897fc278ca7f4d5753ce7360ca03532e54` |
| `out/rgsp-fix71-input-display/at4k-cards-hidden.png` | `14477c4fe6c89033f9d465327cc5290c8e8502339b559bd43b58ac829f136aef` |

## TV Input Method

Fetched AOSP `platform/packages/inputmethods/LeanbackIME` from its official
Git repository, revision `1667592ee5924122e43b611fa813c8f894087cd6`.
That January 2020 import is available on `android11-release`; it is built
here against the Android 10 SDK, without any Android 11 framework binary.
Source files retain Apache-2.0 notices. The source contains no INTERNET
permission; no microphone runtime permission or accessibility grant was made.
This is not a full security audit or a production signing configuration.

Reproduction:

```sh
bash tools/prepare_h700_leanback_ime.sh /home/lpf/h700-android10/android
# Sync the RGSP device overlay, then in the Android 10 build environment:
m -j4 LeanbackIME
```

The preparation tool pins origin and revision, checks the patch, supports
an exact idempotent re-run, and rejects unrelated source modifications.
It does not delete or reset an existing source tree.

`tools/h700-leanback-ime-rgsp.patch` adapts only input-method handling:

- On `Build.DEVICE=rgsp`, ENTER with the calibrated scan code 304 becomes
  DPAD_CENTER while the keyboard is visible. Virtual injected ENTER is also
  accepted for automated smoke tests. Real USB keyboard Enter is preserved.
- A can reopen a hidden keyboard only for a non-TYPE_NULL editor with an
  input connection. The opening release is consumed without typing a character.
- B hides the keyboard without forwarding that same press to dismiss the dialog.
- Starting a different input session clears pending button state.
- Original Leanback behavior provides DPAD navigation, X backspace, Y space,
  shift/symbol keys and L1/R1 cursor movement. Only a subset is hardware-tested.

The first prototype incorrectly allowed A to show the keyboard on non-editable
controls, because Android supplies an input connection even for TYPE_NULL.
It was replaced before requesting physical validation. The final source
explicitly checks `EditorInfo.inputType`.

The RGSP-only resource overlay reduces spacing/key width and bottom padding,
leaving room for the action button and password dialog. It is selected by
this product, not by a generic H700 profile. It must not be assumed suitable
for other models' panels or physical key semantics.

Final APK (ordinary data-side test installation):

```text
out/rgsp-fix71-input-display/LeanbackIME-rgsp-compact.apk
389088 bytes
SHA256 2a57b52cbac36d09138f7d94ba43f5d7fa9c4175966f7f1b43bb004b1a83ff18
IME com.android.inputmethod.leanback/.service.LeanbackImeService
```

`h700_rgsp.mk` now includes LeanbackIME and its compact resource overlay.
LatinIME remains installed. The final APK build succeeded in 3:15;
the build log explicitly compiled the RGSP overlay.

## Runtime Verification

At 12:30 the final APK replaced the first prototype. Serial SHA-256 upload
and Package Manager installation succeeded. At 12:31 DPAD navigation
selected the user's previously chosen AP, and A opened the password dialog
with the compact keyboard. The password editor and NEXT button were visible
on the 720x480 screenshot.

At 12:32-12:33, injected Android key events verified:

1. A selected a character, RIGHT changed the key, and A selected another.
2. B hid the keyboard while retaining the password dialog.
3. Parsed UI XML confirmed exactly two masked characters and CONNECT disabled.
4. A reopened the keyboard.
5. Two X presses deleted both test characters.
6. B hid the keyboard again; parsed XML confirmed the editor was empty and
   the dialog remained present.

No test string was submitted to an access point. The user was then asked
to test physical controls and enter the actual password privately. Password-page
capture stopped before that request. No network credentials belong in Git.

Local UART logs under `out/logs/uart/rgsp/`:

- `rgsp_serial_exec_20260907_123027_115200.log`: final APK installation.
- `rgsp_serial_exec_20260907_123121_115200.log`: text editor and keyboard activation.
- `rgsp_serial_exec_20260907_123207_115200.log`: two-character test and hide.
- `rgsp_serial_exec_20260907_123301_115200.log`: reopen and clear.

The inspected crash buffer was empty. This is a focused smoke test, not
physical-key, long-press, all-symbol, multilingual or stability qualification.

## Recovery And Next Gates

The current device has the verified helper at
`/data/local/tmp/set_rgsp_tv_ime.sh`. From an Android root shell:

```sh
sh /data/local/tmp/set_rgsp_tv_ime.sh latin
sh /data/local/tmp/set_rgsp_tv_ime.sh leanback
```

The helper validates the installed Leanback APK hash and retains the previous
IME selection locally. The final hash-only helper update was uploaded; the
selection path was exercised with the earlier prototype, while the final APK
was selected directly with `ime set`.

Next: physical A/DPAD/B/X verification, actual authentication/DHCP/DNS/HTTPS,
then reconnect and controlled reboot persistence. No Wi-Fi connection is
claimed by this keyboard test. TF2-only cold boot is still unqualified.

`out/rgsp-fix70-wifi-deployment` is immutable and does not contain Fix71.
The final keyboard APK is built and installed on retained data; a fresh full
system/deployment image including it and blank-data provisioning is separate
work. AT4K's layout preference currently lives in the retained app data and
must be handled explicitly by the eventual first-run setup.

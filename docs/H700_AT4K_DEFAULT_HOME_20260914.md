# AT4K Factory Default Home - 2026-09-14

Subsequent integration: the default and latest wallpaper APK are now included
in the v5e build. See `H700_V5E_AT4K_BASELINE.md`; the task-scoped live-only
status below records the earlier step, not the final integration status.

## Decision and Scope

AT4K is the RGSP product's factory default home. A fresh installation should
open AT4K without asking the user to select a launcher. Keep Launcher3 and
RGSPLauncher installed as recovery choices; do not disable their activities.
This is a factory default, not a kiosk restriction or an every-boot override
of a later explicit user choice.

## Changes

- Added `device/roc/rgsp/configs/at4k-home.xml` to the product overlay.
  `h700_rgsp.mk` installs it at `/system/etc/preferred-apps/at4k-home.xml`.
- Its preferred activity is `com.overdevs.at4k/.MainActivity`, for the
  MAIN / HOME / DEFAULT intent filter. Candidate activities are discovered
  by PackageManager, not hard-coded as a stale activity set.
- Confirmed the format and default-loading path against the local Android 10
  framework source: `Settings.applyDefaultPreferredAppsLPw`,
  `readDefaultPreferredActivitiesLPw`, `PreferredComponent` and `IntentFilter`.
- Selection is no longer dependent solely on the late `sys.boot_completed`
  firstboot job, which also validates the keyboard APK before setting HOME.
- Added the exact live-tested dock APK SHA-256 to the existing allowlists
  in `tools/set_rgsp_home.sh` and `rgsp-firstboot.sh`. Unknown APK hashes
  remain rejected; no signature or licensing policy was relaxed.
- Added the preferred-apps XML to the full-image verification gate.

The existing system prebuilt APK remains unchanged in this task. The latest
dock APK is still the live `/data/app` update documented in
`H700_AT4K_DOCK_PATCH_20260913.md`; integrating that binary into a future ROM
requires updating and verifying its packaged APK/DEX/resource hashes.

## Live Verification

Ran the updated helper from
`/data/local/tmp/rgsp-at4k-20260913/set_rgsp_home-default.sh`.

- Before and after: `com.overdevs.at4k/.MainActivity`.
- `pm set-home-activity --user 0`: Success.
- Implicit MAIN / HOME launch: Status ok, Activity AT4K MainActivity.
- No resolver activity was launched in this test.
- Previous/resolved HOME and launch outputs saved on-device at
  `/data/local/tmp/rgsp-home.eFc2Yf`.

No system remount, preference clear, input-method change, physical reboot,
full ROM build or flash was performed. The live default is persisted by
PackageManager; the new factory XML still needs fresh-data boot validation
after the next image build. Existing boot-media failures are not resolved
or requalified by this launcher-default change.

## Tests

`wsl.exe -d Ubuntu -- python3 /mnt/d/Works/H700Android/tools/test_rgsp_offline.py -v`

Result: all 22 tests passed. `git diff --check` reported no whitespace errors.

Coverage includes factory XML/product/release wiring, accepted dock APK,
unknown APK rejection, launch failure, switch rollback, read-only status,
and existing firstboot provisioning regressions. These host mocks do not
substitute for fresh-flash startup acceptance.

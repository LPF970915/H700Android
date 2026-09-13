# RGSP Runtime Navigation Trial

This directory retains the local test/rollback harness. The physically
accepted helper sources now live in
`android/h700-android10/device/roc/rgsp/RGSPNavigation/` and are built into
the v5d system image as RGSPNavigation 1.0. This remains a scoped
accessibility implementation, not a native Settings/DocumentsUI source fix
or a substitute for physical firmware qualification.

Scope: RGSP only; the Settings locale-order list and DocumentsUI.
Directions move a subtle gray selection highlight. Physical A invokes a locale row's
existing move-to-top action, or clicks a Files control. BACK/B remains with
the original app via a scoped overlay-focus release and Android's BACK
action. The focusable accessibility overlay also accepts joystick HAT axes:
Android 10 accessibility key filtering alone does not capture those axes.
Editable fields and visible input-method windows suspend
the helper. Other Settings screens, AT4K and other apps are untouched.
The package has no network, storage or input-text logging permission/code.

Build locally with `tools/runtime_nav_trial/build.ps1`. Ten host-only
direction-selection tests run first. The APK and local signing key are
generated under ignored `out/runtime-nav-trial/`.

Install the APK as a new package, then push and run `enable-trial.sh`.
This snapshots the prior accessibility settings and locale order into
`/data/local/tmp/rgsp-nav-trial-20260913`, then adds only this service.
Run `disable-trial.sh` to restore those accessibility settings. It refuses
to overwrite accessibility-service changes made after activation.
Uninstall `com.roc.rgsp.navtrial` after disabling to remove the helper.
User locale choices are deliberately not reset by the disable script.

The APK and service-enable setting persist until disabled/uninstalled,
unlike the separate RAM-only UART console workaround.
No system APK, global key map, IME preference or firmware image is replaced.
Reopen Settings after enabling accessibility so its RecyclerView installs
the locale-row accessibility delegates.

The user accepted locale/language switching and basic Files navigation
on 2026-09-13. Wi-Fi keyboard operation and connection were also accepted
earlier in this runtime. Broader picker confirmation, long-list scrolling,
context menus, multiselect and reboot persistence remain unqualified.
Injected key success alone is not physical button acceptance.

Version 0.2 changed only the highlight from a double outline to a neutral
translucent fill. It does not change input routing or address screen flicker.
The formal 1.0 build retains that Java behavior and changes packaging/label.
The platform-signed system app is intended for the requested full flash,
not an in-place replacement over the differently signed trial APK.
The separate test-display timeout settings can be restored with
`restore-test-display.sh`; they are not coupled to enabling this service.

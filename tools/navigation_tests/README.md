# Public Source64 navigation regressions

Run from a public checkout with Python 3.10+ and a host JDK providing `javac` and
`java`. Android sources, an Android SDK, signing keys and a connected device are
not required. The runner resolves all 13 Source64 Navigation18 inputs from
`build-support/public/source-manifest.json`, checks their size and SHA256, and
preserves their directories under a fresh `sources/Navigation` snapshot. This
includes the manifest, build file, service resource, `MouseController` and all
Java helpers. Missing, extra or changed Navigation manifest inputs are rejected.

On the project's Linux build host, use the existing resource wrapper:

```sh
REPO=/path/to/H700Android
WORK=/path/to/new-navigation-test-directory
bash "$REPO/tools/public_build/run-limited.sh" \
  python3 -B "$REPO/tools/navigation_tests/run_source64.py" \
  --javac /path/to/jdk/bin/javac --java /path/to/jdk/bin/java \
  --work "$WORK"
```

With root as the wrapper caller, also set `ROC_BUILD_USER` to the unprivileged
build user. The two executable options default to `javac` and `java` on `PATH`.
`--manifest` may select another public manifest; required navigation inputs must
still resolve to hash-matching repository files. An existing work directory is
rejected so old classes cannot count as a new test pass.

The snapshot must identify Navigation18, version `2.4-resume-guard`. Success
requires the original seven helper suites plus `KeyNavigationTest`, including 79 checks against the production
`AxisNavigation` source and the Source64 Select/fallback mouse-hotkey regression.
The ordinary RGSP `MouseHotkeyTest` has a different scan-code contract; this
entry point deliberately runs `Source64MouseHotkeyTest` for Source64.

The runner then executes `test_navigation_resume_candidate.py` against the same
complete snapshot. It requires another 79 Axis checks, the existing 32 service
fragment checks, and all nine resume scenarios covering blocked axes, neutral
gates, screen transitions, live lock checks, retired callbacks and mouse input
ownership. The original 32 assertions retain an explicit always-allowed
`guardInteraction` stub to test their existing allowed-state contract. The new
resume scenarios execute the extracted guard implementation itself.

`KeyNavigationTest` executes the exact physical DPAD timing controller. Seven
additional wrapper scenarios execute the extracted service gate, local timer,
context checks, cancellation and Ring dispatch methods. They cover the local
400/160ms repeat schedule, the absolute ten-second cap despite zero-count raw
DOWN events, real versus canceled release, game pass-through, axis and mouse
ownership, screen/keyguard boundaries and retired callbacks. Navigation event
delivery and the remainder of the service navigation body are explicit doubles.

Both Python fragment scripts and all eight Java test sources are copied with
their relative directories and locked by SHA256. The parent runner checks the
complete candidate input map, the imported extractor identity, the candidate
version, all nine resume and seven key-wrapper scenario identities, both
physical-key PASS counts and `emit_only=false` in the child
receipt. It checks the original and copied inputs again before reporting PASS;
generated fragments alone cannot count as a successful run.

Read `$WORK/result.json`, the per-command logs, and
`$WORK/service-fragments-result.json` for source identities and results. The
original child receipt and generated Java fragments remain in
`$WORK/service-fragments/`. These host checks use virtual Android boundaries;
they do not reproduce the intermittent physical fault or establish ordinary
HOME repeat, framework scheduling, panel, sleep, or USB behavior.

The separate `test_native_joystick_source.py` diagnostic requires the retained
Android10 `ViewRootImpl.java` and checks its fixed SHA256 before extracting the
entire unchanged `SyntheticJoystickHandler` class. Run it with the same resource
wrapper, supplying `--source`, a fresh `--work`, `--javac`, and `--java`. It does
not use the public Source64 manifest or build the production framework. Its
seven scenarios currently execute 39 checks with virtual Android scheduling,
clock, events and delivery. They establish repeat/state mechanisms, including
cross-channel and cross-device interference, rather than reproduce a physical
wake failure or exercise the complete Android input pipeline.

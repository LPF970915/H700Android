# Public Source64 navigation regressions

Run from a public checkout with Python 3.10+ and a host JDK providing `javac` and
`java`. Android sources, an Android SDK, signing keys and a connected device are
not required. The runner resolves the Source64 Java inputs from
`build-support/public/source-manifest.json`, checks their size and SHA256, and
copies the selected files and test harnesses into a new work directory.

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

Success requires 79 checks against the production `AxisNavigation` source,
32 checks executing extracted `NavigationService` fragments with a virtual
Android boundary, the Source64 Select/fallback mouse-hotkey regression, and the
existing Direction, FocusIdentity, MenuHotkey, PointerPosition and StickVector
tests. The ordinary RGSP `MouseHotkeyTest` has a different scan-code contract;
this entry point deliberately runs `Source64MouseHotkeyTest` for Source64.

Read `$WORK/result.json`, the per-command logs, and
`$WORK/service-fragments-result.json` for source identities and results. These
host checks do not reproduce the intermittent physical fault or prove Android
framework, panel, sleep, or USB behavior.

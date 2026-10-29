[CmdletBinding()]
param(
    [string]$JavaHome = 'C:\Program Files\Java\jdk-11',
    [string]$Output = 'out/host-tests/navigation'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$out = [IO.Path]::GetFullPath((Join-Path $root $Output))
$allowed = [IO.Path]::GetFullPath((Join-Path $root 'out')) + '\'
if (!$out.StartsWith($allowed, [StringComparison]::OrdinalIgnoreCase)) { throw 'Test output must remain inside workspace out.' }
New-Item -ItemType Directory -Force -Path $out | Out-Null
$source = Join-Path $root 'android/h700-android10/device/roc/rgsp/RGSPNavigation/src/com/roc/rgsp/navtrial'
$tests = Join-Path $PSScriptRoot 'navigation_tests/com/roc/rgsp/navtrial'
& "$JavaHome/bin/javac.exe" --release 8 -d $out `
    "$source/Direction.java" "$source/PointerPosition.java" "$source/FocusIdentity.java" "$source/StickVector.java" "$source/MouseHotkey.java" "$source/MenuHotkey.java" `
    "$tests/DirectionTest.java" "$tests/PointerPositionTest.java" "$tests/FocusIdentityTest.java" "$tests/StickVectorTest.java" "$tests/MouseHotkeyTest.java" "$tests/MenuHotkeyTest.java"
if ($LASTEXITCODE) { throw 'Navigation host compilation failed.' }
foreach ($test in @('DirectionTest','PointerPositionTest','FocusIdentityTest','StickVectorTest','MouseHotkeyTest','MenuHotkeyTest')) {
    & "$JavaHome/bin/java.exe" -cp $out "com.roc.rgsp.navtrial.$test"
    if ($LASTEXITCODE) { throw "Navigation host test failed: $test" }
}

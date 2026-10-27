param(
    [string]$Sdk = "$env:LOCALAPPDATA\Android\Sdk",
    [string]$JavaHome = "C:\Program Files\Java\jdk-11",
    [string]$Output = "out/runtime-nav-trial"
)
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot '..\..\android\h700-android10\device\roc\rgsp\RGSPNavigation'
$env:JAVA_HOME = $JavaHome
$out = [IO.Path]::GetFullPath((Join-Path (Get-Location) $Output))
$tools = Join-Path $Sdk 'build-tools\34.0.0'
$android = Join-Path $Sdk 'platforms\android-34\android.jar'
foreach ($dir in @($out, "$out\classes", "$out\dex", "$out\test-classes")) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}
function Check-Exit {
    if ($LASTEXITCODE -ne 0) { throw "Build command failed: $LASTEXITCODE" }
}
$direction = Join-Path $source 'src\com\roc\rgsp\navtrial\Direction.java'
$test = Join-Path $PSScriptRoot 'tests\com\roc\rgsp\navtrial\DirectionTest.java'
$pointer = Join-Path $source 'src\com\roc\rgsp\navtrial\PointerPosition.java'
$pointerTest = Join-Path $PSScriptRoot 'tests\com\roc\rgsp\navtrial\PointerPositionTest.java'
$identity = Join-Path $source 'src\com\roc\rgsp\navtrial\FocusIdentity.java'
$identityTest = Join-Path $PSScriptRoot 'tests\com\roc\rgsp\navtrial\FocusIdentityTest.java'
& "$JavaHome\bin\javac.exe" --release 8 -d "$out\test-classes" $direction $test $pointer $pointerTest $identity $identityTest
Check-Exit
& "$JavaHome\bin\java.exe" -cp "$out\test-classes" com.roc.rgsp.navtrial.DirectionTest
Check-Exit
& "$JavaHome\bin\java.exe" -cp "$out\test-classes" com.roc.rgsp.navtrial.PointerPositionTest
Check-Exit
& "$JavaHome\bin\java.exe" -cp "$out\test-classes" com.roc.rgsp.navtrial.FocusIdentityTest
Check-Exit
& "$tools\aapt2.exe" compile --dir "$source\res" -o "$out\resources.zip"
Check-Exit
& "$tools\aapt2.exe" link -I $android --manifest "$source\AndroidManifest.xml" `
    -o "$out\nav-unsigned.apk" "$out\resources.zip"
Check-Exit
$javaFiles = @(Get-ChildItem "$source\src" -Recurse -Filter '*.java' |
    ForEach-Object { $_.FullName })
& "$JavaHome\bin\javac.exe" -source 8 -target 8 -classpath $android -d "$out\classes" @javaFiles
Check-Exit
$classFiles = @(Get-ChildItem "$out\classes" -Recurse -Filter '*.class' |
    ForEach-Object { $_.FullName })
& "$tools\d8.bat" --min-api 29 --lib $android --output "$out\dex" @classFiles
Check-Exit
& "$JavaHome\bin\jar.exe" uf "$out\nav-unsigned.apk" -C "$out\dex" classes.dex
Check-Exit
if (-not (Test-Path "$out\trial-key.jks")) {
    & "$JavaHome\bin\keytool.exe" -genkeypair -keystore "$out\trial-key.jks" -storepass android `
        -keypass android -alias trial -keyalg RSA -keysize 2048 -validity 3650 `
        -dname 'CN=RGSP Local Navigation Trial'
    Check-Exit
}
& "$tools\zipalign.exe" -f 4 "$out\nav-unsigned.apk" "$out\nav-aligned.apk"
Check-Exit
& "$tools\apksigner.bat" sign --ks "$out\trial-key.jks" --ks-key-alias trial `
    --ks-pass pass:android --key-pass pass:android `
    --out "$out\RGSPNavigationTrial.apk" "$out\nav-aligned.apk"
Check-Exit
& "$tools\apksigner.bat" verify "$out\RGSPNavigationTrial.apk"
Check-Exit
Get-FileHash "$out\RGSPNavigationTrial.apk" -Algorithm SHA256

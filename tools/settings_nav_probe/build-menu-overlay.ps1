param([string]$Output='out/settings-deep-audit-20261023/menu-overlay', [string]$FrameworkApk='', [string]$ResourceDir='', [string]$Manifest='')
$ErrorActionPreference='Stop'
$sdk=Join-Path $env:LOCALAPPDATA 'Android/Sdk'
$build=Join-Path $sdk 'build-tools/34.0.0'
$aosp='\\wsl.localhost\Ubuntu\home\lpf\h700-android10\android'
$key=Join-Path $aosp 'build/make/target/product/security/platform.pk8'
$cert=Join-Path $aosp 'build/make/target/product/security/platform.x509.pem'
$out=[IO.Path]::GetFullPath($Output)
if (!$FrameworkApk) { $FrameworkApk="$sdk/platforms/android-34/android.jar" }
if (!$ResourceDir) { $ResourceDir="$PSScriptRoot/menu-overlay/res" }
if (!$Manifest) { $Manifest="$PSScriptRoot/menu-overlay/AndroidManifest.xml" }
New-Item -ItemType Directory -Force $out | Out-Null
$env:JAVA_HOME='C:\Program Files\Java\jdk-11'
& "$build/aapt2.exe" compile --dir $ResourceDir -o "$out/resources.zip"
if($LASTEXITCODE){throw 'Overlay compile failed'}
& "$build/aapt2.exe" link -I $FrameworkApk --manifest $Manifest --auto-add-overlay -o "$out/unsigned.apk" "$out/resources.zip"
if($LASTEXITCODE){throw 'Overlay link failed'}
& "$build/zipalign.exe" -f 4 "$out/unsigned.apk" "$out/aligned.apk"
if($LASTEXITCODE){throw 'Overlay align failed'}
& "$build/apksigner.bat" sign --key $key --cert $cert --out "$out/RgspDpadFrameworkOverlay.apk" "$out/aligned.apk"
if($LASTEXITCODE){throw 'Overlay signing failed'}
& "$build/apksigner.bat" verify --print-certs "$out/RgspDpadFrameworkOverlay.apk"
if($LASTEXITCODE){throw 'Overlay verification failed'}

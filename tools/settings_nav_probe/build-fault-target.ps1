param([string]$Output='out/settings-deep-audit-20261023/fault-target')
$ErrorActionPreference='Stop'
$sdk=Join-Path $env:LOCALAPPDATA 'Android/Sdk'
$buildTools=Join-Path $sdk 'build-tools/34.0.0'
$out=[IO.Path]::GetFullPath($Output)
$key=[IO.Path]::GetFullPath('out/settings-deep-audit-20261023/universal-nav/build/trial-key.jks')
if(!(Test-Path -LiteralPath $key)){throw 'Build the local navigation trial key first'}
New-Item -ItemType Directory -Force $out | Out-Null
$env:JAVA_HOME='C:/Program Files/Java/jdk-11'
& "$buildTools/aapt2.exe" link -I "$sdk/platforms/android-34/android.jar" --manifest "$PSScriptRoot/fault-target/AndroidManifest.xml" -o "$out/unsigned.apk"
if($LASTEXITCODE -ne 0){throw 'Fault target packaging failed'}
& "$buildTools/zipalign.exe" -f 4 "$out/unsigned.apk" "$out/aligned.apk"
if($LASTEXITCODE -ne 0){throw 'Fault target alignment failed'}
& "$buildTools/apksigner.bat" sign --ks $key --ks-key-alias trial --ks-pass pass:android --key-pass pass:android --out "$out/FaultTarget.apk" "$out/aligned.apk"
if($LASTEXITCODE -ne 0){throw 'Fault target signing failed'}
& "$buildTools/apksigner.bat" verify "$out/FaultTarget.apk"
if($LASTEXITCODE -ne 0){throw 'Fault target verification failed'}
Get-FileHash "$out/FaultTarget.apk" -Algorithm SHA256

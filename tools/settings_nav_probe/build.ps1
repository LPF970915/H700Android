param([string]$Output='out/settings-deep-audit-20261023/probe')
$ErrorActionPreference='Stop'
$sdk=Join-Path $env:LOCALAPPDATA 'Android\Sdk'
$java='C:\Program Files\Java\jdk-11'
$android=Join-Path $sdk 'platforms\android-34\android.jar'
$buildTools=Join-Path $sdk 'build-tools\34.0.0'
$out=[IO.Path]::GetFullPath($Output)
New-Item -ItemType Directory -Force "$out/classes","$out/dex" | Out-Null
& "$java/bin/javac.exe" -source 8 -target 8 -classpath $android -d "$out/classes" "$PSScriptRoot/Dump.java"
if($LASTEXITCODE -ne 0){throw 'Probe javac failed'}
$env:JAVA_HOME=$java
& "$buildTools/d8.bat" --min-api 29 --lib $android --output "$out/dex" "$out/classes/Dump.class"
if($LASTEXITCODE -ne 0){throw 'Probe D8 failed'}
& "$java/bin/jar.exe" cf "$out/nav-probe.jar" -C "$out/dex" classes.dex
if($LASTEXITCODE -ne 0){throw 'Probe jar failed'}
Get-FileHash "$out/nav-probe.jar" -Algorithm SHA256

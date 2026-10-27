param([string]$Output='out/flicker-tools')
$ErrorActionPreference='Stop'
$sdk=Join-Path $env:LOCALAPPDATA 'Android\Sdk'
$java='C:\Program Files\Java\jdk-11'
$android=Join-Path $sdk 'platforms\android-34\android.jar'
$buildTools=Join-Path $sdk 'build-tools\34.0.0'
$out=[IO.Path]::GetFullPath($Output)
New-Item -ItemType Directory -Force "$out/classes","$out/dex" | Out-Null
& "$java/bin/javac.exe" -classpath $android -d "$out/classes" "$PSScriptRoot/WallpaperSwap.java"
if($LASTEXITCODE -ne 0){throw 'javac failed'}
$env:JAVA_HOME=$java
& "$buildTools/d8.bat" --min-api 29 --lib $android --output "$out/dex" "$out/classes/WallpaperSwap.class"
if($LASTEXITCODE -ne 0){throw 'd8 failed'}
& "$java/bin/jar.exe" cf "$out/wallpaper-swap.jar" -C "$out/dex" classes.dex
if($LASTEXITCODE -ne 0){throw 'jar failed'}
Get-FileHash "$out/wallpaper-swap.jar" -Algorithm SHA256

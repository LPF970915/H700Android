param(
    [string]$Distro = 'Ubuntu',
    [string]$SourceRoot = '/home/lpf/h700-android10/android',
    [switch]$RebuildRamdisk
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$out = Join-Path $root 'out/h700-android10-b2'
$product = "$SourceRoot/out/target/product/rgsp"
$wslRoot = ($root -replace '\\','/')
$wslRoot = "/mnt/" + $wslRoot.Substring(0,1).ToLowerInvariant() + $wslRoot.Substring(2)
$ramdiskImage = Join-Path $out 'ramdisk-android10.img'
$boot = Join-Path $out 'h700-android10-test-boot.img'
$template = Join-Path $root 'out/rgsp-android11-handoff-boot-fix32.img'
$kernel = Join-Path $root 'out/rgsp-android11-alpha/Image'
$dtb = Join-Path $root 'out/rgsp-android11-alpha/rgsp-rg34xxsp.dtb'

foreach ($path in @($template,$kernel,$dtb)) {
    if (!(Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing verified boot input: $path" }
}

New-Item -ItemType Directory -Force -Path $out | Out-Null
$builtRamdisk = "$product/ramdisk.img"
if ($RebuildRamdisk) {
    $cmd = "set -e; cd '$SourceRoot'; source build/envsetup.sh >/dev/null; lunch h700_rgsp-eng >/dev/null; m -j4 ramdisk"
    & wsl.exe -d $Distro -- bash -lc $cmd
    if ($LASTEXITCODE -ne 0) { throw "ramdisk generation failed: $LASTEXITCODE" }
}
& wsl.exe -d $Distro -- bash -lc "test -f '$builtRamdisk' && cp '$builtRamdisk' '$wslRoot/out/h700-android10-b2/ramdisk-android10.img'"
if ($LASTEXITCODE -ne 0) { throw "missing built ramdisk: $builtRamdisk" }

$toolWsl = "$wslRoot/tools/android_bootimg.py"
$templateWsl = "$wslRoot/out/rgsp-android11-handoff-boot-fix32.img"
$bootWsl = "$wslRoot/out/h700-android10-b2/h700-android10-test-boot.img"
$kernelWsl = "$wslRoot/out/rgsp-android11-alpha/Image"
$dtbWsl = "$wslRoot/out/rgsp-android11-alpha/rgsp-rg34xxsp.dtb"
$ramdiskWsl = "$wslRoot/out/h700-android10-b2/ramdisk-android10.img"
$packCommand = "python3 '$toolWsl' pack '$templateWsl' '$bootWsl' --kernel '$kernelWsl' --ramdisk '$ramdiskWsl' --dtb '$dtbWsl'"
& wsl.exe -d $Distro -- bash -lc $packCommand
if ($LASTEXITCODE -ne 0) { throw "boot image packing failed: $LASTEXITCODE" }

$system = "$SourceRoot/out/target/product/rgsp/system.img"
$vendor = "$SourceRoot/out/target/product/rgsp/vendor.img"
$ramdiskDir = "$SourceRoot/out/target/product/rgsp/ramdisk"
$rootDir = "$SourceRoot/out/target/product/rgsp/root"
$manifest = "$SourceRoot/out/target/product/rgsp/verified_assembled_vendor_manifest.xml"
$systemOut = Join-Path $out 'system.img'
$vendorOut = Join-Path $out 'vendor.img'
$manifestOut = Join-Path $out 'manifest.xml'
$fstabOut = Join-Path $out 'fstab.sun50iw9p1'
& wsl.exe -d $Distro -- bash -lc "cp '$system' '$wslRoot/out/h700-android10-b2/system.img'; cp '$vendor' '$wslRoot/out/h700-android10-b2/vendor.img'; cp '$manifest' '$wslRoot/out/h700-android10-b2/manifest.xml'; cp '$ramdiskDir/fstab.sun50iw9p1' '$wslRoot/out/h700-android10-b2/fstab.sun50iw9p1'"
if ($LASTEXITCODE -ne 0) { throw 'copying system/vendor images into B2 staging failed' }

$checks = @()
function Add-Check([string]$Name, [bool]$Ok, [string]$Detail) {
    $script:checks += [pscustomobject]@{ check=$Name; ok=$Ok; detail=$Detail }
}
function Test-Wsl([string]$Command, [string]$Detail) {
    & wsl.exe -d $Distro -- bash -lc $Command | Out-Null
    $ok = ($LASTEXITCODE -eq 0)
    Add-Check $Detail $ok $Command
}

Test-Wsl "test -f '$system'" 'system.img exists'
Test-Wsl "test -f '$vendor'" 'vendor.img exists'
Test-Wsl "test -x '$ramdiskDir/init'" 'ramdisk init exists'
Test-Wsl "test -f '$ramdiskDir/fstab.sun50iw9p1'" 'ramdisk fstab exists'
Test-Wsl "test -s '$manifest'" 'vendor manifest exists'
Add-Check 'staged system.img exists' (Test-Path -LiteralPath $systemOut -PathType Leaf) $systemOut
Add-Check 'staged vendor.img exists' (Test-Path -LiteralPath $vendorOut -PathType Leaf) $vendorOut
Add-Check 'staged manifest exists' (Test-Path -LiteralPath $manifestOut -PathType Leaf) $manifestOut
Add-Check 'staged fstab exists' (Test-Path -LiteralPath $fstabOut -PathType Leaf) $fstabOut

$forbidden = & wsl.exe -d $Distro -- bash -lc "rg -n -i 'H618|r36s|rk3326|rk30board' '$ramdiskDir' '$rootDir' '$manifest' 2>/dev/null || true"
Add-Check 'no forbidden product identities' ([string]::IsNullOrWhiteSpace(($forbidden -join "`n"))) (($forbidden -join "`n").Trim())

$extractDir = "$wslRoot/out/h700-android10-b2/boot-extracted"
& wsl.exe -d $Distro -- bash -lc "mkdir -p '$extractDir'; python3 '$toolWsl' extract '$bootWsl' '$extractDir' >/dev/null; cmp '$extractDir/kernel' '$kernelWsl'; cmp '$extractDir/dtb' '$dtbWsl'; cmp '$extractDir/ramdisk' '$ramdiskWsl'"
Add-Check 'boot components round-trip' ($LASTEXITCODE -eq 0) 'kernel, DTB and ramdisk match their verified inputs after extraction'
Add-Check 'boot image is 64 MiB' ((Get-Item -LiteralPath $boot).Length -eq 64MB) "$((Get-Item -LiteralPath $boot).Length) bytes"

$hashFiles = @($boot,$template,$kernel,$dtb,$ramdiskImage)
$hashLines = foreach ($file in $hashFiles) {
    $hash = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
    $relative = $file.Substring($root.Length).TrimStart([char[]]"\\/") -replace '\\','/'
    "$hash  $relative"
}
$hashLines += foreach ($file in @($systemOut,$vendorOut,$manifestOut,$fstabOut)) {
    $hash = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
    $relative = $file.Substring($root.Length).TrimStart([char[]]"\\/") -replace '\\','/'
    "$hash  $relative"
}
$hashLines | Set-Content -LiteralPath (Join-Path $out 'SHA256SUMS.txt') -Encoding ascii

$headerJson = & wsl.exe -d $Distro -- bash -lc "python3 '$toolWsl' inspect '$bootWsl'"
$headerJson | Set-Content -LiteralPath (Join-Path $out 'boot-header.json') -Encoding utf8

$checks | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $out 'STATIC_CHECKS.json') -Encoding utf8
if (($checks | Where-Object { !$_.ok }).Count -gt 0) { throw 'Static checks failed; see STATIC_CHECKS.json' }

$generated = Get-Date -Format 'yyyy-MM-dd HH:mm:ss K'
$readme = @'
# H700 Android 10 A10-B2 test staging

Generated: __GENERATED__

This is a no-write deployment staging package. It combines the Android 10 `rgsp`
userspace with the previously verified RGSP/H700 kernel, DTB and legacy boot
header. It must not be written to a device without an explicit B3 preparation
step that records CID, boot/env hashes, filesystem checks and rollback state.

Files:

- `h700-android10-test-boot.img`: 64 MiB legacy Android boot image.
- `ramdisk-android10.img`: gzip cpio ramdisk produced by the Android 10 build.
- `system.img`, `vendor.img`: Android 10 TF2 filesystem images.
- `manifest.xml`, `fstab.sun50iw9p1`: static deployment metadata copied from the build.
- `SHA256SUMS.txt`: hashes for all inputs and outputs.
- `boot-header.json`: parsed boot header and component offsets.
- `STATIC_CHECKS.json`: offline checks for required files and forbidden identities.

Android 10 source: `$SourceRoot`
Verified kernel input: `out/rgsp-android11-alpha/Image`
Verified DTB input: `out/rgsp-android11-alpha/rgsp-rg34xxsp.dtb`
Boot template: `out/rgsp-android11-handoff-boot-fix32.img`

No TF1/TF2 partition, U-Boot environment, or device state was modified.
'@
$readme = $readme.Replace('__GENERATED__', $generated).Replace('$SourceRoot', $SourceRoot)
$readme | Set-Content -LiteralPath (Join-Path $out 'README.md') -Encoding utf8

Write-Output "B2_OUT=$out"
Write-Output "BOOT=$boot"
Write-Output "RAMDISK=$ramdiskImage"
$passed = @($checks | Where-Object { $_.ok }).Count
Write-Output "CHECKS=$passed/$($checks.Count)"

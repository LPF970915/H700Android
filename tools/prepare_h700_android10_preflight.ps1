[CmdletBinding()]
param(
    [string]$Distro = 'Ubuntu',
    [string]$SourceRoot = '/home/lpf/h700-android10/android',
    [string]$StagingDirectory = 'out/h700-android10-b2',
    [string]$OutputDirectory = 'out/h700-android10-preflight',
    [string]$At4kApk = ''
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$staging = (Resolve-Path (Join-Path $root $StagingDirectory)).Path
$output = Join-Path $root $OutputDirectory
$wslRoot = ($root -replace '\\','/')
$wslRoot = '/mnt/' + $wslRoot.Substring(0,1).ToLowerInvariant() + $wslRoot.Substring(2)
$wslTool = "$wslRoot/tools/android_sparse_to_raw.py"
$wslStaging = "$wslRoot/$($StagingDirectory -replace '\\','/')"
$wslOutput = "$wslRoot/$($OutputDirectory -replace '\\','/')"

Write-Host 'Refreshing Android 10 B2 staging from the current source build...'
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'tools/prepare_h700_android10_b2.ps1') `
    -Distro $Distro -SourceRoot $SourceRoot
if ($LASTEXITCODE -ne 0) { throw "B2 staging failed: $LASTEXITCODE" }

New-Item -ItemType Directory -Force -Path $output | Out-Null
$at4kTarget = $null
if (-not [string]::IsNullOrWhiteSpace($At4kApk)) {
    $at4kSource = (Resolve-Path -LiteralPath $At4kApk).Path
    $at4kTarget = Join-Path $output 'AT4K-launcher.apk'
    Copy-Item -LiteralPath $at4kSource -Destination $at4kTarget -Force
}
$payloadNames = @(
    'h700-android10-test-boot.img',
    'ramdisk-android10.img',
    'system.img',
    'vendor.img',
    'manifest.xml',
    'fstab.sun50iw9p1',
    'boot-header.json',
    'STATIC_CHECKS.json'
)
foreach ($name in $payloadNames) {
    Copy-Item -LiteralPath (Join-Path $staging $name) -Destination (Join-Path $output $name) -Force
}
Copy-Item -LiteralPath (Join-Path $root 'tools/flash_sparse_over_http.py') `
    -Destination (Join-Path $output 'flash_sparse_over_http.py') -Force

$rawCommands = @(
    "mkdir -p '$wslOutput'",
    "python3 '$wslTool' '$wslStaging/system.img' '$wslOutput/system.raw.img'",
    "python3 '$wslTool' '$wslStaging/vendor.img' '$wslOutput/vendor.raw.img'"
)
foreach ($command in $rawCommands) {
    & wsl.exe -d $Distro -- bash -lc $command
    if ($LASTEXITCODE -ne 0) { throw "Sparse image conversion failed: $command" }
}

$expected = @{
    'system.raw.img' = 8589934592L
    'vendor.raw.img' = 2147483648L
    'h700-android10-test-boot.img' = 67108864L
}
foreach ($item in $expected.GetEnumerator()) {
    $path = Join-Path $output $item.Key
    if (!(Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing preflight artifact: $path" }
    $actual = (Get-Item -LiteralPath $path).Length
    if ($actual -ne $item.Value) { throw "$($item.Key) size mismatch: $actual != $($item.Value)" }
}

$fsChecks = @()
foreach ($name in @('system.raw.img','vendor.raw.img')) {
    $path = "$wslOutput/$name"
    $checkOutput = & wsl.exe -d $Distro -- bash -lc "e2fsck -fn '$path' 2>&1"
    $exitCode = $LASTEXITCODE
    $fsChecks += [pscustomobject]@{
        image = $name
        exit_code = $exitCode
        accepted = ($exitCode -le 1)
        output = ($checkOutput -join "`n").Trim()
    }
    if ($exitCode -gt 1) { throw "Offline ext4 check failed for $name with exit code $exitCode" }
}

$layout = @'
RGSP H700 TF2 preflight layout

Target device: RGSP H700 TF2
Target block device: /dev/mmcblk1
Sector size: 512 bytes

ANDROID_SYSTEM
  partition: mmcblk1p2
  offset: 269484032 bytes
  size: 8589934592 bytes
  partuuid: 096d7fa1-62e8-c242-9876-cfdd5a92b8eb

ANDROID_VENDOR
  partition: mmcblk1p3
  offset: 8859418624 bytes
  size: 2147483648 bytes
  partuuid: 6aa8b46e-b96f-9545-bbfb-1b7d2bdc7da8

ANDROID_DATA is intentionally not included. It must be preserved or explicitly
formatted on the device only after the first successful Android 10 boot plan
has been confirmed.
'@
$layout | Set-Content -LiteralPath (Join-Path $output 'TF2_LAYOUT.txt') -Encoding ascii

$fsChecks | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $output 'EXT4_CHECKS.json') -Encoding utf8
Copy-Item -LiteralPath (Join-Path $root 'tools/write_tf2_android10_preflight_admin.ps1') `
    -Destination (Join-Path $output 'write_tf2_android10_preflight_admin.ps1') -Force

$readme = @'
# H700 Android 10 RGSP preflight package

This directory is the final offline package prepared before the serial adapter
is moved from the H700 projector to the RGSP handheld.

Included payload:

- h700-android10-test-boot.img: 64 MiB boot image using the verified RGSP
  kernel and DTB with the current Android 10 ramdisk.
- system.img and vendor.img: Android sparse filesystem images.
- system.raw.img and vendor.raw.img: fixed-size TF2 images for the verified
  RGSP p2 and p3 geometry.
- manifest.xml, fstab.sun50iw9p1, boot-header.json and STATIC_CHECKS.json:
  deployment metadata and offline checks.
- EXT4_CHECKS.json and TF2_LAYOUT.txt: fixed-size image and partition checks.
- flash_sparse_over_http.py: target-restricted sparse writer with RAW chunk
  readback verification for the original Linux path.
- write_tf2_android10_preflight_admin.ps1: explicit, confirmation-protected
  Windows writer. It is not executed by this preparation step.
- SHA256SUMS.txt: hashes for every package file except the hash list itself.
__AT4K_NOTE__

Required before any device write:

1. Move the serial adapter to RGSP and enumerate the actual COM port.
2. Record TF1/TF2 CID, boot partition hash, U-Boot environment head hash and
   current TF2 p2/p3 readback hashes.
3. Confirm the physical disk geometry and rollback files against the live
   device. Never infer the disk number from an earlier session.
4. Use the one-shot boot/handoff procedure only after those checks pass.

This package does not modify a device, U-Boot environment, partition table,
TF1, TF2 or the projector.
'@
$at4kNote = if ($null -ne $at4kTarget) {
    '- AT4K-launcher.apk: user-supplied APK for normal post-boot installation; it is not part of system/vendor.'
} else {
    '- No third-party APK was copied; pass -At4kApk to include the user-supplied AT4K package locally.'
}
$readme = $readme.Replace('__AT4K_NOTE__', $at4kNote)
$readme | Set-Content -LiteralPath (Join-Path $output 'README.md') -Encoding ascii

$runbook = @'
# RGSP H700 first hardware session

This runbook starts only after the serial adapter has been moved from the
projector to the RGSP handheld. The package preparation itself is offline and
does not require a live COM port.

## Read-only discovery

From the repository root, enumerate the actual port. Do not reuse a port name
from the projector session:

```powershell
.\tools\capture_rgsp_uart.ps1 -List
```

Before writing anything, capture the RGSP boot console and record:

- the live COM port and baud rate;
- TF1 and TF2 CID values;
- TF1 boot partition SHA-256 and the U-Boot environment head SHA-256;
- TF2 p2 and p3 current hashes;
- the live GPT partition offsets and sizes;
- the current boot target and rollback path.

Use the existing UART and U-Boot probe tools only with the live port. A failed
probe is a stop condition, not a reason to guess the port or disk number.

## Write gate

The package writer is confirmation-protected and requires an explicit disk
number. Run it from this package directory only after the read-only checks
match `TF2_LAYOUT.txt`:

```powershell
.\write_tf2_android10_preflight_admin.ps1 -DiskNumber <verified-number>
```

It writes only `ANDROID_SYSTEM` p2 and `ANDROID_VENDOR` p3, then hashes both
ranges back from the physical disk. It does not write TF1, ANBOOT, U-Boot
environment, partition tables or `ANDROID_DATA`.

The 64 MiB test boot image is a separate one-shot boot/handoff input. Do not
replace the existing TF1 boot partition until the live boot path, rollback
state and current hashes have been captured and the handoff script has been
updated for the current boot hash.

## AT4K post-boot installation

If `AT4K-launcher.apk` is present, install it as a normal data-side application
after Android has booted and `/data` is mounted:

```text
adb install -r AT4K-launcher.apk
adb shell am start -n com.overdevs.at4k/.MainActivity
```

Do not grant root, accessibility or privileged permissions during the first
run. Keep Launcher3 as the recovery HOME until DPAD focus, B return, popup
exit and Settings/network navigation have passed.

## First boot evidence

After the explicit write and any separately approved handoff step, capture
UART, kmsg, logcat, ADB availability, mount state, SurfaceFlinger state and a
screen photo. Keep the original TF1 boot image and environment backups beside
the log set.
'@
$runbook | Set-Content -LiteralPath (Join-Path $output 'ON_DEVICE_RUNBOOK.md') -Encoding ascii

$manifest = [ordered]@{
    generated = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')
    product = 'h700_rgsp-eng'
    android = '10 / API 29'
    source_root = $SourceRoot
    package = 'h700-android10-preflight'
    writes_performed = $false
    target = [ordered]@{
        board = 'RGSP H700'
        soc = 'sun50iw9p1'
        display = '720x480 LCD'
        system_partition = 'mmcblk1p2'
        vendor_partition = 'mmcblk1p3'
    }
    artifacts = [ordered]@{}
    ext4_checks = $fsChecks
}
foreach ($file in Get-ChildItem -LiteralPath $output -File | Sort-Object Name) {
    if ($file.Name -in @('SHA256SUMS.txt','DEPLOYMENT_MANIFEST.json')) { continue }
    $manifest.artifacts[$file.Name] = [ordered]@{
        bytes = $file.Length
        sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $output 'DEPLOYMENT_MANIFEST.json') -Encoding utf8

$hashLines = foreach ($file in Get-ChildItem -LiteralPath $output -File | Sort-Object Name) {
    if ($file.Name -eq 'SHA256SUMS.txt') { continue }
    $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $($file.Name)"
}
$hashLines | Set-Content -LiteralPath (Join-Path $output 'SHA256SUMS.txt') -Encoding ascii

Write-Host "PREFLIGHT_OUT=$output"
Write-Host "ARTIFACTS=$((Get-ChildItem -LiteralPath $output -File).Count)"
Write-Host 'WRITES_PERFORMED=false'

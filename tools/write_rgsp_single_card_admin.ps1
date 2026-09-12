#requires -RunAsAdministrator
[CmdletBinding()]
param(
    [switch]$ConfirmWrite,
    [string]$Distro = 'Ubuntu'
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$out = Join-Path $root 'out/rgsp-single-card-20260911'
$diskNumber = 3
$expectedName = 'Generic MassStorageClass'
$expectedSerial = '000000001539'
$expectedSize = 62239277056L

if (-not $ConfirmWrite) {
    throw 'Refusing to write. Re-run with -ConfirmWrite after reviewing Disk 3.'
}

$disk = Get-Disk -Number $diskNumber
if ($disk.FriendlyName -ne $expectedName -or
    $disk.SerialNumber -ne $expectedSerial -or
    $disk.Size -ne $expectedSize -or
    $disk.BusType -ne 'USB') {
    throw 'Disk identity mismatch; refusing to write.'
}

foreach ($name in @(
    'boot-single-card.img',
    'system.raw.img',
    'vendor.raw.img',
    'data.raw.img'
)) {
    $path = Join-Path $out $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing staged image: $path"
    }
}

# Remove the Windows mount point before WSL claims the physical disk.
& mountvol F: /p
if ($LASTEXITCODE -ne 0) {
    throw 'Could not remove the F: mount point.'
}

$wslRoot = '/mnt/' + $root.Substring(0, 1).ToLowerInvariant() +
    ($root.Substring(2) -replace '\\', '/')
$wslOut = "$wslRoot/out/rgsp-single-card-20260911"
$writer = "$wslRoot/tools/write_rgsp_single_card_wsl.sh"
$physical = "\\.\PHYSICALDRIVE$diskNumber"

& wsl.exe --mount $physical --bare
if ($LASTEXITCODE -ne 0) {
    throw 'WSL could not attach the physical disk. No partition or image write was attempted.'
}

try {
    & wsl.exe -d $Distro -- bash $writer $wslOut $expectedSize
    if ($LASTEXITCODE -ne 0) {
        throw "Single-card physical write failed with exit code $LASTEXITCODE."
    }
}
finally {
    & wsl.exe --unmount $physical
}

Write-Host 'Single-card image write and readback completed.'

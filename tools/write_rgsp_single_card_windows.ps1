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
$sectorSize = 512L
$totalSectors = [long]($expectedSize / $sectorSize)
$template = Join-Path $out 'single-card-gpt-template.img'

$parts = @(
    [pscustomobject]@{ Number = 1; Start = 2048L; Size = 67108864L; Name = 'boot'; Guid = '3b9b1a40-0d34-4b3d-9f53-1f4a1ad1c701'; Image = 'boot-single-card.img' },
    [pscustomobject]@{ Number = 2; Start = 133120L; Size = 8589934592L; Name = 'system'; Guid = '096d7fa1-62e8-c242-9876-cfdd5a92b8eb'; Image = 'system.raw.img' },
    [pscustomobject]@{ Number = 3; Start = 16910336L; Size = 2147483648L; Name = 'vendor'; Guid = '6aa8b46e-b96f-9545-bbfb-1b7d2bdc7da8'; Image = 'vendor.raw.img' },
    [pscustomobject]@{ Number = 4; Start = 21104640L; Size = 17179869184L; Name = 'data'; Guid = '734716ed-e7d9-e74f-9b3e-4f1cb8d448ed'; Image = 'data.raw.img' },
    [pscustomobject]@{ Number = 5; Start = 54659072L; Size = ($totalSectors - 34L - 54659072L) * $sectorSize; Name = 'ROMS'; Guid = 'b4d04d65-2c35-4b7f-b9c5-8f24d2f10505'; Image = $null }
)

function Invoke-Checked {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList
    )
    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "$FilePath failed with exit code $LASTEXITCODE."
    }
}

function Copy-FileRangeToDisk {
    param(
        [System.IO.FileStream]$Disk,
        [string]$Path,
        [long]$Offset,
        [long]$ExpectedLength
    )
    $info = Get-Item -LiteralPath $Path
    if ($info.Length -ne $ExpectedLength) {
        throw "Unexpected image size for ${Path}: $($info.Length), expected $ExpectedLength."
    }
    $source = [System.IO.File]::OpenRead($Path)
    try {
        $Disk.Position = $Offset
        $buffer = New-Object byte[] (4MB)
        [long]$done = 0
        while (($read = $source.Read($buffer, 0, $buffer.Length)) -gt 0) {
            $Disk.Write($buffer, 0, $read)
            $done += $read
            if (($done % 256MB) -lt $read -or $done -eq $ExpectedLength) {
                Write-Host ("  {0}: {1:N1} / {2:N1} MiB" -f $info.Name, ($done / 1MB), ($ExpectedLength / 1MB))
            }
        }
    }
    finally {
        $source.Dispose()
    }
}

function Copy-TemplateRangeToDisk {
    param(
        [System.IO.FileStream]$Disk,
        [System.IO.FileStream]$TemplateStream,
        [long]$Offset,
        [long]$Length
    )
    $TemplateStream.Position = $Offset
    $Disk.Position = $Offset
    $buffer = New-Object byte[] (1MB)
    [long]$done = 0
    while ($done -lt $Length) {
        $want = [int][Math]::Min($buffer.Length, $Length - $done)
        $read = $TemplateStream.Read($buffer, 0, $want)
        if ($read -ne $want) {
            throw "Short read from GPT template at offset $($Offset + $done)."
        }
        $Disk.Write($buffer, 0, $read)
        $done += $read
    }
}

function Get-RangeHash {
    param(
        [System.IO.FileStream]$Stream,
        [long]$Offset,
        [long]$Length
    )
    $hash = [System.Security.Cryptography.IncrementalHash]::CreateHash(
        [System.Security.Cryptography.HashAlgorithmName]::SHA256
    )
    try {
        $Stream.Position = $Offset
        $buffer = New-Object byte[] (4MB)
        [long]$left = $Length
        while ($left -gt 0) {
            $want = [int][Math]::Min($buffer.Length, $left)
            $read = $Stream.Read($buffer, 0, $want)
            if ($read -ne $want) {
                throw "Short read from physical disk at offset $($Offset + ($Length - $left))."
            }
            $hash.AppendData($buffer, 0, $read)
            $left -= $read
        }
        return ([BitConverter]::ToString($hash.GetHashAndReset()).Replace('-', '').ToLowerInvariant())
    }
    finally {
        $hash.Dispose()
    }
}

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

foreach ($part in $parts | Where-Object Image) {
    $path = Join-Path $out $part.Image
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing staged image: $path"
    }
}

$wslTemplate = '/mnt/' + $template.Substring(0, 1).ToLowerInvariant() +
    ($template.Substring(2) -replace '\\', '/')
if (Test-Path -LiteralPath $template) {
    Remove-Item -LiteralPath $template -Force
}
$templateStream = [System.IO.File]::Open($template, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::Read)
try {
    $templateStream.SetLength($expectedSize)
}
finally {
    $templateStream.Dispose()
}

$sgdiskArgs = @(
    '-d', $Distro, '--', 'bash', '-lc',
    "sgdisk --zap-all '$wslTemplate' && " +
    "sgdisk --new=1:2048:+64M --typecode=1:8300 --change-name=1:boot --partition-guid=1:3b9b1a40-0d34-4b3d-9f53-1f4a1ad1c701 " +
    "--new=2:0:+8G --typecode=2:8300 --change-name=2:system --partition-guid=2:096d7fa1-62e8-c242-9876-cfdd5a92b8eb " +
    "--new=3:0:+2G --typecode=3:8300 --change-name=3:vendor --partition-guid=3:6aa8b46e-b96f-9545-bbfb-1b7d2bdc7da8 " +
    "--new=4:0:+16G --typecode=4:8300 --change-name=4:data --partition-guid=4:734716ed-e7d9-e74f-9b3e-4f1cb8d448ed " +
    "--new=5:0:0 --typecode=5:0700 --change-name=5:ROMS --partition-guid=5:b4d04d65-2c35-4b7f-b9c5-8f24d2f10505 '$wslTemplate' && " +
    "sgdisk --verify '$wslTemplate'"
)
Write-Host 'Generating GPT template...'
Invoke-Checked -FilePath 'wsl.exe' -ArgumentList $sgdiskArgs

Write-Host 'Taking Disk 3 offline and writing GPT plus Android images...'
& mountvol F: /p
if ($LASTEXITCODE -ne 0) {
    throw 'Could not remove the F: mount point.'
}
Set-Disk -Number $diskNumber -IsOffline $true
Start-Sleep -Seconds 2

$physical = "\\.\PHYSICALDRIVE$diskNumber"
$diskStream = [System.IO.FileStream]::new(
    $physical,
    [System.IO.FileMode]::Open,
    [System.IO.FileAccess]::ReadWrite,
    [System.IO.FileShare]::ReadWrite,
    4MB,
    [System.IO.FileOptions]::WriteThrough
)
$templateStream = [System.IO.File]::OpenRead($template)
try {
    Copy-TemplateRangeToDisk -Disk $diskStream -TemplateStream $templateStream -Offset 0 -Length (34L * $sectorSize)
    Copy-TemplateRangeToDisk -Disk $diskStream -TemplateStream $templateStream -Offset (($totalSectors - 33L) * $sectorSize) -Length (33L * $sectorSize)
    foreach ($part in $parts | Where-Object Image) {
        $path = Join-Path $out $part.Image
        Copy-FileRangeToDisk -Disk $diskStream -Path $path -Offset ($part.Start * $sectorSize) -ExpectedLength $part.Size
    }
    $diskStream.Flush()
}
finally {
    $templateStream.Dispose()
    $diskStream.Dispose()
}

Set-Disk -Number $diskNumber -IsOffline $false
Update-Disk -Number $diskNumber
Start-Sleep -Seconds 3

$actual = @(Get-Partition -DiskNumber $diskNumber | Where-Object PartitionNumber -le 5 | Sort-Object PartitionNumber)
if ($actual.Count -ne 5) {
    throw "Expected 5 partitions after GPT write, found $($actual.Count)."
}
foreach ($part in $parts) {
    $got = $actual | Where-Object PartitionNumber -eq $part.Number
    if ($got.Offset -ne ($part.Start * $sectorSize) -or $got.Size -ne $part.Size) {
        throw "Partition $($part.Number) geometry mismatch."
    }
    if ($got.Guid.ToString().ToLowerInvariant() -ne $part.Guid) {
        throw "Partition $($part.Number) GUID mismatch: $($got.Guid)."
    }
}

Set-Partition -DiskNumber $diskNumber -PartitionNumber 5 -NewDriveLetter F
& cmd.exe /c 'echo Y|format F: /FS:FAT32 /V:ROMS /Q /X /A:32768'
if ($LASTEXITCODE -ne 0) {
    throw 'FAT32 formatting of the ROMS partition failed.'
}

$diskStream = [System.IO.FileStream]::new(
    $physical,
    [System.IO.FileMode]::Open,
    [System.IO.FileAccess]::Read,
    [System.IO.FileShare]::ReadWrite,
    4MB,
    [System.IO.FileOptions]::SequentialScan
)
try {
    $checks = foreach ($part in $parts | Where-Object Image) {
        $path = Join-Path $out $part.Image
        $sourceHash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
        $targetHash = Get-RangeHash -Stream $diskStream -Offset ($part.Start * $sectorSize) -Length $part.Size
        [pscustomobject]@{
            Partition = $part.Number
            Image = $part.Image
            Source = $sourceHash
            Readback = $targetHash
            Match = ($sourceHash -eq $targetHash)
        }
    }
}
finally {
    $diskStream.Dispose()
}

$checks | Format-Table -AutoSize
if (@($checks | Where-Object { -not $_.Match }).Count -ne 0) {
    throw 'One or more partition image readback hashes did not match.'
}

$volume = Get-Volume -DriveLetter F
if ($volume.FileSystem -ne 'FAT32' -or $volume.FileSystemLabel -ne 'ROMS') {
    throw "ROMS volume verification failed: $($volume.FileSystem) / $($volume.FileSystemLabel)."
}

Write-Host 'Single-card Windows raw write and readback completed.'

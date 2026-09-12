#requires -RunAsAdministrator
[CmdletBinding()]
param(
    [switch]$ConfirmWrite,
    [switch]$PrepareOnly
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$out = Join-Path $root 'out/rgsp-single-card-20260911'
$bootArea = Join-Path $out 'tf1-boot-area-8m.bin'
$expectedName = 'Generic MassStorageClass'
$expectedSerial = '000000001539'
$expectedSize = 62239277056L
$sectorSize = 512L
$totalSectors = [long]($expectedSize / $sectorSize)
$bootAreaSize = 8MB

$parts = @(
    [pscustomobject]@{ Number = 1; Start = 16384L; Size = 67108864L; Name = 'boot'; Guid = '3b9b1a40-0d34-4b3d-9f53-1f4a1ad1c701'; Image = 'boot-single-card.img' },
    [pscustomobject]@{ Number = 2; Start = 147456L; Size = 8589934592L; Name = 'system'; Guid = '096d7fa1-62e8-c242-9876-cfdd5a92b8eb'; Image = 'system.raw.img' },
    [pscustomobject]@{ Number = 3; Start = 16924672L; Size = 2147483648L; Name = 'vendor'; Guid = '6aa8b46e-b96f-9545-bbfb-1b7d2bdc7da8'; Image = 'vendor.raw.img' },
    [pscustomobject]@{ Number = 4; Start = 21118976L; Size = 17179869184L; Name = 'data'; Guid = '734716ed-e7d9-e74f-9b3e-4f1cb8d448ed'; Image = 'data.raw.img' },
    [pscustomobject]@{ Number = 5; Start = 54673408L; Size = ($totalSectors - 3L - 54673408L) * $sectorSize; Name = 'ROMS'; Guid = 'b4d04d65-2c35-4b7f-b9c5-8f24d2f10505'; Image = $null }
)

if (-not (Test-Path -LiteralPath $bootArea -PathType Leaf)) {
    throw "Missing preserved TF1 boot area: $bootArea"
}
if ((Get-Item -LiteralPath $bootArea).Length -ne $bootAreaSize) {
    throw "Unexpected TF1 boot area size."
}

# Brandy places boot packages beyond 8 MiB. Never deploy this known-bad layout.
if ($bootAreaSize -le (32800L * $sectorSize + 64) -or
    $parts[0].Start -le 32800L) {
    throw 'Incomplete boot-area capture / boot-package overlap. Capture the original RGSP boot packages and review the layout before any write.'
}

function Convert-GuidBytes {
    param([string]$Guid)
    return ([Guid]::Parse($Guid)).ToByteArray()
}

function Convert-UInt64Bytes {
    param([UInt64]$Value)
    $bytes = New-Object byte[] 8
    for ($i = 0; $i -lt 8; $i++) {
        $bytes[$i] = [byte](($Value -shr (8 * $i)) -band 0xff)
    }
    return $bytes
}

function Get-Crc32 {
    param([byte[]]$Bytes)
    [uint32]$allOnes = [uint32]::MaxValue
    [uint32]$polynomial = [uint32]::Parse(
        'EDB88320',
        [System.Globalization.NumberStyles]::HexNumber
    )
    [uint32]$crc = $allOnes
    foreach ($byte in $Bytes) {
        $crc = $crc -bxor [uint32]$byte
        for ($i = 0; $i -lt 8; $i++) {
            if (($crc -band 1) -ne 0) {
                $crc = ($crc -shr 1) -bxor $polynomial
            } else {
                $crc = $crc -shr 1
            }
        }
    }
    return ($crc -bxor $allOnes)
}

function Set-Bytes {
    param(
        [byte[]]$Target,
        [int]$Offset,
        [byte[]]$Source
    )
    [Array]::Copy($Source, 0, $Target, $Offset, $Source.Length)
}

function Set-UInt32 {
    param([byte[]]$Target, [int]$Offset, [UInt32]$Value)
    Set-Bytes -Target $Target -Offset $Offset -Source @(
        [byte]($Value -band 0xff),
        [byte](($Value -shr 8) -band 0xff),
        [byte](($Value -shr 16) -band 0xff),
        [byte](($Value -shr 24) -band 0xff)
    )
}

function Set-UInt64 {
    param([byte[]]$Target, [int]$Offset, [UInt64]$Value)
    Set-Bytes -Target $Target -Offset $Offset -Source (Convert-UInt64Bytes $Value)
}

function Get-UInt32 {
    param([byte[]]$Bytes, [int]$Offset)
    return ([uint32]$Bytes[$Offset] -bor
        ([uint32]$Bytes[$Offset + 1] -shl 8) -bor
        ([uint32]$Bytes[$Offset + 2] -shl 16) -bor
        ([uint32]$Bytes[$Offset + 3] -shl 24))
}

function Normalize-GuidText {
    param([object]$Value)
    return $Value.ToString().Trim('{}').ToLowerInvariant()
}

function New-GptEntries {
    $entries = New-Object byte[] (8 * 128)
    $linuxType = Convert-GuidBytes '0fc63daf-8483-4772-8e79-3d69d8477de4'
    $basicType = Convert-GuidBytes 'ebd0a0a2-b9e5-4433-87c0-68b6b72699c7'
    foreach ($part in $parts) {
        $entryOffset = ($part.Number - 1) * 128
        $type = if ($part.Number -eq 5) { $basicType } else { $linuxType }
        Set-Bytes -Target $entries -Offset $entryOffset -Source $type
        Set-Bytes -Target $entries -Offset ($entryOffset + 16) -Source (Convert-GuidBytes $part.Guid)
        Set-UInt64 -Target $entries -Offset ($entryOffset + 32) -Value ([UInt64]$part.Start)
        Set-UInt64 -Target $entries -Offset ($entryOffset + 40) -Value ([UInt64]($part.Start + ($part.Size / $sectorSize) - 1))
        $nameBytes = [Text.Encoding]::Unicode.GetBytes($part.Name)
        Set-Bytes -Target $entries -Offset ($entryOffset + 56) -Source $nameBytes
    }
    return $entries
}

function New-GptHeader {
    param(
        [UInt64]$CurrentLba,
        [UInt64]$BackupLba,
        [UInt64]$EntriesLba,
        [UInt32]$EntriesCrc,
        [byte[]]$DiskGuid
    )
    $header = New-Object byte[] 512
    Set-Bytes -Target $header -Offset 0 -Source ([Text.Encoding]::ASCII.GetBytes('EFI PART'))
    Set-UInt32 -Target $header -Offset 8 -Value 0x00010000
    Set-UInt32 -Target $header -Offset 12 -Value 92
    Set-UInt64 -Target $header -Offset 24 -Value $CurrentLba
    Set-UInt64 -Target $header -Offset 32 -Value $BackupLba
    Set-UInt64 -Target $header -Offset 40 -Value 2048
    Set-UInt64 -Target $header -Offset 48 -Value ([UInt64]($totalSectors - 4))
    Set-Bytes -Target $header -Offset 56 -Source $DiskGuid
    Set-UInt64 -Target $header -Offset 72 -Value $EntriesLba
    Set-UInt32 -Target $header -Offset 80 -Value 8
    Set-UInt32 -Target $header -Offset 84 -Value 128
    Set-UInt32 -Target $header -Offset 88 -Value $EntriesCrc
    $crcInput = New-Object byte[] 92
    [Array]::Copy($header, 0, $crcInput, 0, 92)
    Set-UInt32 -Target $crcInput -Offset 16 -Value 0
    Set-UInt32 -Target $header -Offset 16 -Value (Get-Crc32 $crcInput)
    return $header
}

function Copy-FileToDisk {
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

function Copy-RangeToDisk {
    param(
        [System.IO.FileStream]$Disk,
        [string]$Path,
        [long]$Offset,
        [long]$Length
    )
    $source = [System.IO.File]::OpenRead($Path)
    try {
        $source.Position = $Offset
        $Disk.Position = $Offset
        $buffer = New-Object byte[] (4MB)
        [long]$left = $Length
        while ($left -gt 0) {
            $want = if ($left -lt $buffer.Length) { [int]$left } else { $buffer.Length }
            $read = $source.Read($buffer, 0, $want)
            if ($read -ne $want) {
                throw "Short read from preserved boot area."
            }
            $Disk.Write($buffer, 0, $read)
            $left -= $read
        }
    }
    finally {
        $source.Dispose()
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
            $want = if ($left -lt $buffer.Length) { [int]$left } else { $buffer.Length }
            $read = $Stream.Read($buffer, 0, $want)
            if ($read -ne $want) {
                throw 'Short read from physical disk.'
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

$matches = @(Get-Disk | Where-Object {
    $_.FriendlyName -eq $expectedName -and
    $_.SerialNumber -eq $expectedSerial -and
    $_.Size -eq $expectedSize -and
    $_.BusType -eq 'USB'
})
if ($matches.Count -ne 1) {
    throw "Expected exactly one matching target disk, found $($matches.Count)."
}
$disk = $matches[0]
$diskNumber = $disk.Number
if ($disk.PartitionStyle -eq 'RAW' -and $disk.OperationalStatus -eq 'No Media') {
    throw 'Disk identity mismatch; refusing to write.'
}

foreach ($part in $parts | Where-Object Image) {
    $path = Join-Path $out $part.Image
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing staged image: $path"
    }
}

$entries = New-GptEntries
$entriesCrc = Get-Crc32 $entries
$diskGuid = Convert-GuidBytes 'c6f0c6f8-6d07-42c7-96b7-70e146c4d8a1'
$primaryHeader = New-GptHeader -CurrentLba 1 -BackupLba ([UInt64]($totalSectors - 1)) -EntriesLba 2 -EntriesCrc $entriesCrc -DiskGuid $diskGuid
$backupHeader = New-GptHeader -CurrentLba ([UInt64]($totalSectors - 1)) -BackupLba 1 -EntriesLba ([UInt64]($totalSectors - 3)) -EntriesCrc $entriesCrc -DiskGuid $diskGuid
$preflight = [pscustomobject]@{
    TargetDisk = $diskNumber
    TotalSectors = $totalSectors
    EntriesCrc32 = ('{0:x8}' -f $entriesCrc)
    PrimaryHeaderCrc32 = ('{0:x8}' -f (Get-UInt32 -Bytes $primaryHeader -Offset 16))
    BackupHeaderCrc32 = ('{0:x8}' -f (Get-UInt32 -Bytes $backupHeader -Offset 16))
    PartitionCount = $parts.Count
}
if ($PrepareOnly) {
    $preflight | Format-List
    exit 0
}
$mbr = New-Object byte[] 512
$mbr[446 + 4] = 0xee
Set-UInt32 -Target $mbr -Offset (446 + 8) -Value 1
Set-UInt32 -Target $mbr -Offset (446 + 12) -Value ([uint32]::MaxValue)
$mbr[510] = 0x55
$mbr[511] = 0xaa

Write-Host 'Preparing removable Disk 3 and writing GPT plus Android images...'
$existingF = Get-Volume -DriveLetter F -ErrorAction SilentlyContinue
if ($null -ne $existingF) {
    & mountvol F: /p
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not remove the F: mount point.'
    }
}
Start-Sleep -Seconds 1

$physical = "\\.\PHYSICALDRIVE$diskNumber"
$diskStream = [System.IO.FileStream]::new(
    $physical,
    [System.IO.FileMode]::Open,
    [System.IO.FileAccess]::ReadWrite,
    [System.IO.FileShare]::ReadWrite,
    4MB,
    [System.IO.FileOptions]::WriteThrough
)
try {
    # Preserve the real H700 Allwinner boot0/boot package. The GPT written
    # below replaces only the protective MBR and the active GPT records.
    Copy-RangeToDisk -Disk $diskStream -Path $bootArea -Offset 0 -Length $bootAreaSize
    $diskStream.Position = 0
    $diskStream.Write($mbr, 0, $mbr.Length)
    $diskStream.Write($primaryHeader, 0, $primaryHeader.Length)
    $diskStream.Write($entries, 0, $entries.Length)
    $diskStream.Position = ($totalSectors - 3) * $sectorSize
    $diskStream.Write($entries, 0, $entries.Length)
    $diskStream.Write($backupHeader, 0, $backupHeader.Length)
    foreach ($part in $parts | Where-Object Image) {
        Copy-FileToDisk -Disk $diskStream -Path (Join-Path $out $part.Image) -Offset ($part.Start * $sectorSize) -ExpectedLength $part.Size
    }
    $diskStream.Flush()
}
finally {
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
    if (([Guid]::Parse((Normalize-GuidText $got.Guid))).ToString().ToLowerInvariant() -ne
        ([Guid]::Parse((Normalize-GuidText $part.Guid))).ToString().ToLowerInvariant()) {
        throw "Partition $($part.Number) GUID mismatch: $($got.Guid)."
    }
}

Set-Partition -DiskNumber $diskNumber -PartitionNumber 5 -NewDriveLetter F
Format-Volume -DriveLetter F -FileSystem FAT32 -AllocationUnitSize 32768 -NewFileSystemLabel ROMS -Confirm:$false -Force | Out-Null

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

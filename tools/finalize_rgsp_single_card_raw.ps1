#requires -RunAsAdministrator
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
# The legacy finalizer formats ROMS and cannot qualify missing boot packages.
throw 'Known-bad 8 MiB single-card layout is quarantined. Do not format ROMS or certify this card with the legacy finalizer; use read-only inspection.'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$out = Join-Path $root 'out/rgsp-single-card-20260911'
$log = Join-Path $out 'single-card-finalize.log'
Start-Transcript -LiteralPath $log -Force | Out-Null

try {
    $expectedName = 'Generic MassStorageClass'
    $expectedSerial = '000000001539'
    $expectedSize = 62239277056L
    $sectorSize = 512L
    $totalSectors = [long]($expectedSize / $sectorSize)
    $parts = @(
        [pscustomobject]@{ Number = 1; Start = 16384L; Size = 67108864L; Name = 'boot'; Guid = '3b9b1a40-0d34-4b3d-9f53-1f4a1ad1c701'; Image = 'boot-single-card.img' },
        [pscustomobject]@{ Number = 2; Start = 147456L; Size = 8589934592L; Name = 'system'; Guid = '096d7fa1-62e8-c242-9876-cfdd5a92b8eb'; Image = 'system.raw.img' },
        [pscustomobject]@{ Number = 3; Start = 16924672L; Size = 2147483648L; Name = 'vendor'; Guid = '6aa8b46e-b96f-9545-bbfb-1b7d2bdc7da8'; Image = 'vendor.raw.img' },
        [pscustomobject]@{ Number = 4; Start = 21118976L; Size = 17179869184L; Name = 'data'; Guid = '734716ed-e7d9-e74f-9b3e-4f1cb8d448ed'; Image = 'data.raw.img' },
        [pscustomobject]@{ Number = 5; Start = 54673408L; Size = ($totalSectors - 3L - 54673408L) * $sectorSize; Name = 'ROMS'; Guid = 'b4d04d65-2c35-4b7f-b9c5-8f24d2f10505'; Image = $null }
    )

    function Normalize-GuidText {
        param([object]$Value)
        return $Value.ToString().Trim('{}').ToLowerInvariant()
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
    if ($disk.OperationalStatus -ne 'Online' -or $disk.IsReadOnly) {
        throw 'Target disk is not writable and online.'
    }

    $actual = @(Get-Partition -DiskNumber $diskNumber | Sort-Object PartitionNumber)
    if ($actual.Count -ne 5) {
        throw "Expected 5 partitions after image write, found $($actual.Count)."
    }
    foreach ($part in $parts) {
        $got = $actual | Where-Object PartitionNumber -eq $part.Number
        if ($null -eq $got) {
            throw "Missing partition $($part.Number)."
        }
        if ($got.Offset -ne ($part.Start * $sectorSize) -or $got.Size -ne $part.Size) {
            throw "Partition $($part.Number) geometry mismatch."
        }
        if (([Guid]::Parse((Normalize-GuidText $got.Guid))).ToString().ToLowerInvariant() -ne
            ([Guid]::Parse((Normalize-GuidText $part.Guid))).ToString().ToLowerInvariant()) {
            throw "Partition $($part.Number) GUID mismatch: $($got.Guid)."
        }
    }
    Write-Host 'Partition geometry and GUID validation passed.'

    $existingF = Get-Volume -DriveLetter F -ErrorAction SilentlyContinue
    if ($null -ne $existingF) {
        & mountvol F: /p
        if ($LASTEXITCODE -ne 0) {
            throw 'Could not remove the F: mount point.'
        }
    }
    Set-Partition -DiskNumber $diskNumber -PartitionNumber 5 -NewDriveLetter F
    Format-Volume -DriveLetter F -FileSystem FAT32 -AllocationUnitSize 32768 -NewFileSystemLabel ROMS -Confirm:$false -Force | Out-Null
    Write-Host 'ROMS FAT32 formatting completed.'

    $physical = "\\.\PHYSICALDRIVE$diskNumber"
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
    Write-Host 'Single-card image finalize and readback completed.'
}
finally {
    Stop-Transcript | Out-Null
}

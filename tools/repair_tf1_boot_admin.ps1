param(
    [int]$DiskNumber = 3,
    [string]$Workspace = 'D:\Works\H700Android',
    [string]$ExpectedCurrentSha = '1ed746d7d967fd21b7a24aa9733ca22569dd600e93f81fbfddfd028530f3965c'
)

$ErrorActionPreference = 'Stop'

$ExpectedOriginalSha = 'd42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5'
$ExpectedPartitionOffset = 155189248L
$ExpectedPartitionSize = 67108864L
$OriginalImage = Join-Path $Workspace 'input\boot-live.img'
$LogDirectory = Join-Path $Workspace 'out\logs\tf1-repair'
$Timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$BackupImage = Join-Path $LogDirectory "tf1-p4-before-repair-$Timestamp.img"
$LogPath = Join-Path $LogDirectory "tf1-repair-$Timestamp.log"

New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
Start-Transcript -Path $LogPath -Force | Out-Null

function Get-RangeSha256 {
    param(
        [System.IO.FileStream]$Stream,
        [long]$Offset,
        [long]$Length,
        [string]$BackupPath
    )

    $sha = [System.Security.Cryptography.SHA256]::Create()
    $buffer = New-Object byte[] (1MB)
    $remaining = $Length
    $Stream.Position = $Offset
    $backup = $null
    if ($BackupPath) {
        $backup = [System.IO.File]::Open($BackupPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    }
    try {
        while ($remaining -gt 0) {
            $want = [int][Math]::Min($buffer.Length, $remaining)
            $read = $Stream.Read($buffer, 0, $want)
            if ($read -ne $want) {
                throw "Short raw read: wanted $want bytes, received $read."
            }
            if ($backup) {
                $backup.Write($buffer, 0, $read)
            }
            [void]$sha.TransformBlock($buffer, 0, $read, $null, 0)
            $remaining -= $read
        }
        [void]$sha.TransformFinalBlock([byte[]]::new(0), 0, 0)
        return ([BitConverter]::ToString($sha.Hash).Replace('-', '').ToLowerInvariant())
    } finally {
        if ($backup) {
            $backup.Flush($true)
            $backup.Dispose()
        }
        $sha.Dispose()
    }
}

try {
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
    if (-not $isAdmin) {
        throw 'Administrator privileges are required.'
    }

    $disk = Get-Disk -Number $DiskNumber
    $partitions = @(Get-Partition -DiskNumber $DiskNumber | Sort-Object PartitionNumber)
    $bootPartition = $partitions | Where-Object PartitionNumber -eq 4

    if ($disk.BusType -ne 'USB' -or $disk.IsBoot -or $disk.IsSystem) {
        throw 'Target is not a non-system USB disk.'
    }
    if ($disk.Size -lt 14GB -or $disk.Size -gt 16GB) {
        throw "Unexpected TF1 capacity: $($disk.Size)."
    }
    if ($partitions.Count -ne 8) {
        throw "Unexpected partition count: $($partitions.Count)."
    }
    if (-not $bootPartition -or $bootPartition.Offset -ne $ExpectedPartitionOffset -or $bootPartition.Size -ne $ExpectedPartitionSize) {
        throw 'TF1 p4 offset or size does not match the protected layout.'
    }
    if (-not (Test-Path -LiteralPath $OriginalImage)) {
        throw "Original boot image is missing: $OriginalImage"
    }
    $image = Get-Item -LiteralPath $OriginalImage
    $imageSha = (Get-FileHash -LiteralPath $OriginalImage -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($image.Length -ne $ExpectedPartitionSize -or $imageSha -ne $ExpectedOriginalSha) {
        throw "Original boot image validation failed: size=$($image.Length), sha=$imageSha"
    }

    Write-Host "TARGET_DISK=$DiskNumber"
    Write-Host "TARGET_MODEL=$($disk.FriendlyName)"
    Write-Host "TARGET_SIZE=$($disk.Size)"
    Write-Host "P4_OFFSET=$($bootPartition.Offset)"
    Write-Host "P4_SIZE=$($bootPartition.Size)"
    Write-Host "TARGET_BOOT_SHA=$imageSha"

    $diskWasOfflined = $false
    if ($disk.BusType -ne 'USB') {
        Set-Disk -Number $DiskNumber -IsOffline $true
        $diskWasOfflined = $true
    }
    # Windows refuses Set-Disk -IsOffline for removable media. Partition 4
    # has no mounted filesystem, so address only that partition device and
    # leave the mounted ROMS volume on partition 8 untouched.
    $rawPath = "\\?\GLOBALROOT\Device\Harddisk$DiskNumber\Partition4"
    $rawOffset = 0L
    $raw = [System.IO.File]::Open($rawPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::ReadWrite)
    try {
        $currentSha = Get-RangeSha256 -Stream $raw -Offset $rawOffset -Length $ExpectedPartitionSize -BackupPath $BackupImage
        Write-Host "CURRENT_P4_SHA=$currentSha"
        Write-Host "BACKUP_IMAGE=$BackupImage"
        if ($currentSha -ne $ExpectedCurrentSha) {
            throw "Current p4 does not match the explicitly authorized pre-repair image: $currentSha"
        }

        $source = [System.IO.File]::OpenRead($OriginalImage)
        try {
            $raw.Position = $rawOffset
            $source.CopyTo($raw, 1MB)
            $raw.Flush($true)
        } finally {
            $source.Dispose()
        }

        $readbackSha = Get-RangeSha256 -Stream $raw -Offset $rawOffset -Length $ExpectedPartitionSize -BackupPath $null
        Write-Host "READBACK_P4_SHA=$readbackSha"
        if ($readbackSha -ne $ExpectedOriginalSha) {
            throw "TF1 p4 readback verification failed: $readbackSha"
        }
    } finally {
        $raw.Dispose()
    }

    Write-Host 'TF1_BOOT_REPAIR_OK'
} catch {
    Write-Error $_
    exit 1
} finally {
    if ($diskWasOfflined) {
        try {
            Set-Disk -Number $DiskNumber -IsOffline $false
        } catch {
            Write-Warning "Could not bring disk $DiskNumber online automatically: $_"
        }
    }
    Stop-Transcript | Out-Null
}

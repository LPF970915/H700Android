[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('Backup', 'BackupBoot', 'Write')][string]$Mode,
    [Parameter(Mandatory = $true)][int]$DiskNumber,
    [Parameter(Mandatory = $true)][string]$BackupDirectory,
    [string]$PackageDirectory,
    [string]$BootSnapshotDirectory
)

$ErrorActionPreference = 'Stop'
$backup = [IO.Path]::GetFullPath($BackupDirectory)
if ($backup -notlike 'D:\Works\H700Android\out\*') { throw 'Backup must stay in workspace out.' }
New-Item -ItemType Directory -Force -Path $backup | Out-Null
$log = Join-Path $backup "$Mode.log"
Start-Transcript -Path $log -Append | Out-Null
$raw = $null
$locks = @()
$exitCode = 1
try {
    $disk = Get-Disk -Number $DiskNumber
    if ($disk.BusType -ne 'USB' -or $disk.Size -ne 125069950976L -or
        $disk.PartitionStyle -ne 'GPT' -or $disk.IsBoot -or $disk.IsSystem -or
        $disk.IsOffline -or $disk.IsReadOnly) { throw 'Disk identity gate failed.' }
    $parts = @(Get-Partition -DiskNumber $DiskNumber | Sort-Object PartitionNumber)
    $geometry = @(
        @(1048576L, 268435456L, '0720745f-bbfb-4940-bef7-8595c6f34f4b'),
        @(269484032L, 8589934592L, '096d7fa1-62e8-c242-9876-cfdd5a92b8eb'),
        @(8859418624L, 2147483648L, '6aa8b46e-b96f-9545-bbfb-1b7d2bdc7da8'),
        @(11006902272L, 17179869184L, '734716ed-e7d9-e74f-9b3e-4f1cb8d448ed'),
        @(28186771456L, 96883162624L, '324a1514-de37-6344-8d09-ed5dd8b90da2')
    )
    if ($parts.Count -ne 5) { throw 'Expected five partitions.' }
    for ($i = 0; $i -lt 5; $i++) {
        if ($parts[$i].PartitionNumber -ne $i + 1 -or
            $parts[$i].Offset -ne $geometry[$i][0] -or
            $parts[$i].Size -ne $geometry[$i][1] -or
            ([guid]$parts[$i].Guid).ToString() -ne $geometry[$i][2]) {
            throw "Partition $($i + 1) identity mismatch."
        }
    }
    $bootRoot = "$($parts[0].DriveLetter):\"
    if ($bootRoot -notmatch '^[A-Z]:\\$') { throw 'ANBOOT drive is not mounted.' }
    $linuxBoot = Join-Path $bootRoot 'rgsp-linux-boot-original.img'
    if ((Get-FileHash -LiteralPath $linuxBoot).Hash.ToLowerInvariant() -ne
        'd42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5') {
        throw 'Linux recovery image hash mismatch.'
    }
    if (Test-Path -LiteralPath (Join-Path $bootRoot 'RGSP_ANDROID_TRY.ONCE')) {
        throw 'An unconsumed Android boot request exists.'
    }
    $receiptPath = Join-Path $backup 'backup.json'
    $ranges = @(
        @{ Name = 'gpt-head.bin'; Offset = 0L; Length = 1048576L },
        @{ Name = 'anboot.img'; Offset = 1048576L; Length = 268435456L },
        @{ Name = 'system.before.img'; Offset = 269484032L; Length = 8589934592L },
        @{ Name = 'vendor.before.img'; Offset = 8859418624L; Length = 2147483648L },
        @{ Name = 'gpt-tail.bin'; Offset = 125069934080L; Length = 16896L }
    )
    $buffer = New-Object byte[] (4MB)
    function Hash-Range($stream, [long]$offset, [long]$length) {
        [void]$stream.Seek($offset, [IO.SeekOrigin]::Begin)
        $sha = [Security.Cryptography.SHA256]::Create()
        try {
            $left = $length
            $lastReport = $left
            while ($left -gt 0) {
                $n = $stream.Read($buffer, 0, [int][Math]::Min($left, $buffer.Length))
                if ($n -le 0) { throw 'Unexpected disk EOF.' }
                [void]$sha.TransformBlock($buffer, 0, $n, $buffer, 0)
                $left -= $n
                if ($lastReport - $left -ge 1GB) {
                    Write-Host "HASH_RANGE offset=$offset checked=$($length - $left)/$length"
                    $lastReport = $left
                }
            }
            [void]$sha.TransformFinalBlock([byte[]]@(), 0, 0)
            return ([BitConverter]::ToString($sha.Hash) -replace '-', '').ToLowerInvariant()
        } finally { $sha.Dispose() }
    }
    $devicePath = "\\.\PhysicalDrive$DiskNumber"
    Write-Host "MODE=$Mode TARGET=$devicePath SERIAL=$($disk.SerialNumber)"
    if ($Mode -in @('BackupBoot', 'Write')) {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class RgspVolumeLock {
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool DeviceIoControl(SafeFileHandle h, uint code,
        IntPtr input, uint inputSize, IntPtr output, uint outputSize,
        out uint returned, IntPtr overlapped);
}
'@
        $toLock = @($parts[0])
        if ($Mode -eq 'Write') { $toLock += @($parts[1], $parts[2]) }
        foreach ($part in $toLock) {
            $volume = @($part.AccessPaths | Where-Object { $_ -like '\\?\Volume{*' })[0]
            if (!$volume) { throw 'Partition volume path missing.' }
            $handle = [IO.File]::Open($volume.TrimEnd('\'), 'Open', 'ReadWrite', 'ReadWrite')
            $locks += $handle
            $returned = [uint32]0
            if (![RgspVolumeLock]::DeviceIoControl($handle.SafeFileHandle, 0x00090018,
                [IntPtr]::Zero, 0, [IntPtr]::Zero, 0, [ref]$returned, [IntPtr]::Zero)) {
                throw "Volume lock failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
            }
        }
    }
    if ($Mode -in @('Backup', 'BackupBoot')) {
        if ($Mode -eq 'BackupBoot') {
            $ranges = @($ranges | Where-Object Name -in @('gpt-head.bin', 'anboot.img', 'gpt-tail.bin'))
        }
        if (Test-Path -LiteralPath $receiptPath) { throw 'Backup receipt already exists; do not overwrite.' }
        $raw = [IO.File]::Open($devicePath, 'Open', 'Read', 'ReadWrite')
        $records = @()
        foreach ($range in $ranges) {
            $path = Join-Path $backup $range.Name
            $dest = [IO.File]::Open($path, 'CreateNew', 'Write', 'None')
            $sha = [Security.Cryptography.SHA256]::Create()
            try {
                [void]$raw.Seek($range.Offset, [IO.SeekOrigin]::Begin)
                $left = $range.Length
                $lastReport = $left
                while ($left -gt 0) {
                    $n = $raw.Read($buffer, 0, [int][Math]::Min($left, $buffer.Length))
                    if ($n -le 0) { throw 'Unexpected EOF during backup.' }
                    $dest.Write($buffer, 0, $n)
                    [void]$sha.TransformBlock($buffer, 0, $n, $buffer, 0)
                    $left -= $n
                    if ($lastReport - $left -ge 256MB) {
                        Write-Host "$($range.Name) copied=$($range.Length - $left)/$($range.Length)"
                        $lastReport = $left
                    }
                }
                $dest.Flush($true)
                [void]$sha.TransformFinalBlock([byte[]]@(), 0, 0)
                $hash = ([BitConverter]::ToString($sha.Hash) -replace '-', '').ToLowerInvariant()
            } finally { $sha.Dispose(); $dest.Dispose() }
            if ((Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant() -ne $hash) {
                throw "Backup verification failed: $path"
            }
            $records += @{ file = $range.Name; offset = $range.Offset; bytes = $range.Length; sha256 = $hash }
            Write-Host "BACKUP_VERIFIED=$($range.Name) SHA256=$hash"
        }
        @{
            recorded = (Get-Date).ToString('o'); disk_unique_id = $disk.UniqueId
            disk_bytes = $disk.Size; partitions = $geometry; ranges = $records
            writes_performed = $false
        } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $receiptPath -Encoding UTF8
        Write-Host 'TF2_BACKUP_OK'
    } else {
        if (!$PackageDirectory) { throw 'PackageDirectory required for Write.' }
        $receipt = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
        if ($receipt.disk_unique_id -ne $disk.UniqueId) { throw 'Reader identity changed since backup.' }
        $manifest = Get-Content -LiteralPath (Join-Path $PackageDirectory 'DEPLOYMENT_MANIFEST.json') -Raw | ConvertFrom-Json
        foreach ($name in @('system.raw.img', 'vendor.raw.img')) {
            $image = Join-Path $PackageDirectory $name
            $entry = $manifest.artifacts.$name
            if (!$entry -or (Get-Item -LiteralPath $image).Length -ne $entry.bytes -or
                (Get-FileHash -LiteralPath $image).Hash.ToLowerInvariant() -ne $entry.sha256) {
                throw "Package integrity failed: $name"
            }
        }
        if ($manifest.artifacts.'system.raw.img'.bytes -ne 8589934592L -or
            $manifest.artifacts.'vendor.raw.img'.bytes -ne 2147483648L) { throw 'Image size mismatch.' }
        if ($BootSnapshotDirectory) {
            $bootSnapshot = Get-Content -LiteralPath (Join-Path $BootSnapshotDirectory 'backup.json') -Raw | ConvertFrom-Json
            if ($bootSnapshot.disk_unique_id -ne $disk.UniqueId) { throw 'Boot snapshot identity mismatch.' }
            foreach ($name in @('gpt-head.bin', 'anboot.img', 'gpt-tail.bin')) {
                $old = @($receipt.ranges | Where-Object file -eq $name)[0]
                $fresh = @($bootSnapshot.ranges | Where-Object file -eq $name)[0]
                if (!$fresh -or $fresh.offset -ne $old.offset -or $fresh.bytes -ne $old.bytes -or
                    (Get-FileHash -LiteralPath (Join-Path $backup $name)).Hash.ToLowerInvariant() -ne $old.sha256 -or
                    (Get-FileHash -LiteralPath (Join-Path $BootSnapshotDirectory $name)).Hash.ToLowerInvariant() -ne $fresh.sha256) {
                    throw 'Boot snapshot metadata or backup hash mismatch.'
                }
                if ($name -ne 'anboot.img' -and $old.sha256 -ne $fresh.sha256) {
                    throw 'Partition table changed since original backup.'
                }
                if ($name -eq 'anboot.img') {
                    $old.sha256 = $fresh.sha256
                    Write-Host "REVIEWED_BOOT_SNAPSHOT=$BootSnapshotDirectory SHA256=$($fresh.sha256)"
                }
            }
        }
        $raw = [IO.File]::Open($devicePath, 'Open', 'ReadWrite', 'ReadWrite')
        foreach ($range in $ranges) {
            $record = @($receipt.ranges | Where-Object file -eq $range.Name)[0]
            if (!$record -or $record.offset -ne $range.Offset -or $record.bytes -ne $range.Length) {
                throw 'Backup range metadata mismatch.'
            }
            $rangeBackup = Join-Path $backup $range.Name
            if ($BootSnapshotDirectory -and $range.Name -eq 'anboot.img') {
                $rangeBackup = Join-Path $BootSnapshotDirectory $range.Name
            }
            if ((Get-FileHash -LiteralPath $rangeBackup).Hash.ToLowerInvariant() -ne $record.sha256 -or
                (Hash-Range $raw $range.Offset $range.Length) -ne $record.sha256) {
                throw "Backup or live content changed: $($range.Name)"
            }
            Write-Host "PREWRITE_VERIFIED=$($range.Name)"
        }
        $written = @()
        for ($i = 1; $i -le 2; $i++) {
            $name = @('system.raw.img', 'vendor.raw.img')[$i - 1]
            $input = [IO.File]::Open((Join-Path $PackageDirectory $name), 'Open', 'Read', 'Read')
            try {
                [void]$raw.Seek($parts[$i].Offset, [IO.SeekOrigin]::Begin)
                $left = [long]$parts[$i].Size
                $lastReport = $left
                while ($left -gt 0) {
                    $n = $input.Read($buffer, 0, [int][Math]::Min($left, $buffer.Length))
                    if ($n -le 0) { throw 'Unexpected source EOF.' }
                    $raw.Write($buffer, 0, $n)
                    $left -= $n
                    if ($lastReport - $left -ge 256MB) {
                        Write-Host "$name written=$($parts[$i].Size - $left)/$($parts[$i].Size)"
                        $lastReport = $left
                    }
                }
                $raw.Flush($true)
            } finally { $input.Dispose() }
            $actual = Hash-Range $raw $parts[$i].Offset $parts[$i].Size
            if ($actual -ne $manifest.artifacts.$name.sha256) { throw "Readback failed: $name" }
            $written += @{ image = $name; sha256 = $actual; partition = $i + 1 }
            Write-Host "READBACK_VERIFIED=$name SHA256=$actual"
        }
        foreach ($name in @('gpt-head.bin', 'anboot.img', 'gpt-tail.bin')) {
            $r = @($receipt.ranges | Where-Object file -eq $name)[0]
            if ((Hash-Range $raw $r.offset $r.bytes) -ne $r.sha256) { throw "Protected range changed: $name" }
        }
        @{ completed = (Get-Date).ToString('o'); written = $written; untouched_partitions = @(1, 4, 5) } |
            ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $backup 'write.json') -Encoding UTF8
        Write-Host 'TF2_WRITE_READBACK_OK'
    }
    $exitCode = 0
} catch {
    Write-Host "FAILED=$($_.Exception.Message)"
    Write-Host $_.ScriptStackTrace
} finally {
    if ($raw) { $raw.Dispose() }
    foreach ($handle in $locks) { $handle.Dispose() }
    [IO.File]::WriteAllText((Join-Path $backup "$Mode.exitcode"), [string]$exitCode)
    Stop-Transcript | Out-Null
}
exit $exitCode

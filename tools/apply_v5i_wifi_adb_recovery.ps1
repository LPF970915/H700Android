#requires -RunAsAdministrator
[CmdletBinding()]
param(
    [Parameter(Mandatory)][int]$DiskNumber,
    [Parameter(Mandatory)][long]$ExpectedSize,
    [Parameter(Mandatory)][string]$ExpectedSerial,
    [Parameter(Mandatory)][string]$ExpectedUniqueId,
    [Parameter(Mandatory)][string]$PatchDirectory,
    [Parameter(Mandatory)][string]$ReceiptDirectory,
    [ValidateSet('Inspect', 'Apply', 'Rollback')][string]$Mode = 'Inspect'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$patch = (Resolve-Path -LiteralPath $PatchDirectory).Path
$receipt = [IO.Path]::GetFullPath($ReceiptDirectory)
if (Test-Path -LiteralPath $receipt) { throw 'A new receipt directory is required.' }
$workspaceOut = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\out')) + '\'
if (!$receipt.StartsWith($workspaceOut, [StringComparison]::OrdinalIgnoreCase)) { throw 'Receipt must remain in workspace out.' }
New-Item -ItemType Directory -Path $receipt | Out-Null
$progressPath = Join-Path $receipt 'progress.txt'
$result = [ordered]@{ mode=$Mode; started=(Get-Date -Format o); writes_performed=$false; status='STARTED' }
$raw = $null
$volumeLock = $null
$written = @()

function Note([string]$Message) {
    ((Get-Date -Format o) + ' ' + $Message) | Add-Content -LiteralPath $progressPath
}
function Assert-Disk {
    $selected = Get-Disk -Number $DiskNumber
    if ($selected.Size -ne $ExpectedSize -or $selected.SerialNumber -ne $ExpectedSerial -or
        $selected.UniqueId -ne $ExpectedUniqueId -or $selected.FriendlyName -ne 'Generic MassStorageClass' -or
        $selected.BusType -ne 'USB' -or $selected.IsBoot -or $selected.IsSystem -or
        $selected.IsReadOnly -or $ExpectedSize -lt 32434554368L -or $selected.LogicalSectorSize -ne 512) {
        throw 'Physical disk identity or writeability mismatch.'
    }
    return $selected
}
function Hex([byte[]]$Bytes) { return [BitConverter]::ToString($Bytes).Replace('-', '').ToLowerInvariant() }
function Bytes-Sha([byte[]]$Bytes) {
    $hash = [Security.Cryptography.SHA256]::Create()
    try { return Hex ($hash.ComputeHash($Bytes)) } finally { $hash.Dispose() }
}
function Read-Exact([long]$Offset, [int]$Length) {
    $raw.Position = $Offset
    $bytes = [byte[]]::new($Length)
    $done = 0
    while ($done -lt $Length) {
        $count = $raw.Read($bytes, $done, $Length - $done)
        if (!$count) { throw "Short physical read at $($Offset + $done)." }
        $done += $count
    }
    return ,$bytes
}
function Range-Sha([long]$Offset, [long]$Length) {
    $hash = [Security.Cryptography.IncrementalHash]::CreateHash([Security.Cryptography.HashAlgorithmName]::SHA256)
    $buffer = [byte[]]::new(4MB)
    $raw.Position = $Offset
    [long]$done = 0
    [long]$reported = 0
    try {
        while ($done -lt $Length) {
            $want = [int][Math]::Min([long]$buffer.Length, [long]($Length - $done))
            $count = $raw.Read($buffer, 0, $want)
            if ($count -ne $want) { throw 'Short physical read during full partition hash.' }
            $hash.AppendData($buffer, 0, $count)
            $done += $count
            if ($done - $reported -ge 256MB -or $done -eq $Length) {
                Note "HASH $done / $Length"
                $reported = $done
            }
        }
        return Hex ($hash.GetHashAndReset())
    } finally { $hash.Dispose() }
}

try {
    $manifest = Get-Content -LiteralPath (Join-Path $patch 'recovery-manifest.json') -Raw | ConvertFrom-Json
    if ($manifest.before_system_sha256 -ne '5377190d2b8955c168e100a1e444aedbd1716c57ce7ccd7c545e645c8eaf2af1' -or
        $manifest.system_offset -ne 222298112L -or $manifest.system_bytes -ne 8589934592L -or
        !$manifest.reverse_delta_matches_original -or $manifest.changed_bytes -le 0 -or $manifest.changed_bytes -gt 4MB) {
        throw 'Recovery manifest does not match the verified v5i layout.'
    }
    foreach ($name in @('before','after')) {
        $file = Join-Path $patch ($name + '.bin')
        $expected = $manifest.($name + '_payload_sha256')
        if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) { throw 'Delta payload hash mismatch.' }
    }
    $before = [IO.File]::ReadAllBytes((Join-Path $patch 'before.bin'))
    $after = [IO.File]::ReadAllBytes((Join-Path $patch 'after.bin'))
    if ($before.Length -ne $manifest.changed_bytes -or $after.Length -ne $before.Length) { throw 'Delta length mismatch.' }
    [long]$lastEnd = 0
    [long]$payloadEnd = 0
    foreach ($block in $manifest.blocks) {
        [long]$at = $block.partition_offset
        if ($at -lt $lastEnd -or $at % 4096 -ne 0 -or $block.bytes -ne 4096 -or
            $block.payload_offset -ne $payloadEnd -or $at + $block.bytes -gt $manifest.system_bytes) { throw 'Invalid or overlapping block geometry.' }
        $lastEnd = $at + $block.bytes
        $payloadEnd += $block.bytes
        foreach ($name in @('before','after')) {
            $payload = if ($name -eq 'before') { $before } else { $after }
            $slice = [byte[]]::new(4096)
            [Array]::Copy($payload, [long]$block.payload_offset, $slice, 0L, 4096L)
            if ((Bytes-Sha $slice) -ne $block.($name + '_sha256')) { throw 'Delta block hash mismatch.' }
        }
    }
    if ($payloadEnd -ne $before.Length) { throw 'Incomplete delta geometry.' }
    $disk = Assert-Disk
    if ($disk.IsOffline) { throw 'Disk is already offline; inspect its ownership before continuing.' }
    $parts = @(Get-Partition -DiskNumber $DiskNumber | Sort-Object PartitionNumber)
    $geometry = @(
        @(37748736L,67108864L), @(104857600L,33554432L), @(138412032L,16777216L),
        @(155189248L,67108864L), @(222298112L,8589934592L), @(8812232704L,2147483648L),
        @(10959716352L,17179869184L)
    )
    if ($parts.Count -ne 8) { throw 'Expected eight-partition v5i card.' }
    for ($i=0; $i -lt 7; $i++) {
        if ($parts[$i].PartitionNumber -ne $i+1 -or $parts[$i].Offset -ne $geometry[$i][0] -or
            $parts[$i].Size -ne $geometry[$i][1]) { throw "Partition $($i+1) differs from v5i." }
    }
    if ($parts[7].PartitionNumber -ne 8 -or $parts[7].Offset -ne 28139585536L -or
        $parts[7].Size -lt 4294967296L -or $parts[7].Offset + $parts[7].Size -gt $ExpectedSize) { throw 'Unexpected ROMS partition geometry.' }
    $result.disk = $disk | Select-Object Number,FriendlyName,SerialNumber,UniqueId,Size
    $result.partitions = $parts | Select-Object PartitionNumber,Offset,Size
    Note 'IDENTITY_AND_EIGHT_PARTITIONS_VERIFIED'
    if ($Mode -ne 'Inspect') {
        # Windows cannot offline removable SD media. Lock only the unmounted
        # Android system volume; no other volume or partition is written.
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class H700RecoveryVolumeLock {
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool DeviceIoControl(SafeFileHandle h, uint code,
        IntPtr input, uint inputSize, IntPtr output, uint outputSize,
        out uint returned, IntPtr overlapped);
}
'@
        $paths = @($parts[4].AccessPaths | Where-Object { $_ -like '\\?\Volume{*' })
        if ($paths.Count -ne 1) { throw 'Expected exactly one system volume path.' }
        $volumeLock = [IO.File]::Open($paths[0].TrimEnd('\'), 'Open', 'ReadWrite', 'ReadWrite')
        $returned = [uint32]0
        foreach ($control in @(0x00090018, 0x00090020)) {
            if (![H700RecoveryVolumeLock]::DeviceIoControl($volumeLock.SafeFileHandle, $control,
                [IntPtr]::Zero, 0, [IntPtr]::Zero, 0, [ref]$returned, [IntPtr]::Zero)) {
                throw "System volume lock/dismount failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
            }
        }
        $null = Assert-Disk
        Note 'SYSTEM_VOLUME_EXCLUSIVELY_LOCKED_AND_DISMOUNTED'
    }
    $access = if ($Mode -eq 'Inspect') { [IO.FileAccess]::Read } else { [IO.FileAccess]::ReadWrite }
    $raw = [IO.FileStream]::new("\\.\PhysicalDrive$DiskNumber", [IO.FileMode]::Open, $access, [IO.FileShare]::ReadWrite, 4MB)
    [IO.File]::WriteAllBytes((Join-Path $receipt 'disk-prefix.before.bin'), (Read-Exact 0 32768))
    $result.before_system_sha256 = Range-Sha $manifest.system_offset $manifest.system_bytes
    $expectedSystem = if ($Mode -eq 'Rollback') { $manifest.after_system_sha256 } else { $manifest.before_system_sha256 }
    if ($result.before_system_sha256 -ne $expectedSystem) { throw 'Whole system partition does not match the required image; no patch written.' }
    Note 'FULL_SYSTEM_HASH_VERIFIED'
    if ($Mode -eq 'Inspect') {
        $result.status = 'PASS_READ_ONLY_V5I_CARD_IDENTIFIED'
    } else {
        $oldPayload = if ($Mode -eq 'Rollback') { $after } else { $before }
        $newPayload = if ($Mode -eq 'Rollback') { $before } else { $after }
        [IO.File]::WriteAllBytes((Join-Path $receipt 'changed-blocks.before.bin'), $oldPayload)
        foreach ($block in $manifest.blocks) {
            $actual = Read-Exact ($manifest.system_offset + $block.partition_offset) $block.bytes
            $expectedBlock = if ($Mode -eq 'Rollback') { $block.after_sha256 } else { $block.before_sha256 }
            if ((Bytes-Sha $actual) -ne $expectedBlock) { throw 'Physical block changed after full hash; refusing write.' }
        }
        foreach ($block in $manifest.blocks) {
            $raw.Position = $manifest.system_offset + $block.partition_offset
            # Record before attempting the write so a partial write is also restored.
            $written += $block
            $raw.Write($newPayload, [int]$block.payload_offset, [int]$block.bytes)
            $result.writes_performed = $true
        }
        $raw.Flush($true)
        foreach ($block in $manifest.blocks) {
            $actual = Read-Exact ($manifest.system_offset + $block.partition_offset) $block.bytes
            $expectedBlock = if ($Mode -eq 'Rollback') { $block.before_sha256 } else { $block.after_sha256 }
            if ((Bytes-Sha $actual) -ne $expectedBlock) { throw 'Written block failed readback.' }
        }
        Note 'ALL_CHANGED_BLOCKS_WRITTEN_AND_READ_BACK'
        $result.after_system_sha256 = Range-Sha $manifest.system_offset $manifest.system_bytes
        $expectedAfter = if ($Mode -eq 'Rollback') { $manifest.before_system_sha256 } else { $manifest.after_system_sha256 }
        if ($result.after_system_sha256 -ne $expectedAfter) { throw 'Written full system hash mismatch.' }
        $result.changed_bytes = $manifest.changed_bytes
        $result.status = 'PASS_DELTA_FULL_PARTITION_READBACK_VERIFIED'
        $written = @()
    }
} catch {
    $result.status = 'ERROR'
    $result.error = $_.Exception.Message
    Note ('ERROR ' + $result.error)
    if ($written.Count -gt 0 -and $null -ne $raw) {
        try {
            foreach ($block in $written) {
                $raw.Position = $manifest.system_offset + $block.partition_offset
                $raw.Write($oldPayload, [int]$block.payload_offset, [int]$block.bytes)
            }
            $raw.Flush($true)
            $result.failure_rollback_sha256 = Range-Sha $manifest.system_offset $manifest.system_bytes
            $result.failure_rollback_verified = $result.failure_rollback_sha256 -eq $expectedSystem
            Note ('FAILURE_ROLLBACK_VERIFIED=' + $result.failure_rollback_verified)
        } catch { $result.failure_rollback_error = $_.Exception.Message }
    }
} finally {
    if ($null -ne $raw) { $raw.Dispose() }
    if ($null -ne $volumeLock) { $volumeLock.Dispose() }
    $result.completed = Get-Date -Format o
    $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $receipt 'receipt.json') -Encoding UTF8
    Note ('FINAL ' + $result.status)
}
if ($result.status -eq 'ERROR') { exit 1 }

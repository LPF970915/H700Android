[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Backup', 'Apply', 'Restore')][string]$Mode = 'Plan',
    [Nullable[int]]$DiskNumber,
    [string]$BackupDirectory,
    [ValidateSet('Codec', 'Audio')][string]$Profile = 'Codec'
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'rgsp_vendor_io.ps1')
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$frozenSha = 'cb65140203807d0d80408e314f0c76554f2f81cd13fc76bf8ef07a4e46243c34'
$codecSha = '1e1c90ffdc6fc08e7e40d333d3fab4ea065c19a34df38b4a0889bcc83a8dc891'
$systemSha = '199c03bf5b46a81e26aab133d8310ae576690c99c926b1835d5f3e8ac3115faa'
$linuxSha = 'd42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5'
$candidate = Join-Path $root 'out/rgsp-fix72-codec-candidate-20260908/vendor.raw.img'
$frozen = Join-Path $root 'out/rgsp-fix72-wifi-profile/vendor.raw.img'
$scope = 'fix72-codec-vendor-only-v1'
$label = 'CODEC_VENDOR'
if ($Profile -eq 'Audio') {
    $frozenSha = '1e1c90ffdc6fc08e7e40d333d3fab4ea065c19a34df38b4a0889bcc83a8dc891'
    $codecSha = '9d0c8d4a95b69131a70db6aebdfa1d9b3967afa9dc7dc8e95932872ecb372cc2'
    $candidate = Join-Path $root 'out/rgsp-audio-candidate-20260910/vendor.raw.img'
    $frozen = Join-Path $root 'out/rgsp-fix72-codec-candidate-20260908/vendor.raw.img'
    $scope = 'fix72-audio-vendor-only-v1'
    $label = 'AUDIO_VENDOR'
}
$vendorOffset = 8859418624L
$vendorBytes = 2147483648L
foreach ($entry in @(@($candidate, $codecSha), @($frozen, $frozenSha))) {
    if ((Get-Item -LiteralPath $entry[0]).Length -ne $vendorBytes -or
        (Get-FileHash -LiteralPath $entry[0]).Hash.ToLowerInvariant() -ne $entry[1]) {
        throw 'Pinned local image mismatch.'
    }
}
if ($Mode -eq 'Plan') {
    Write-Host "${label}_PLAN_OK: pinned candidate and rollback images verified."
    Write-Host 'Only TF2 p3 may be written. Backup, Apply and Restore are separate explicit modes.'
    Write-Host 'No device opened, partitions mounted, files created, or reboot requested.'
    return
}
if ($null -eq $DiskNumber -or $DiskNumber -lt 0 -or !$BackupDirectory) {
    throw 'An explicitly discovered DiskNumber and BackupDirectory are required.'
}
$backup = [IO.Path]::GetFullPath($BackupDirectory)
$outRoot = [IO.Path]::GetFullPath((Join-Path $root 'out')) + [IO.Path]::DirectorySeparatorChar
if (!$backup.StartsWith($outRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Backup must stay inside workspace out.'
}
for ($parent = $backup; $parent; $parent = [IO.Path]::GetDirectoryName($parent)) {
    if ((Test-Path -LiteralPath $parent) -and
        ((Get-Item -LiteralPath $parent).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Reparse points are not accepted in the backup path.'
    }
}
if ($Mode -eq 'Backup') {
    if (Test-Path -LiteralPath $backup) { throw 'Use a NEW backup directory.' }
    if ([IO.DriveInfo]::new([IO.Path]::GetPathRoot($backup)).AvailableFreeSpace -lt 5GB) {
        throw 'Insufficient recovery-copy headroom.'
    }
} elseif (!(Test-Path -LiteralPath (Join-Path $backup 'backup.json'))) {
    throw 'Verified fresh backup receipt required.'
}
$disk = Get-Disk -Number $DiskNumber
$parts = @(Get-Partition -DiskNumber $DiskNumber | Sort-Object PartitionNumber)
Assert-RgspVendorDisk $disk $parts
$bootRoot = Get-RgspBootRoot $parts[0]
Assert-RgspBootRecovery $bootRoot $linuxSha
$ranges = @(
    @{ file = 'gpt-head.bin'; offset = 0L; bytes = 1048576L },
    @{ file = 'anboot.img'; offset = 1048576L; bytes = 268435456L },
    @{ file = 'vendor.before.img'; offset = $vendorOffset; bytes = $vendorBytes },
    @{ file = 'gpt-tail.bin'; offset = 125069934080L; bytes = 16896L }
)
$locks = @()
$raw = $null
$image = $null
$recovery = $null
$transcript = $false
try {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class RgspCodecVolumeLock {
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool DeviceIoControl(SafeFileHandle h, uint code,
        IntPtr input, uint inputSize, IntPtr output, uint outputSize,
        out uint returned, IntPtr overlapped);
}
'@
    foreach ($part in $parts[0..2]) {
        $volumes = @($part.AccessPaths | Where-Object { $_ -like '\\?\Volume{*' })
        if ($volumes.Count -ne 1) { throw 'Expected exactly one volume path.' }
        $handle = [IO.File]::Open($volumes[0].TrimEnd('\'), 'Open', 'ReadWrite', 'ReadWrite')
        $locks += $handle
        $returned = [uint32]0
        if (![RgspCodecVolumeLock]::DeviceIoControl($handle.SafeFileHandle, 0x00090018,
            [IntPtr]::Zero, 0, [IntPtr]::Zero, 0, [ref]$returned, [IntPtr]::Zero)) {
            throw "Volume lock failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
        }
    }
    $access = if ($Mode -eq 'Backup') { 'Read' } else { 'ReadWrite' }
    $raw = [IO.File]::Open("\\.\PhysicalDrive$DiskNumber", 'Open', $access, 'ReadWrite')
    Write-Host 'Checking complete live system hash; only read access to system.'
    if ((Get-RgspRangeHash $raw 269484032L 8589934592L) -ne $systemSha) {
        throw 'Live system is not the pinned Fix72 image.'
    }
    $liveVendor = Get-RgspRangeHash $raw $vendorOffset $vendorBytes
    if ($Mode -in @('Backup', 'Apply') -and $liveVendor -ne $frozenSha) {
        throw 'Expected exact frozen vendor before backup/apply.'
    }
    if ($Mode -eq 'Backup') {
        New-Item -ItemType Directory -Path $backup | Out-Null
    }
    Start-Transcript -LiteralPath (Join-Path $backup "$Mode-$(Get-Date -Format yyyyMMdd_HHmmss).log") -NoClobber | Out-Null
    $transcript = $true
    $receiptPath = Join-Path $backup 'backup.json'
    if ($Mode -eq 'Backup') {
        $records = foreach ($range in $ranges) {
            $path = Join-Path $backup $range.file
            $dest = [IO.File]::Open($path, 'CreateNew', 'ReadWrite', 'None')
            try {
                Copy-RgspRange $raw $dest $range.offset 0 $range.bytes
                $actual = Get-RgspRangeHash $dest 0 $range.bytes
                if ((Get-RgspRangeHash $raw $range.offset $range.bytes) -ne $actual) {
                    throw 'Backup readback mismatch.'
                }
            } finally { $dest.Dispose() }
            @{ file = $range.file; offset = $range.offset; bytes = $range.bytes; sha256 = $actual }
        }
        Write-RgspNewJson $receiptPath @{
            scope = $scope; disk_unique_id = $disk.UniqueId
            recorded = (Get-Date).ToString('o'); system_sha256 = $systemSha
            ranges = @($records); device_writes = $false
        }
        Write-Host "${label}_BACKUP_VERIFIED"
        return
    }
    $receipt = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
    if ($receipt.scope -ne $scope -or
        $receipt.disk_unique_id -ne $disk.UniqueId -or $receipt.system_sha256 -ne $systemSha -or
        @($receipt.ranges).Count -ne 4) { throw 'Backup receipt identity mismatch.' }
    foreach ($range in $ranges) {
        $records = @($receipt.ranges | Where-Object file -eq $range.file)
        if ($records.Count -ne 1) { throw 'Missing or duplicate backup range.' }
        $record = $records[0]
        $path = Join-Path $backup $range.file
        if ($record.offset -ne $range.offset -or $record.bytes -ne $range.bytes -or
            (Get-Item -LiteralPath $path).Length -ne $range.bytes -or
            (Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant() -ne $record.sha256) {
            throw 'Backup integrity mismatch.'
        }
        if ($range.file -eq 'vendor.before.img') {
            if ($record.sha256 -ne $frozenSha) { throw 'Rollback image is not frozen Fix72.' }
        } elseif ((Get-RgspRangeHash $raw $range.offset $range.bytes) -ne $record.sha256) {
            throw "Protected range changed since backup: $($range.file)"
        }
    }
    $attempt = Join-Path $backup 'apply-attempt.json'
    $receiptSha = (Get-FileHash -LiteralPath $receiptPath).Hash.ToLowerInvariant()
    if ($Mode -eq 'Apply') {
        if ((Test-Path -LiteralPath $attempt) -or
            (Test-Path -LiteralPath (Join-Path $backup 'Apply-result.json'))) {
            throw 'Apply already attempted. Preserve receipt; use a new backup for retry.'
        }
    } else {
        $prior = Get-Content -LiteralPath $attempt -Raw | ConvertFrom-Json
        if ($prior.receipt_sha256 -ne $receiptSha -or $prior.candidate_sha256 -ne $codecSha) {
            throw 'Restore requires the matching prior Apply attempt.'
        }
        if (Test-Path -LiteralPath (Join-Path $backup 'Restore-result.json')) {
            throw 'Restore already recorded; inspect before retry.'
        }
    }
    $imagePath = if ($Mode -eq 'Apply') { $candidate } else { Join-Path $backup 'vendor.before.img' }
    $expected = if ($Mode -eq 'Apply') { $codecSha } else { $frozenSha }
    $image = [IO.File]::Open($imagePath, 'Open', 'Read', 'Read')
    $recovery = [IO.File]::Open((Join-Path $backup 'vendor.before.img'), 'Open', 'Read', 'Read')
    $freshDisk = Get-Disk -Number $DiskNumber
    Assert-RgspVendorDisk $freshDisk @(Get-Partition -DiskNumber $DiskNumber | Sort-Object PartitionNumber)
    if ($freshDisk.UniqueId -ne $disk.UniqueId) { throw 'Device changed before write.' }
    if ($Mode -eq 'Apply') {
        Write-RgspNewJson $attempt @{
            receipt_sha256 = $receiptSha; candidate_sha256 = $codecSha
            recorded = (Get-Date).ToString('o'); only_write_partition = 3
        }
    }
    Invoke-RgspVendorTransaction $raw $image $recovery $vendorOffset $vendorBytes $expected $frozenSha
    foreach ($record in $receipt.ranges | Where-Object file -ne 'vendor.before.img') {
        if ((Get-RgspRangeHash $raw $record.offset $record.bytes) -ne $record.sha256) {
            throw 'Post-write protected range mismatch. Do not boot.'
        }
    }
    if ((Get-RgspRangeHash $raw 269484032L 8589934592L) -ne $systemSha) {
        throw 'Post-write system hash mismatch. Do not boot.'
    }
    Write-RgspNewJson (Join-Path $backup "$Mode-result.json") @{
        completed = (Get-Date).ToString('o'); partition = 3; vendor_sha256 = $expected
        system_sha256 = $systemSha; protected_boot_ranges_verified = $true
        data_rom_written = $false; data_rom_full_hash_verified = $false
        reboot_requested = $false
    }
    Write-Host "${label}_${Mode}_READBACK_VERIFIED"
} finally {
    if ($image) { $image.Dispose() }
    if ($recovery) { $recovery.Dispose() }
    if ($raw) { $raw.Dispose() }
    foreach ($handle in $locks) { $handle.Dispose() }
    if ($transcript) { Stop-Transcript | Out-Null }
}

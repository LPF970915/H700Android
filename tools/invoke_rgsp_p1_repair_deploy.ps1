[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Apply', 'Restore')][string]$Mode = 'Plan',
    [Parameter(Mandatory = $true)][int]$DiskNumber,
    [Parameter(Mandatory = $true)][string]$Directory,
    [ValidateSet('Legacy', 'Audio')][string]$Profile = 'Legacy'
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'rgsp_vendor_io.ps1')
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$dir = [IO.Path]::GetFullPath($Directory)
$outRoot = [IO.Path]::GetFullPath((Join-Path $root 'out')) + [IO.Path]::DirectorySeparatorChar
if (!$dir.StartsWith($outRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Directory must stay inside workspace out.'
}
for ($parent = $dir; $parent; $parent = [IO.Path]::GetDirectoryName($parent)) {
    if ((Test-Path -LiteralPath $parent) -and
        ((Get-Item -LiteralPath $parent).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Reparse points are not accepted.'
    }
}
$errorLog = Join-Path $dir 'Apply-error.log'
trap {
    $record = "$(Get-Date -Format o) $($_.Exception.GetType().FullName): $($_.Exception.Message)"
    Add-Content -LiteralPath $errorLog -Value $record
    throw
}
$rawImage = Join-Path $dir 'tf2-p1.raw.img'
$fixedImage = Join-Path $dir 'tf2-p1-repaired-copy.img'
$fixedSha = '7f35e0f4a47202dc3495d88dd6e7853b9751eafe386e21b1557d3d4fb568d567'
$rawSha = '1e6844214d7570d66b34485af91362b6b3938a9b8d7947fbdbcb9a635c7939cf'
$p1Offset = 1048576L
$p1Bytes = 268435456L
$systemOffset = 269484032L
$systemBytes = 8589934592L
$systemSha = '199c03bf5b46a81e26aab133d8310ae576690c99c926b1835d5f3e8ac3115faa'
$vendorOffset = 8859418624L
$vendorBytes = 2147483648L
$vendorSha = '1e1c90ffdc6fc08e7e40d333d3fab4ea065c19a34df38b4a0889bcc83a8dc891'
if ($Profile -eq 'Audio') {
    $rawImage = Join-Path $dir 'anboot-before.img'
    $fixedImage = Join-Path $dir 'offline-review/anboot-repaired.img'
    $rawSha = 'ee4b9a7ad5164f2b411f2555b935332dccfda76f321863cf620c31c52a9cc1b6'
    $fixedSha = '721ca44d984263f54f61cdf444d018ff733b4ff97ffd39ec81d791b88d13d887'
    $vendorSha = '9d0c8d4a95b69131a70db6aebdfa1d9b3967afa9dc7dc8e95932872ecb372cc2'
    $capture = Get-Content -LiteralPath (Join-Path $dir 'anboot-backup.json') -Raw | ConvertFrom-Json
    $review = Get-Content -LiteralPath (Join-Path $dir 'offline-review/review.json') -Raw | ConvertFrom-Json
    if ($capture.sha256 -ne $rawSha -or $capture.offset -ne $p1Offset -or $capture.bytes -ne $p1Bytes -or
        $review.source_sha256 -ne $rawSha -or $review.candidate_sha256 -ne $fixedSha -or
        !$review.readonly_fat_check_clean -or !$review.all_file_contents_and_metadata_unchanged -or
        $review.changed_bytes -ne 60 -or ($review.changed_sectors -join ',') -ne '0,1,3030,7063') {
        throw 'Audio p1 capture/review receipt mismatch.'
    }
}
foreach ($item in @(@($rawImage, $rawSha), @($fixedImage, $fixedSha))) {
    if (!(Test-Path -LiteralPath $item[0]) -or
        (Get-Item -LiteralPath $item[0]).Length -ne $p1Bytes -or
        (Get-FileHash -LiteralPath $item[0]).Hash.ToLowerInvariant() -ne $item[1]) {
        throw "Pinned p1 image mismatch: $($item[0])"
    }
}
$disk = Get-Disk -Number $DiskNumber
$parts = @(Get-Partition -DiskNumber $DiskNumber | Sort-Object PartitionNumber)
Assert-RgspVendorDisk $disk $parts
if ($Profile -eq 'Audio' -and ($disk.UniqueId -ne $capture.disk_unique_id -or
    $disk.UniqueId -ne 'USBSTOR\DISK&VEN_GENERIC&PROD_MASSSTORAGECLASS&REV_1539\000000001539&1:DESKTOP-4UKLVM3')) {
    throw 'Fresh p1 capture device identity mismatch.'
}
if ($Mode -eq 'Plan') {
    Write-Host 'P1_REPAIR_PLAN_OK: original and repaired p1 images verified.'
    Write-Host 'Only TF2 p1 may be written; no device was opened.'
    return
}
$backupPath = $rawImage
$attemptPath = Join-Path $dir 'p1-repair-attempt.json'
$resultPath = Join-Path $dir "$Mode-result.json"
if ($Mode -eq 'Apply' -and ((Test-Path -LiteralPath $resultPath) -or
    (Test-Path -LiteralPath $attemptPath))) {
    throw 'Apply result already exists; refusing a second write.'
}
if ($Mode -eq 'Restore') {
    $prior = Get-Content -LiteralPath $attemptPath -Raw | ConvertFrom-Json
    if ($prior.candidate_sha256 -ne $fixedSha -or $prior.recovery_sha256 -ne $rawSha -or
        (Test-Path -LiteralPath $resultPath)) {
        throw 'Restore requires a matching, unrestored Apply attempt.'
    }
}
$raw = $null
$source = $null
$recovery = $null
$volumeLock = $null
try {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class RgspP1VolumeLock {
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool DeviceIoControl(SafeFileHandle h, uint code,
        IntPtr input, uint inputSize, IntPtr output, uint outputSize,
        out uint returned, IntPtr overlapped);
}
'@
    $p1Paths = @($parts[0].AccessPaths | Where-Object { $_ -like '\\?\Volume{*' })
    if ($p1Paths.Count -ne 1) { throw 'Expected exactly one p1 volume path.' }
    $volumeLock = [IO.File]::Open($p1Paths[0].TrimEnd('\'), 'Open', 'ReadWrite', 'ReadWrite')
    $returned = [uint32]0
    if (![RgspP1VolumeLock]::DeviceIoControl($volumeLock.SafeFileHandle, 0x00090018,
        [IntPtr]::Zero, 0, [IntPtr]::Zero, 0, [ref]$returned, [IntPtr]::Zero)) {
        throw "p1 volume lock failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
    }
    $raw = [IO.File]::Open("\\.\PhysicalDrive$DiskNumber", 'Open', 'ReadWrite', 'ReadWrite')
    if ($Mode -eq 'Apply') {
        Assert-RgspRangePreimage $raw $p1Offset $p1Bytes $rawSha
    }
    Write-Host "$(Get-Date -Format o) Checking full protected system and vendor hashes."
    if ((Get-RgspRangeHash $raw $systemOffset $systemBytes) -ne $systemSha) {
        throw 'Live system hash mismatch; no p1 write.'
    }
    if ((Get-RgspRangeHash $raw $vendorOffset $vendorBytes) -ne $vendorSha) {
        throw 'Live vendor hash mismatch; no p1 write.'
    }
    $gpt = Get-RgspRangeHash $raw 0 1048576L
    $tail = Get-RgspRangeHash $raw 125069934080L 16896L
    if ($Profile -eq 'Audio' -and
        ($gpt -ne '0c5ff5e2b488ecd9c4ac193eca4dcb48e81f7f4487c0efde0f5cfe713e4bfad9' -or
         $tail -ne 'fd7ba49795a063054cad97fbf17843fbf2365c4cd72cfa6a8d050cc8dc89f320')) {
        throw 'GPT differs from the verified audio deployment.'
    }
    if ($Mode -eq 'Apply') {
        $source = [IO.File]::Open($fixedImage, 'Open', 'Read', 'Read')
        $expected = $fixedSha
    } else {
        $source = [IO.File]::Open($rawImage, 'Open', 'Read', 'Read')
        $expected = $rawSha
    }
    $recovery = [IO.File]::Open($backupPath, 'Open', 'Read', 'Read')
    $freshDisk = Get-Disk -Number $DiskNumber
    Assert-RgspVendorDisk $freshDisk @(Get-Partition -DiskNumber $DiskNumber | Sort-Object PartitionNumber)
    if ($freshDisk.UniqueId -ne $disk.UniqueId) { throw 'Device changed before p1 write.' }
    if ($Mode -eq 'Apply') {
        Assert-RgspRangePreimage $raw $p1Offset $p1Bytes $rawSha
    }
    # Lock first, then dismount FAT so stale filesystem state cannot be flushed back.
    if (![RgspP1VolumeLock]::DeviceIoControl($volumeLock.SafeFileHandle, 0x00090020,
        [IntPtr]::Zero, 0, [IntPtr]::Zero, 0, [ref]$returned, [IntPtr]::Zero)) {
        throw "p1 dismount failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
    }
    if ($Mode -eq 'Apply') {
        Assert-RgspRangePreimage $raw $p1Offset $p1Bytes $rawSha
    }
    if ($Mode -eq 'Apply') {
        Write-RgspNewJson $attemptPath @{
            mode = 'Apply'; profile = $Profile; disk_number = $DiskNumber; partition = 1
            disk_unique_id = $disk.UniqueId
            candidate_sha256 = $fixedSha; recovery_sha256 = $rawSha
            gpt_head_sha256 = $gpt; gpt_tail_sha256 = $tail
            system_sha256 = $systemSha; vendor_sha256 = $vendorSha
            recorded = (Get-Date).ToString('o')
        }
    }
    Write-Host "$(Get-Date -Format o) Writing only p1 with complete readback and automatic rollback."
    Invoke-RgspVendorTransaction $raw $source $recovery $p1Offset $p1Bytes $expected $rawSha
    Write-Host "$(Get-Date -Format o) P1_READBACK_VERIFIED; checking protected ranges."
    if ((Get-RgspRangeHash $raw 0 1048576L) -ne $gpt -or
        (Get-RgspRangeHash $raw 125069934080L 16896L) -ne $tail -or
        (Get-RgspRangeHash $raw $systemOffset $systemBytes) -ne $systemSha -or
        (Get-RgspRangeHash $raw $vendorOffset $vendorBytes) -ne $vendorSha) {
        throw 'Protected range changed after p1 write; do not boot.'
    }
    $postwritePath = Join-Path $dir "$Mode-p1-readback.img"
    $postwrite = [IO.File]::Open($postwritePath, 'CreateNew', 'ReadWrite', 'None')
    try {
        Copy-RgspRange $raw $postwrite $p1Offset 0 $p1Bytes
        if ((Get-RgspRangeHash $postwrite 0 $p1Bytes) -ne $expected) {
            throw 'Post-write p1 exported readback mismatch.'
        }
    } finally { $postwrite.Dispose() }
    Write-RgspNewJson $resultPath @{
        mode = $Mode; profile = $Profile; partition = 1; p1_sha256 = $expected
        gpt_head_sha256 = $gpt; gpt_tail_sha256 = $tail
        system_sha256 = $systemSha; vendor_sha256 = $vendorSha
        other_partitions_written = $false; reboot_requested = $false
        data_rom_full_hash_verified = $false
        completed = (Get-Date).ToString('o')
    }
    Write-Host "P1_REPAIR_${Mode}_READBACK_VERIFIED"
} finally {
    if ($source) { $source.Dispose() }
    if ($recovery) { $recovery.Dispose() }
    if ($raw) { $raw.Dispose() }
    if ($volumeLock) { $volumeLock.Dispose() }
}

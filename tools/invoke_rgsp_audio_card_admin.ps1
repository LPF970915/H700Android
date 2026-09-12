[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Inspect', 'Backup', 'Apply', 'P1Apply')][string]$Mode,
    [Parameter(Mandatory = $true)][int]$DiskNumber,
    [Parameter(Mandatory = $true)][string]$EvidenceDirectory,
    [string]$BackupDirectory
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'rgsp_vendor_io.ps1')
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$evidence = [IO.Path]::GetFullPath($EvidenceDirectory)
$outRoot = (Join-Path $root 'out') + '\'
if (!$evidence.StartsWith($outRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Evidence directory must be inside workspace out.'
}
for ($parent = $evidence; $parent; $parent = [IO.Path]::GetDirectoryName($parent)) {
    if ((Test-Path -LiteralPath $parent) -and
        ((Get-Item -LiteralPath $parent).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Reparse points are not accepted.'
    }
}
if (!(Test-Path -LiteralPath $evidence)) {
    New-Item -ItemType Directory -Path $evidence | Out-Null
}
$log = Join-Path $evidence "$Mode-admin.log"
$statusPath = Join-Path $evidence "$Mode-status.json"
if ((Test-Path -LiteralPath $log) -or (Test-Path -LiteralPath $statusPath)) {
    throw 'Preserve existing evidence; choose a fresh evidence directory.'
}
$exitCode = 1
$raw = $null
$volume = $null
Start-Transcript -LiteralPath $log -NoClobber | Out-Null
try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    if (!([Security.Principal.WindowsPrincipal]::new($identity)).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Administrator token required.'
    }
    $disk = Get-Disk -Number $DiskNumber
    $parts = @(Get-Partition -DiskNumber $DiskNumber | Sort-Object PartitionNumber)
    Assert-RgspVendorDisk $disk $parts
    if ($disk.UniqueId -ne 'USBSTOR\DISK&VEN_GENERIC&PROD_MASSSTORAGECLASS&REV_1539\000000001539&1:DESKTOP-4UKLVM3') {
        throw 'Discovered reader identity changed.'
    }
    Write-Host "$(Get-Date -Format o) MODE=$Mode DISK=$DiskNumber SIZE=$($disk.Size)"
    if ($Mode -eq 'Inspect') {
        Write-RgspNewJson (Join-Path $evidence 'disk.json') @{
            disk = $disk | Select-Object Number, UniqueId, Size, BusType, PartitionStyle
            partitions = @($parts | Select-Object PartitionNumber, Offset, Size, Guid, AccessPaths)
            volumes = @($parts | Get-Volume -ErrorAction SilentlyContinue |
                Select-Object FileSystemLabel, FileSystemType, HealthStatus, Path)
        }
        $paths = @($parts[0].AccessPaths | Where-Object { $_ -like '\\?\Volume{*' })
        if ($paths.Count -ne 1) { throw 'Expected one ANBOOT volume path.' }
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class RgspAudioInspectLock {
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool DeviceIoControl(SafeFileHandle h, uint code,
        IntPtr input, uint inputSize, IntPtr output, uint outputSize,
        out uint returned, IntPtr overlapped);
}
'@
        $volume = [IO.File]::Open($paths[0].TrimEnd('\'), 'Open', 'ReadWrite', 'ReadWrite')
        $returned = [uint32]0
        if (![RgspAudioInspectLock]::DeviceIoControl($volume.SafeFileHandle, 0x00090018,
            [IntPtr]::Zero, 0, [IntPtr]::Zero, 0, [ref]$returned, [IntPtr]::Zero)) {
            throw "ANBOOT lock failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
        }
        $raw = [IO.File]::Open("\\.\PhysicalDrive$DiskNumber", 'Open', 'Read', 'ReadWrite')
        $path = Join-Path $evidence 'anboot-before.img'
        $dest = [IO.File]::Open($path, 'CreateNew', 'ReadWrite', 'None')
        try {
            Copy-RgspRange $raw $dest 1048576L 0L 268435456L
            $sha = Get-RgspRangeHash $dest 0 268435456L
            if ((Get-RgspRangeHash $raw 1048576L 268435456L) -ne $sha) {
                throw 'ANBOOT backup readback mismatch.'
            }
        } finally { $dest.Dispose() }
        Write-RgspNewJson (Join-Path $evidence 'anboot-backup.json') @{
            disk_unique_id = $disk.UniqueId; offset = 1048576L; bytes = 268435456L
            sha256 = $sha; device_writes = $false; recorded = (Get-Date).ToString('o')
        }
        Write-Host "ANBOOT_READONLY_BACKUP_VERIFIED SHA256=$sha"
    } elseif ($Mode -eq 'P1Apply') {
        & (Join-Path $PSScriptRoot 'invoke_rgsp_p1_repair_deploy.ps1') `
            -Mode Apply -Profile Audio -DiskNumber $DiskNumber -Directory $evidence
        if (!(Test-Path -LiteralPath (Join-Path $evidence 'Apply-result.json'))) {
            throw 'Required p1 completion receipt is missing.'
        }
    } else {
        & (Join-Path $PSScriptRoot 'invoke_rgsp_audio_vendor_deploy.ps1') `
            -Mode $Mode -DiskNumber $DiskNumber -BackupDirectory $BackupDirectory
        $receiptName = if ($Mode -eq 'Backup') { 'backup.json' } else { 'Apply-result.json' }
        if (!(Test-Path -LiteralPath (Join-Path $BackupDirectory $receiptName))) {
            throw 'Required completion receipt is missing.'
        }
    }
    Write-RgspNewJson $statusPath @{ mode = $Mode; success = $true; completed = (Get-Date).ToString('o') }
    $exitCode = 0
} catch {
    Write-Host ($_ | Out-String)
    Write-RgspNewJson $statusPath @{
        mode = $Mode; success = $false; error = ($_ | Out-String)
        completed = (Get-Date).ToString('o')
    }
} finally {
    if ($raw) { $raw.Dispose() }
    if ($volume) { $volume.Dispose() }
    Stop-Transcript | Out-Null
}
exit $exitCode

[CmdletBinding()]
param(
    [switch]$Execute,
    [ValidateSet('All', 'FirstTwo', 'LastTrial')][string]$Set = 'All'
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'rgsp_vendor_io.ps1')
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$out = $root + '\out\'
$files = @(
    'out/tf2-fix72-deploy-20260907-current-v2/data.before.img',
    'out/tf2-fix72-deploy-20260907-current-v2/data.journal-review.img',
    'out/tf2-data-backup-20260909-2359/offline-journal-trial/data.journal-replayed.img'
)
if ($Set -eq 'FirstTwo') { $files = @($files[0..1]) }
if ($Set -eq 'LastTrial') { $files = @($files[2]) }
$records = @()
foreach ($relative in $files) {
    $path = [IO.Path]::GetFullPath((Join-Path $root $relative))
    if (!$path.StartsWith($out, [StringComparison]::OrdinalIgnoreCase)) { throw 'Outside workspace out.' }
    foreach ($target in @($path, "$path.archived-20260910.gz", "$path.archived-20260910.gz.json")) {
        $item = Get-Item -LiteralPath $target
        if ($item.PSIsContainer) { throw 'Only regular files are eligible.' }
        for ($parent = $target; $parent; $parent = [IO.Path]::GetDirectoryName($parent)) {
            if ((Get-Item -LiteralPath $parent).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw 'Reparse path rejected.'
            }
        }
    }
    if (@(& git -C $root ls-files -- $relative).Count) { throw 'Tracked file rejected.' }
    $receipt = Get-Content -LiteralPath "$path.archived-20260910.gz.json" -Raw | ConvertFrom-Json
    if ($receipt.status -ne 'FULL_ARCHIVE_VERIFIED_SOURCE_RETAINED' -or
        $receipt.source -ne $relative -or $receipt.raw_bytes -ne 17179869184L -or
        (Get-Item -LiteralPath $path).Length -ne $receipt.raw_bytes -or
        (Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant() -ne $receipt.raw_sha256 -or
        (Get-Item -LiteralPath "$path.archived-20260910.gz").Length -ne $receipt.archive_bytes -or
        (Get-FileHash -LiteralPath "$path.archived-20260910.gz").Hash.ToLowerInvariant() -ne $receipt.archive_sha256) {
        throw 'Archive/source integrity mismatch; nothing deleted.'
    }
    $records += @{ path = $path; sha256 = $receipt.raw_sha256; archive = "$path.archived-20260910.gz" }
}
Write-Host "SELECTED_${Set}_ARCHIVES_AND_CURRENT_SOURCES_VERIFIED"
if (!$Execute) { return }
$report = Join-Path $out ("cleanup-archived-data-" + (Get-Date -Format yyyyMMdd-HHmmss) + '.json')
$freeBefore = (Get-PSDrive D).Free
$removed = @()
try {
    foreach ($record in $records) {
        # All absolute file paths and retained archives were verified above; no recursive operations.
        Remove-Item -LiteralPath $record.path
        $removed += $record
    }
} finally {
    Write-RgspNewJson $report @{
        removed = $removed; free_before = $freeBefore; free_after = (Get-PSDrive D).Free
        lossless_archives_retained = $true; completed = (Get-Date).ToString('o')
    }
}
Write-Host "CLEANUP_RECEIPT=$report"

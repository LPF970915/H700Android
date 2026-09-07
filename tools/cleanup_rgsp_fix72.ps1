[CmdletBinding()]
param([switch]$Execute)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$out = Join-Path $root 'out'

function Get-SafeFile([string]$RelativePath) {
    $absolute = [IO.Path]::GetFullPath((Join-Path $root $RelativePath))
    if (-not $absolute.StartsWith($out + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Not inside workspace out: $absolute"
    }
    $item = Get-Item -LiteralPath $absolute -Force
    if ($item.PSIsContainer) { throw "Only regular files allowed: $absolute" }
    $cursor = $item
    while ($cursor.FullName -ne $root) {
        if ($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Refusing reparse point: $($cursor.FullName)"
        }
        $cursor = Get-Item -LiteralPath (Split-Path -Parent $cursor.FullName) -Force
    }
    return $item
}

function Test-Artifact([string]$RelativePath, [long]$Bytes, [string]$Hash) {
    $item = Get-SafeFile $RelativePath
    if ($item.Length -ne $Bytes) { throw "Wrong length: $RelativePath" }
    if ((Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash -ne $Hash) {
        throw "Hash mismatch: $RelativePath"
    }
}

$targets = [Collections.Generic.List[string]]::new()
foreach ($directory in @('h700-android10-b2', 'rgsp-fix69-wifi-deployment', 'rgsp-fix72-preflight')) {
    foreach ($name in @('system.raw.img', 'vendor.raw.img')) {
        $targets.Add("out/$directory/$name")
    }
}
# Fix63/Fix67 still require diag3's compressed boot and the fix61 ramdisk.
# These are deliberately not selected, nor is any baseline payload.
Get-ChildItem -LiteralPath (Join-Path $out 'h700-android10-b2') -File |
    Where-Object { $_.Name -match '^h700-android10-b3-diag[1-8](?:-header)?-boot\.img$' } |
    ForEach-Object { $targets.Add("out/h700-android10-b2/$($_.Name)") }
Get-ChildItem -LiteralPath $out -File |
    Where-Object {
        $_.Name -match '^fix(?:4[4-9]|50)_RGSP_ANDROID_.*\.log$' -or
        $_.Name -match '^RGSP_ANDROID_.*_fix(?:[1-9]|[1-4][0-9])_.*\.log$'
    } | ForEach-Object { $targets.Add("out/$($_.Name)") }

$plan = @(
    foreach ($path in $targets | Sort-Object -Unique) {
        if (Test-Path -LiteralPath (Join-Path $root $path)) {
            $item = Get-SafeFile $path
            [pscustomobject]@{path=$path; bytes=$item.Length; modifiedUtc=$item.LastWriteTimeUtc.Ticks}
        }
    }
)
$plan | Format-Table path, bytes -AutoSize
$total = ($plan | Measure-Object bytes -Sum).Sum
Write-Host ("PLANNED_FILES={0}; LOGICAL_GIB={1:N3}; EXECUTE={2}" -f $plan.Count, ($total/1GB), $Execute)
if (-not $Execute) { return }
if (-not $plan.Count) { Write-Host 'Nothing remains to clean'; return }

$tag = & git -C $root rev-parse 'baseline/rgsp-fix72-offline-20260907^{commit}'
if ($LASTEXITCODE -ne 0 -or $tag -ne 'e3566a9cfbf0d86dbb576631497adc6ea5ee94ce') {
    throw 'Frozen baseline tag missing or changed'
}
foreach ($entry in $plan) {
    $tracked = @(& git -C $root ls-files -- $entry.path)
    if ($tracked.Count) { throw "Refusing tracked file: $($entry.path)" }
}

# Verify the candidate, the prior package and actual pre-write recovery images
# before deleting anything. This is local I/O only, never a device operation.
foreach ($directory in @('rgsp-fix72-wifi-profile', 'rgsp-fix70-wifi-deployment')) {
    Write-Host "VERIFY_RETAINED=$directory"
    $manifest = Get-Content -LiteralPath (Join-Path $out "$directory/DEPLOYMENT_MANIFEST.json") -Raw |
        ConvertFrom-Json
    foreach ($artifact in $manifest.artifacts.PSObject.Properties) {
        Test-Artifact "out/$directory/$($artifact.Name)" $artifact.Value.bytes $artifact.Value.sha256
    }
}
Write-Host 'VERIFY_RETAINED=tf2-pre-write-backup'
$backup = Get-Content -LiteralPath (Join-Path $out 'tf2-deploy-20260907/backup.json') -Raw |
    ConvertFrom-Json
foreach ($entry in $backup.ranges) {
    Test-Artifact "out/tf2-deploy-20260907/$($entry.file)" $entry.bytes $entry.sha256
}
$preflight = Get-Content -LiteralPath (Join-Path $out 'rgsp-fix72-preflight/DEPLOYMENT_MANIFEST.json') -Raw |
    ConvertFrom-Json
foreach ($name in @('system.img', 'vendor.img', 'ramdisk.img', 'AT4K-launcher.apk')) {
    $entry = $preflight.artifacts.$name
    Test-Artifact "out/rgsp-fix72-preflight/$name" $entry.bytes $entry.sha256
}
foreach ($line in Get-Content -LiteralPath (Join-Path $root 'docs/baselines/fix67-payload.sha256')) {
    $hash, $name = $line -split '\s+', 2
    $item = Get-SafeFile "out/h700-android10-b2/$name"
    Test-Artifact "out/h700-android10-b2/$name" $item.Length $hash
}

$reportDir = Join-Path $out 'cleanup-fix72-20260907'
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
$reportFile = Join-Path $reportDir ("cleanup-{0}.json" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$report = [ordered]@{
    baseline=$tag; started=(Get-Date).ToString('o'); freeBefore=(Get-PSDrive D).Free
    retainedHashesVerified=$true; planned=$plan; removed=@(); completed=$false
}
try {
    foreach ($entry in $plan) {
        $item = Get-SafeFile $entry.path
        if ($item.Length -ne $entry.bytes -or $item.LastWriteTimeUtc.Ticks -ne $entry.modifiedUtc) {
            throw "File changed since planning: $($entry.path)"
        }
        # The resolved file has been checked against the fixed workspace above.
        Remove-Item -LiteralPath $item.FullName -Force
        $report.removed += $entry.path
    }
    $report.completed = $true
} finally {
    $report.freeAfter = (Get-PSDrive D).Free
    $report.finished = (Get-Date).ToString('o')
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reportFile -Encoding utf8
    Write-Host "CLEANUP_REPORT=$reportFile"
}
Write-Host ("FREED_GIB={0:N3}" -f (($report.freeAfter - $report.freeBefore)/1GB))

param([switch]$Execute)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$targets = [Collections.Generic.List[object]]::new()

function Add-CleanupTarget([string]$Path) {
    if (!(Test-Path -LiteralPath $Path)) { return }
    $resolved = (Resolve-Path -LiteralPath $Path).Path
    if (!$resolved.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Cleanup target is outside the workspace: $resolved"
    }
    $item = Get-Item -LiteralPath $resolved -Force
    if ($item.PSIsContainer) {
        $measure = Get-ChildItem -LiteralPath $resolved -Recurse -File -Force -ErrorAction SilentlyContinue |
            Measure-Object Length -Sum
        $bytes = [double]$measure.Sum
    } else {
        $bytes = [double]$item.Length
    }
    $targets.Add([pscustomobject]@{
        Path = $resolved
        Bytes = $bytes
        Directory = $item.PSIsContainer
    })
}

# H618: retain the selected source/vendor reference and compact official image.
Add-CleanupTarget (Join-Path $root 'work/h700-source-analysis/h618/H618-Android12-Src.tar.gz')
$h618Root = Get-ChildItem -LiteralPath (Join-Path $root 'H700_Android_Example') -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match 'H618' } |
    Select-Object -First 1
if ($h618Root) {
    Get-ChildItem -LiteralPath $h618Root.FullName -Directory -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^H618_Android12' } |
        Get-ChildItem -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^H618-Android12-Src\.tar\.gz[a-z]{2}$' } |
        ForEach-Object { Add-CleanupTarget $_.FullName }
}
Add-CleanupTarget (Join-Path $root 'work/h700-source-analysis/h618/image-extract')
Add-CleanupTarget (Join-Path $root 'work/h700-source-analysis/images/h618-android12/OrangePi_Zero3_Android12_v1.0.img')

# R36S/Android 11: retain one compressed system, final fix32 boot, scripts and logs.
Add-CleanupTarget (Join-Path $root 'work/upstream-r36s')
Add-CleanupTarget (Join-Path $root 'work/rgsp-android11-alpha/upstream-system.img')
Add-CleanupTarget (Join-Path $root 'work/rgsp-android11-alpha/upstream-boot.img')
Add-CleanupTarget (Join-Path $root 'work/rgsp-android11-alpha/verify-boot')
Add-CleanupTarget (Join-Path $root 'work/rgsp-android11-alpha/mnt-system')
Get-ChildItem -LiteralPath (Join-Path $root 'work') -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '^rgsp-android11-fix(2-base|[2-9].*|10-verify)$' } |
    ForEach-Object { Add-CleanupTarget $_.FullName }
Add-CleanupTarget (Join-Path $root 'out/rgsp-android11-alpha/rgsp-android11-system-alpha.img')
Add-CleanupTarget (Join-Path $root 'out/rgsp-android11-system-alpha-fix11.img')
Add-CleanupTarget (Join-Path $root 'out/rgsp-android11-system-alpha-fix11.img.gz')
Get-ChildItem -LiteralPath (Join-Path $root 'out') -File -Filter 'rgsp-android11-handoff-boot-fix*.img' -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -ne 'rgsp-android11-handoff-boot-fix32.img' } |
    ForEach-Object { Add-CleanupTarget $_.FullName }
Get-ChildItem -LiteralPath (Join-Path $root 'out') -File -Filter 'rgsp-android-handoff-ramdisk-fix*.gz' -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -ne 'rgsp-android-handoff-ramdisk-fix32.gz' } |
    ForEach-Object { Add-CleanupTarget $_.FullName }

$total = ($targets | Measure-Object Bytes -Sum).Sum
Write-Output "MODE=$(if ($Execute) { 'execute' } else { 'preview' })"
Write-Output "TARGETS=$($targets.Count)"
Write-Output "RECLAIM_GIB=$([math]::Round($total / 1GB, 2))"
$targets | Sort-Object Bytes -Descending | ForEach-Object {
    Write-Output ("{0,8:N2} GiB  {1}" -f ($_.Bytes / 1GB), $_.Path)
}

if (!$Execute) {
    Write-Output 'No files were removed. Run with -Execute after reviewing the list.'
    exit 0
}

foreach ($target in $targets) {
    if ($target.Directory) {
        Remove-Item -LiteralPath $target.Path -Recurse -Force
    } else {
        Remove-Item -LiteralPath $target.Path -Force
    }
}

Write-Output "REMOVED_GIB=$([math]::Round($total / 1GB, 2))"

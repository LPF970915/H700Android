param(
    [string]$Distro = 'Ubuntu',
    [string]$WslDestination = '~/h700-android10',
    [switch]$Execute,
    [switch]$SkipHash
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$sourceRoot = Get-ChildItem -LiteralPath (Join-Path $root 'H700_Android_Example') -Directory |
    Where-Object { $_.Name -match 'H616' } |
    Select-Object -First 1

if (!$sourceRoot) {
    throw 'Cannot locate the H616 reference directory.'
}

$archive = Get-ChildItem -LiteralPath $sourceRoot.FullName -File -Recurse -Filter 'android.tar.gz' |
    Where-Object { $_.DirectoryName -match 'H616_Android_Source_Code' } |
    Select-Object -First 1
$longanArchive = Get-ChildItem -LiteralPath $sourceRoot.FullName -File -Recurse -Filter 'longan.tar.gz' |
    Where-Object { $_.DirectoryName -match 'H616_Android_Source_Code' } |
    Select-Object -First 1
$overlay = Join-Path $root 'android/h700-android10/device/roc'
$expectedMd5 = 'c5dd785ecd45ca9a2b9c53b1092ee6ec'
$expectedLonganMd5 = '11a2855d8b5c3430e3dd9dff6f40867e'
$expectedPayloadGiB = 45.14

function Convert-ToWslPath([string]$WindowsPath) {
    if ($WindowsPath -notmatch '^([A-Za-z]):\\(.*)$') {
        throw "Unsupported Windows path: $WindowsPath"
    }
    $drive = $Matches[1].ToLowerInvariant()
    $tail = $Matches[2].Replace('\', '/')
    return "/mnt/$drive/$tail"
}

function Convert-ToBashLiteral([string]$Value) {
    if ($Value.Contains("'")) { throw 'Paths containing apostrophes are unsupported.' }
    return "'" + $Value + "'"
}

if (!$archive) { throw 'Cannot locate the H616 android.tar.gz archive.' }
if (!$longanArchive) { throw 'Cannot locate the H616 longan.tar.gz archive.' }
if (!(Test-Path -LiteralPath $overlay -PathType Container)) {
    throw "Cannot locate the H700 Android 10 overlay: $overlay"
}
if ($WslDestination -notmatch '^[A-Za-z0-9_./~-]+$') {
    throw 'WslDestination contains unsupported characters.'
}

$distribution = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss\*' |
    Where-Object { $_.DistributionName -eq $Distro } |
    Select-Object -First 1
if (!$distribution) { throw "WSL distribution '$Distro' is not registered." }
$distributionBase = $distribution.BasePath -replace '^\\\\\?\\', ''
$requiredBase = Join-Path $root '.wsl'
if (!$distributionBase.StartsWith($requiredBase, [StringComparison]::OrdinalIgnoreCase)) {
    throw "WSL distribution '$Distro' is outside the D-drive project: $distributionBase"
}
$hostDrive = Get-PSDrive -Name ([IO.Path]::GetPathRoot($distributionBase).Substring(0, 1))
if ($hostDrive.Free -lt 120GB) {
    throw "At least 120 GiB of host free space is required; available: $([math]::Round($hostDrive.Free / 1GB, 2)) GiB"
}

$archiveWsl = Convert-ToWslPath $archive.FullName
$longanArchiveWsl = Convert-ToWslPath $longanArchive.FullName
$overlayWsl = Convert-ToWslPath $overlay
$helperWsl = Convert-ToWslPath (Join-Path $PSScriptRoot 'prepare_h616_android10_source.sh')
& wsl.exe -d $Distro -- true
if ($LASTEXITCODE -ne 0) { throw "Cannot access WSL distribution '$Distro'." }

$previewCommand = @(
    'bash',
    (Convert-ToBashLiteral $helperWsl),
    'preview',
    (Convert-ToBashLiteral $archiveWsl),
    (Convert-ToBashLiteral $longanArchiveWsl),
    (Convert-ToBashLiteral $overlayWsl),
    (Convert-ToBashLiteral $WslDestination),
    $expectedMd5,
    $expectedLonganMd5,
    'false'
) -join ' '
& wsl.exe -d $Distro -- bash -lc $previewCommand
if ($LASTEXITCODE -ne 0) { throw 'WSL destination inspection failed.' }

Write-Output "MODE=$(if ($Execute) { 'execute' } else { 'preview' })"
Write-Output "EXPECTED_MD5=$expectedMd5"
Write-Output "EXPECTED_LONGAN_MD5=$expectedLonganMd5"
Write-Output "EXPECTED_PAYLOAD_GIB=$expectedPayloadGiB"
Write-Output "WSL_BASE=$distributionBase"
if (!$Execute) {
    Write-Output 'No files were extracted. Re-run with -Execute after reviewing the destination.'
    exit 0
}

$skip = $SkipHash.IsPresent.ToString().ToLowerInvariant()
$executeCommand = @(
    'bash',
    (Convert-ToBashLiteral $helperWsl),
    'execute',
    (Convert-ToBashLiteral $archiveWsl),
    (Convert-ToBashLiteral $longanArchiveWsl),
    (Convert-ToBashLiteral $overlayWsl),
    (Convert-ToBashLiteral $WslDestination),
    $expectedMd5,
    $expectedLonganMd5,
    $skip
) -join ' '
& wsl.exe -d $Distro -- bash -lc $executeCommand
if ($LASTEXITCODE -ne 0) {
    throw "H616 Android 10 source preparation failed with exit code $LASTEXITCODE."
}

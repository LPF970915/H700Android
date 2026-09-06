[CmdletBinding()]
param(
    [string]$Root = '',
    [string]$Distro = 'Ubuntu'
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($Root)) {
    $Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}
$assetDir = Join-Path $Root 'android/h700-android10/device/roc/rgsp/prebuilts/wifi'
$expected = [ordered]@{
    '8821cs.ko' = '59933ce6ca29c88d5c8382e0aa7bf794b1fb42c2595b03f2694901bbfa206a72'
    'rtl8821c_config' = 'dec80607c1bb6cbbcf59e085997bfc32fe6aa3dd3919c95b827778254805a37f'
    'rtl8821c_fw' = '897698b5aa750afa20db1a984bf66ac60dca06e896e32748f9b0cf7f3492fa2a'
}

foreach ($item in $expected.GetEnumerator()) {
    $path = Join-Path $assetDir $item.Key
    if (!(Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing RGSP Wi-Fi asset: $path"
    }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $item.Value) {
        throw "$($item.Key) SHA-256 mismatch: $actual != $($item.Value)"
    }
}

$boardConfig = Get-Content -LiteralPath (Join-Path $Root 'android/h700-android10/device/roc/rgsp/BoardConfig.mk') -Raw
if ($boardConfig -notmatch '(?m)^WIFI_DRIVER_MODULE_PATH\s*:=\s*/vendor/modules/8821cs\.ko\s*$') {
    throw 'BoardConfig.mk does not use the complete 8821cs.ko module path.'
}

$product = Get-Content -LiteralPath (Join-Path $Root 'android/h700-android10/device/roc/rgsp/h700_rgsp.mk') -Raw
foreach ($needle in @(
    'prebuilts/wifi/8821cs.ko:$(TARGET_COPY_OUT_VENDOR)/modules/8821cs.ko',
    'prebuilts/wifi/rtl8821c_config:$(TARGET_COPY_OUT_VENDOR)/firmware/rtlbt/rtl8821c_config',
    'prebuilts/wifi/rtl8821c_fw:$(TARGET_COPY_OUT_VENDOR)/firmware/rtlbt/rtl8821c_fw'
)) {
    if ($product -notlike "*$needle*") {
        throw "h700_rgsp.mk is missing copy rule: $needle"
    }
}

$ueventd = Get-Content -LiteralPath (Join-Path $Root 'android/h700-android10/device/roc/rgsp/ueventd.rgsp.rc') -Raw
if ($ueventd -notmatch '(?m)^firmware_directories\s+/vendor/firmware/') {
    throw 'ueventd.rgsp.rc does not declare /vendor/firmware.'
}

if ($Root -notmatch '^(?<drive>[A-Za-z]):\\(?<tail>.*)$') {
    throw "Root must be a Windows drive path: $Root"
}
$assetWsl = "/mnt/$($Matches.drive.ToLowerInvariant())/$($Matches.tail -replace '\\','/')/android/h700-android10/device/roc/rgsp/prebuilts/wifi/8821cs.ko"
$modinfo = & wsl.exe -d $Distro -- bash -lc "modinfo -F vermagic '$assetWsl' 2>/dev/null"
if ($LASTEXITCODE -ne 0 -or (($modinfo -join "`n").Trim() -ne '4.9.170 SMP preempt mod_unload modversions aarch64')) {
    throw "Unexpected 8821cs.ko vermagic: $($modinfo -join ' ')"
}

Write-Output 'RGSP_WIFI_ASSETS=PASS'
Write-Output "ASSET_DIR=$assetDir"
Write-Output 'MODULE_VERMAGIC=4.9.170 SMP preempt mod_unload modversions aarch64'

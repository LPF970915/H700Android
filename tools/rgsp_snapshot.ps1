<#
.SYNOPSIS
    Capture a comparable RGSP device snapshot (JSON) for before/after reboot checks.

.DESCRIPTION
    Reads the fields that the audit fixes depend on and writes them as JSON so a
    later run can be diffed. Read-only: no settings are changed.

    Usage:
        .\tools\rgsp_snapshot.ps1                       # baseline, timestamped file
        .\tools\rgsp_snapshot.ps1 -Out .\out\snap.json  # explicit path
        .\tools\rgsp_snapshot.ps1 -Diff .\out\before.json

.NOTES
    ASCII-only: Windows PowerShell 5.1 reads BOM-less scripts as ANSI.
#>
[CmdletBinding()]
param(
    [string]$Target = '192.168.31.161:5555',
    [string]$Out,
    [string]$Diff
)

$ErrorActionPreference = 'Continue'
$repo = Split-Path -Parent $PSScriptRoot
if (-not $Out) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $Out = Join-Path $repo "out\settings-deep-audit-20261023\snapshot-$stamp.json"
}

$probe = @'
echo serial=$(getprop ro.serialno)
echo fingerprint=$(getprop ro.build.fingerprint)
echo uptime_s=$(cut -d. -f1 /proc/uptime)
echo boot_id=$(cat /proc/sys/kernel/random/boot_id)
echo ipv4=$(ip -4 addr show wlan0 | grep 'inet ' | awk '{print $2}')
echo adb_tcp_port=$(getprop service.adb.tcp.port)
echo persistent_adb_port=$(getprop persist.adb.tcp.port)
echo adbd_binary=$(sha256sum /system/bin/adbd | awk '{print $1}')
echo adbd=$(getprop init.svc.adbd)
echo adb_enabled=$(settings get global adb_enabled)
echo show_ime=$(settings get secure show_ime_with_hard_keyboard)
echo dev_settings=$(settings get global development_settings_enabled)
echo bluetooth_on=$(settings get global bluetooth_on)
echo nav_version=$(dumpsys activity service com.roc.rgsp.navtrial/.NavigationService | grep navigationVersion | sed 's/.*navigationVersion=\([0-9]*\).*/\1/')
echo usb_service=$(service check usb)
echo usb_state=$(getprop sys.usb.state)
echo usb_config=$(getprop sys.usb.config)
echo usb_ffs_ready=$(getprop sys.usb.ffs.ready)
echo oem_lock_service=$(service check oem_lock)
echo encrypt_progress=$(getprop vold.encrypt_progress)
echo data_dev=$(mount | grep ' /data ' | awk '{print $1}')
echo systemui=$(sha256sum /system/product/priv-app/SystemUI/SystemUI.apk | awk '{print $1}')
echo services_jar=$(sha256sum /system/framework/services.jar | awk '{print $1}')
echo usb_feature=$(sha256sum /vendor/etc/permissions/android.hardware.usb.host.xml | awk '{print $1}')
echo settings_apk=$(sha256sum $(pm path com.android.settings | sed 's/^package://') | awk '{print $1}')
echo nav_apk=$(sha256sum $(pm path com.roc.rgsp.navtrial | sed 's/^package://') | awk '{print $1}')
echo media_apk=$(sha256sum $(pm path com.android.providers.media | sed 's/^package://') | awk '{print $1}')
echo overlay=$(cmd overlay list | grep rgsp)
echo ipv4_adb_guard=$(iptables -S INPUT | grep -- '--dport 5555')
echo ipv6_adb_guard=$(ip6tables -S INPUT | grep -- '--dport 5555')
'@

$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($probe))
$raw = & (Join-Path $PSScriptRoot 'rgsp_adb.ps1') -Target $Target shell "echo $b64 | base64 -d | sh" 2>&1
if ($LASTEXITCODE -ne 0) { throw "snapshot probe failed (exit $LASTEXITCODE)" }

$data = [ordered]@{
    captured_at = (Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz')
    target      = $Target
}
foreach ($line in $raw) {
    $text = ($line -as [string]).TrimEnd("`r")
    if ($text -match '^([a-z0-9_]+)=(.*)$') {
        $key = $Matches[1]
        $value = $Matches[2].Trim()
        if ($key -eq 'usb_service') { $value = ($value -replace '^Service usb:\s*', '') }
        if ($key -eq 'oem_lock_service') { $value = ($value -replace '^Service oem_lock:\s*', '') }
        $data[$key] = $value
    }
}

if ($data.serial -ne '5c001089d750c872012') { throw 'Snapshot device identity mismatch' }
foreach ($field in @('systemui', 'services_jar', 'usb_feature', 'settings_apk', 'nav_apk', 'media_apk', 'adbd_binary')) {
    if ($data[$field] -notmatch '^[a-f0-9]{64}$') { throw "Incomplete snapshot: $field" }
}
$json = $data | ConvertTo-Json -Depth 3
[IO.File]::WriteAllText($Out, $json + "`n", (New-Object Text.UTF8Encoding($false)))
Write-Host "SNAPSHOT $Out"

if ($Diff) {
    if (-not (Test-Path -LiteralPath $Diff)) { throw "diff baseline not found: $Diff" }
    $before = Get-Content -LiteralPath $Diff -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Host "`n--- diff vs $Diff ---"
    foreach ($name in $data.Keys) {
        if ($name -in @('captured_at', 'target')) { continue }
        $old = $before.$name
        $new = $data[$name]
        if ("$old" -ne "$new") {
            Write-Host ("CHANGED  {0}: {1} -> {2}" -f $name, $old, $new)
        }
    }
    Write-Host '--- end diff (unchanged fields omitted) ---'
}

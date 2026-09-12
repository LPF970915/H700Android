[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-z0-9-]{1,60}$')][string]$Step,
    [int[]]$KeyCodes = @(),
    [ValidateRange(1, 60)][int]$WaitSeconds = 1,
    [Parameter(Mandatory = $true)][string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$output = [IO.Path]::GetFullPath($OutputDirectory)
$allowedRoot = [IO.Path]::GetFullPath((Join-Path $root 'out')) + [IO.Path]::DirectorySeparatorChar
if (-not $output.StartsWith($allowedRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Evidence must remain in workspace out.'
}
foreach ($key in $KeyCodes) {
    if ($key -notin @(19, 20, 21, 22, 66, 97, 100)) {
        throw 'Only DPAD directions, ENTER (A mapping), BUTTON_B and BUTTON_Y are allowed; injection is not a physical-button test.'
    }
}
New-Item -ItemType Directory -Force -Path $output | Out-Null
if (Test-Path -LiteralPath (Join-Path $output "$Step.json")) {
    throw 'Use a new evidence step name.'
}
$remote = "/data/local/tmp/rgsp-dpad-$Step"
$commands = @(
    'set -eu'
    'test "$(getprop ro.product.device)" = rgsp'
    'test "$(getprop sys.boot_completed)" = 1'
    'test "$(cat /sys/block/mmcblk0/device/cid)" = 1d414455534400002000009f9401a1e7'
    'test "$(cat /sys/block/mmcblk1/device/cid)" = fe3432534400000020000005bc01896b'
)
foreach ($key in $KeyCodes) {
    $commands += "input keyevent $key"
    $commands += 'sleep 0.3'
}
$commands += @(
    "sleep $WaitSeconds"
    "screencap -p $remote.png"
    "uiautomator dump $remote.xml"
    "cat $remote.xml"
    "sha256sum $remote.png $remote.xml"
    'dumpsys window | grep -E "mCurrentFocus|mFocusedApp"'
)
$stepLog = Join-Path $output "$Step-serial"
$intent = [ordered]@{
    step = $Step
    recorded = (Get-Date -Format o)
    keys = @($KeyCodes)
    control = 'Android input keyevent; no tap/swipe, am start, pm install or permission grants'
    physical_buttons_verified = $false
    status = 'STEP_INTENT'
}
$intent | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $output "$Step.json") -Encoding utf8
& ([Environment]::ProcessPath) -NoProfile -File (Join-Path $PSScriptRoot 'invoke_rgsp_serial_command.ps1') `
    -ShellPath /system/bin/sh -Command ($commands -join "`n") -TimeoutSeconds 100 `
    -OutputDirectory ([IO.Path]::GetRelativePath($root, $stepLog)) -Quiet
if ($LASTEXITCODE -ne 0) { throw "Step failed; retained intent and serial evidence: $Step" }
& ([Environment]::ProcessPath) -NoProfile -File (Join-Path $PSScriptRoot 'download_rgsp_file_serial.ps1') `
    -RemotePath "$remote.png" -LocalPath (Join-Path $output "$Step.png") -TimeoutSeconds 90
if ($LASTEXITCODE -ne 0) { throw 'Screenshot download failed.' }
$logs = @(Get-ChildItem -LiteralPath $stepLog -Filter '*.log')
if ($logs.Count -ne 1) { throw 'Expected exactly one step transcript.' }
$text = [IO.File]::ReadAllText($logs[0].FullName)
$xmlMatch = [regex]::Match($text, '<\?xml.*?</hierarchy>', [Text.RegularExpressions.RegexOptions]::Singleline)
if (-not $xmlMatch.Success) { throw 'UI XML missing from transcript.' }
[xml]$xml = $xmlMatch.Value
$xml.Save((Join-Path $output "$Step.xml"))
$intent.status = 'STEP_AND_SCREENSHOT_CAPTURED'
$intent['screenshot_sha256'] = (Get-FileHash -LiteralPath (Join-Path $output "$Step.png") -Algorithm SHA256).Hash.ToLowerInvariant()
$intent | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $output "$Step-result.json") -Encoding utf8
$xml.SelectNodes('//node') | Where-Object {
    $_.focused -eq 'true' -or $_.clickable -eq 'true' -or $_.text
} | Select-Object text, content-desc, resource-id, focused, enabled, bounds | Format-Table -Wrap
Write-Host "SCREENSHOT=$(Join-Path $output "$Step.png")"

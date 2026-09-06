param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9_-]{1,40}$')]
    [string]$Step,
    [ValidateRange(5, 60)][int]$Seconds = 20,
    [string]$Port = 'COM4'
)
$ErrorActionPreference = 'Stop'
$token = Get-Date -Format 'yyyyMMdd_HHmmss'
$remote = "/rgsp-persist/input-calibration-${token}-${Step}.log"
# Capture all evdev devices so duplicated auxiliary-key events remain visible.
# This only observes events; it does not grab or remap the hardware.
$command = "echo 'STEP=$Step'; getevent -lp > '$remote'; echo 'RAW_EVENTS' >> '$remote'; timeout $Seconds getevent -t >> '$remote' 2>&1; rc=`$?; test `"`$rc`" = 124 -o `"`$rc`" = 0"
Write-Host "Capturing '$Step' for $Seconds seconds. Press and release only the requested physical key."
& (Join-Path $PSScriptRoot 'invoke_rgsp_serial_command.ps1') -Port $Port `
    -ShellPath /system/bin/sh -Command $command -TimeoutSeconds ($Seconds + 12) -Quiet
if ($LASTEXITCODE -ne 0) { throw 'Remote calibration capture failed.' }
& (Join-Path $PSScriptRoot 'download_rgsp_file_serial.ps1') -Port $Port `
    -RemotePath $remote -LocalPath "out/input-calibration/${token}-${Step}.log"
if ($LASTEXITCODE -ne 0) { throw 'Calibration download failed.' }

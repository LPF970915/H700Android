<#
.SYNOPSIS
    One-shot ADB wrapper for the RGSP device: ensure server + TCP connection, then run.

.DESCRIPTION
    In this environment the adb server is torn down together with the command's
    process tree, so every call starts from "daemon not running". Splitting
    start-server / connect / run across separate calls loses the device mid-run
    (the 2026-10-23 20:25 category scan died exactly that way).

    This script does all three in one invocation and waits for the device state.

.PARAMETER Target
    adb target, default 192.168.31.161:5555 (current Wi-Fi ADB endpoint).

.PARAMETER Mode
    shell / exec-out / push / pull / install / uninstall / logcat / status

.PARAMETER Rest
    Remaining arguments passed to adb. shell/exec-out join them into one command.

.EXAMPLE
    .\tools\rgsp_adb.ps1 shell 'id; getprop ro.serialno; ip -4 addr show wlan0'

.EXAMPLE
    .\tools\rgsp_adb.ps1 push .\out\x.apk /data/local/tmp/x.apk

.EXAMPLE
    .\tools\rgsp_adb.ps1 status

.NOTES
    Keep this file ASCII-only: Windows PowerShell 5.1 reads BOM-less scripts as ANSI.
    If the device is not reachable, check `getprop service.adb.tcp.port` and
    `getprop init.svc.adbd` over the serial console.
#>
[CmdletBinding()]
param(
    [string]$Target = '192.168.31.161:5555',
    [string]$Adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe",
    [int]$WaitSeconds = 10,
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('shell', 'exec-out', 'push', 'pull', 'install', 'uninstall', 'logcat', 'status')]
    [string]$Mode,
    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

# Windows PowerShell turns native stderr into NativeCommandError when the
# preference is Stop, so keep Continue and check exit codes explicitly.
$ErrorActionPreference = 'Continue'

if (-not (Test-Path -LiteralPath $Adb)) { throw "adb not found: $Adb" }

$null = & $Adb start-server 2>&1
$connect = (& $Adb connect $Target 2>&1 | Out-String).Trim()
if ($connect -notmatch 'connected to') { Write-Warning "adb connect: $connect" }

$deadline = (Get-Date).AddSeconds($WaitSeconds)
$state = ''
do {
    $state = (& $Adb -s $Target get-state 2>$null | Out-String).Trim()
    if ($state -eq 'device') { break }
    Start-Sleep -Milliseconds 300
} while ((Get-Date) -lt $deadline)

if ($state -ne 'device') {
    throw "Device $Target not ready (state=$state). Check service.adb.tcp.port / init.svc.adbd over serial."
}

switch ($Mode) {
    'status' {
        & $Adb devices -l
        & $Adb -s $Target shell 'getprop ro.serialno; getprop ro.build.fingerprint; ip -4 addr show wlan0 | grep inet'
        exit $LASTEXITCODE
    }
    'shell' {
        $cmd = ($Rest -join ' ')
        if ([string]::IsNullOrWhiteSpace($cmd)) { throw 'shell mode needs a command' }
        & $Adb -s $Target shell $cmd
        exit $LASTEXITCODE
    }
    'exec-out' {
        $cmd = ($Rest -join ' ')
        if ([string]::IsNullOrWhiteSpace($cmd)) { throw 'exec-out mode needs a command' }
        & $Adb -s $Target exec-out $cmd
        exit $LASTEXITCODE
    }
    'push' {
        if ($Rest.Count -lt 2) { throw 'push needs <local> <remote>' }
        & $Adb -s $Target push $Rest[0] $Rest[1]
        exit $LASTEXITCODE
    }
    'pull' {
        if ($Rest.Count -lt 2) { throw 'pull needs <remote> <local>' }
        & $Adb -s $Target pull $Rest[0] $Rest[1]
        exit $LASTEXITCODE
    }
    'install' {
        if ($Rest.Count -lt 1) { throw 'install needs <apk>' }
        & $Adb -s $Target install --no-incremental -r @Rest
        exit $LASTEXITCODE
    }
    'uninstall' {
        if ($Rest.Count -lt 1) { throw 'uninstall needs <package>' }
        & $Adb -s $Target uninstall @Rest
        exit $LASTEXITCODE
    }
    'logcat' {
        & $Adb -s $Target logcat @Rest
        exit $LASTEXITCODE
    }
}

[CmdletBinding()]
param(
    [string]$Distro = 'Ubuntu',
    [string]$SourceRoot = '/home/lpf/h700-android10/android',
[ValidateSet('systemimage', 'vendorimage', 'ramdisk', 'Settings', 'LeanbackIME', 'DocumentsUI', 'RGSPLauncher')]
    [string[]]$Targets = @('systemimage', 'vendorimage', 'ramdisk'),
    [switch]$Execute
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if ($SourceRoot -notmatch '^/home/lpf/[a-zA-Z0-9/_-]+$') { throw 'Unexpected Android source path' }
$os = Get-CimInstance Win32_OperatingSystem
if ($os.FreePhysicalMemory -lt 6GB / 1KB) { throw 'Need at least 6 GiB free host RAM' }
if ((Get-PSDrive D).Free -lt 40GB) { throw 'Need at least 40 GiB free on D:' }
$unit = 'h700-low-pressure-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
$linuxRoot = '/mnt/' + $root.Substring(0,1).ToLowerInvariant() + ($root.Substring(2) -replace '\\','/')
$argsList = @(
    '-d', $Distro, '-u', 'root', '--',
    'systemd-run', "--unit=$unit", '--wait', '--pipe', '--collect',
    '--service-type=exec', '--uid=lpf',
    '--property=CPUQuota=100%', '--property=AllowedCPUs=0-1',
    '--property=MemoryHigh=5G', '--property=MemoryMax=6G',
    '--property=MemorySwapMax=512M', '--property=OOMPolicy=stop',
    '--property=Nice=19', '--property=IOSchedulingClass=idle',
    # Old Soong/Go can exceed 512 OS threads while enumerating the source tree.
    # Keep the CPU and memory quotas; permit its I/O-blocked worker threads.
    '--property=TasksMax=2048', '--property=RuntimeMaxSec=3h',
    '--property=KillMode=control-group',
    '/usr/bin/taskset', '-c', '0,1', '/bin/bash',
    "$linuxRoot/tools/build_h700_low_pressure.sh", $SourceRoot
) + $Targets
Write-Host "BUILD_UNIT=$unit"
Write-Host 'LIMITS: CPU 0-1; aggregate 1 core; -j1; RAM 6 GiB; swap 512 MiB; nice 19; idle I/O'
if (-not $Execute) {
    Write-Host 'DRY_RUN: pass -Execute to build; no build started'
    return
}
$logDir = Join-Path $root 'out/logs/build'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir "$unit.log"
& wsl.exe @argsList 2>&1 | Tee-Object -FilePath $log
$rc = $LASTEXITCODE
Write-Host "BUILD_LOG=$log"
if ($rc -ne 0) { throw "Low-pressure build stopped (exit $rc); resource limits were not relaxed" }

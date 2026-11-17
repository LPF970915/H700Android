[CmdletBinding()]
param(
    [ValidateSet('package','verify')][string]$Phase = 'package',
    [Parameter(Mandatory=$true)][string]$Preparation,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$PreparationSha256,
    [string]$Work = '/home/lpf/roc-os-h700-manual-selector-test6-20261115-v1',
    [string]$Output = '/mnt/d/Works/H700Android/out/roc-os-h700-manual-selector-test6-20261115',
    [switch]$Execute,
    [string]$Distro = 'Ubuntu'
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$os = Get-CimInstance Win32_OperatingSystem
if ($os.FreePhysicalMemory -lt 6GB / 1KB) { throw 'Need at least 6 GiB free host RAM' }
if ((Get-PSDrive D).Free -lt 40GB) { throw 'Need at least 40 GiB free on D:' }
$linuxRepo = '/mnt/' + $repo.Substring(0,1).ToLowerInvariant() + $repo.Substring(2).Replace([char]92,[char]47)
$unit = 'roc-h700-navigation-test6-' + $Phase + '-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
$scriptName = if ($Phase -eq 'verify') { 'verify_h700_navigation_test6.py' } else { 'package_h700_navigation_test6.py' }
$scriptArgs = @("$linuxRepo/tools/release/$scriptName",'--work',$Work,'--output',$Output,
                '--preparation',$Preparation,'--preparation-sha256',$PreparationSha256)
Write-Host "PACKAGE_UNIT=$unit"
Write-Host 'LIMITS: aggregate 1 CPU; CPUs 0-1; nice 19; RAM 6 GiB; swap 512 MiB; idle IO; 3 h'
if (-not $Execute) { Write-Host 'DRY_RUN: pass -Execute to operate on ordinary image files'; return }
$arguments = @('-d',$Distro,'-u','root','--','systemd-run',"--unit=$unit",'--wait','--pipe','--collect',
    '--service-type=exec','--uid=lpf','--property=CPUQuota=100%','--property=AllowedCPUs=0-1',
    '--property=MemoryHigh=5G','--property=MemoryMax=6G','--property=MemorySwapMax=512M',
    '--property=Nice=19','--property=IOSchedulingClass=idle','--property=RuntimeMaxSec=3h',
    '--property=KillMode=control-group','--property=OOMPolicy=stop','--property=TasksMax=2048',
    '/usr/bin/taskset','-c','0,1','/usr/bin/flock','-n','/tmp/h700-android10-low-pressure.lock',
    '/usr/bin/python3','-B') + $scriptArgs
$logDir = Join-Path $repo 'out/roc-os-h700-navigation-test6-20261115-logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
& wsl.exe @arguments 2>&1 | Tee-Object -FilePath (Join-Path $logDir "$unit.log")
if ($LASTEXITCODE -ne 0) { throw 'Test6 phase failed; preserve outputs and logs' }

[CmdletBinding()]
param(
    [ValidateSet('prepare','package','verify')][string]$Phase = 'prepare',
    [string]$Manifest,
    [string]$Work = '/home/lpf/roc-os-h700-stick-adc-control-test11-20261117-v1',
    [string]$Output = '/mnt/d/Works/H700Android/out/roc-os-h700-stick-adc-control-test11-20261117',
    [switch]$Execute,
    [string]$Distro = 'Ubuntu'
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
if ($Phase -eq 'prepare' -and -not $Manifest) { throw 'Prepare requires the frozen candidate input manifest' }
$linuxRepo = '/mnt/' + $repo.Substring(0,1).ToLowerInvariant() + $repo.Substring(2).Replace([char]92,[char]47)
$unit = 'roc-h700-stick-adc-control-test11-' + $Phase + '-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
$scriptName = if ($Phase -eq 'verify') { 'verify.py' } else { 'package.py' }
$scriptArgs = @()
if ($Phase -ne 'verify') { $scriptArgs += $Phase }
$scriptArgs += @('--work',$Work,'--output',$Output)
if ($Phase -eq 'prepare') { $scriptArgs += @('--manifest',$Manifest) }
Write-Host "PACKAGE_UNIT=$unit"
Write-Host 'LIMITS: one CPU; CPUs 0-1; nice19; RAM high5/max6GiB; swap512MiB; idleIO; globalflock; 3h'
if (-not $Execute) { Write-Host 'DRY_RUN: ordinary image files only; no jobs started'; return }
$os = Get-CimInstance Win32_OperatingSystem
if ($os.FreePhysicalMemory -lt 6GB / 1KB) { throw 'Need at least6GiB free hostRAM' }
if ((Get-PSDrive D).Free -lt 40GB) { throw 'Need at least40GiB free onD:' }
$arguments = @('-d',$Distro,'-u','root','--','systemd-run',"--unit=$unit",'--wait','--pipe','--collect',
    '--service-type=exec','--uid=lpf','--property=CPUQuota=100%','--property=AllowedCPUs=0-1',
    '--property=MemoryHigh=5G','--property=MemoryMax=6G','--property=MemorySwapMax=512M',
    '--property=Nice=19','--property=IOSchedulingClass=idle','--property=RuntimeMaxSec=3h',
    '--property=KillMode=control-group','--property=OOMPolicy=stop','--property=TasksMax=2048',
    '/usr/bin/taskset','-c','0,1','/usr/bin/flock','-n','/tmp/h700-android10-low-pressure.lock',
    '/usr/bin/python3','-B',"$linuxRepo/tools/input_profiles/stick_recovery_package_v2/$scriptName") + $scriptArgs
$logDir = Join-Path $repo 'out/roc-os-h700-stick-adc-control-test11-20261117-logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
& wsl.exe @arguments 2>&1 | Tee-Object -FilePath (Join-Path $logDir "$unit.log")
if ($LASTEXITCODE -ne 0) { throw 'Test11 phase failed; preserve its outputs and logs' }

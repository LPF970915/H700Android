[CmdletBinding()]
param([switch]$Execute, [switch]$VerifyOnly, [string]$Distro = 'Ubuntu')
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$os = Get-CimInstance Win32_OperatingSystem
if ($os.FreePhysicalMemory -lt 6GB / 1KB) { throw 'Need at least 6 GiB free host RAM' }
if ((Get-PSDrive D).Free -lt 40GB) { throw 'Need at least 40 GiB free on D:' }
$linuxRepo = '/mnt/' + $repo.Substring(0,1).ToLowerInvariant() + $repo.Substring(2).Replace([char]92,[char]47)
$unit = 'roc-user-rc4-card-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
$taskScript = 'package_rc4.py'
if ($VerifyOnly) { $taskScript = 'verify_rc4_card.py' }
Write-Host "PACKAGE_UNIT=$unit"
Write-Host 'LIMITS: aggregate 1 CPU; CPUs 0-1; nice19; RAM6GiB; swap512MiB; idle IO; 3h'
if (-not $Execute) { Write-Host 'DRY_RUN: pass -Execute to assemble ordinary files only'; return }
$arguments = @('-d',$Distro,'-u','root','--','systemd-run',"--unit=$unit",'--wait','--pipe','--collect',
    '--service-type=exec','--uid=lpf','--property=CPUQuota=100%','--property=AllowedCPUs=0-1',
    '--property=MemoryHigh=5G','--property=MemoryMax=6G','--property=MemorySwapMax=512M',
    '--property=Nice=19','--property=IOSchedulingClass=idle','--property=RuntimeMaxSec=3h',
    '--property=KillMode=control-group','--property=OOMPolicy=stop','--property=TasksMax=2048',
    '/usr/bin/taskset','-c','0,1','/usr/bin/flock','-n','/tmp/h700-android10-low-pressure.lock',
    '/usr/bin/python3',"$linuxRepo/tools/release/$taskScript")
$logDir = Join-Path $repo 'out/roc-os-user-card-rc4-20261107/logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
& wsl.exe @arguments 2>&1 | Tee-Object -FilePath (Join-Path $logDir "$unit.log")
if ($LASTEXITCODE -ne 0) { throw 'Candidate assembly failed; preserve log and partial files' }

[CmdletBinding()]
param([switch]$Execute)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$os = Get-CimInstance Win32_OperatingSystem
if ($os.FreePhysicalMemory -lt 6GB / 1KB) { throw 'Need at least 6 GiB free host RAM' }
if ((Get-PSDrive D).Free -lt 40GB) { throw 'Need at least 40 GiB free on D:' }
$unit = 'roc-navigation-test6-build-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
Write-Host "BUILD_UNIT=$unit"
Write-Host 'LIMITS: aggregate1CPU; CPUs0-1; nice19; RAM6GiB; swap512MiB; idleIO;3h'
if (-not $Execute) { Write-Host 'DRY_RUN'; return }
$arguments = @('-d','Ubuntu','-u','root','--','systemd-run',"--unit=$unit",'--wait','--pipe','--collect',
  '--service-type=exec','--property=CPUQuota=100%','--property=AllowedCPUs=0-1',
  '--property=MemoryHigh=5G','--property=MemoryMax=6G','--property=MemorySwapMax=512M',
  '--property=Nice=19','--property=IOSchedulingClass=idle','--property=RuntimeMaxSec=3h',
  '--property=KillMode=control-group','--property=OOMPolicy=stop','--property=TasksMax=2048',
  '/usr/bin/taskset','-c','0,1','/usr/bin/unshare','--mount','--propagation','private',
  '/bin/bash','/mnt/d/Works/H700Android/tools/release/navigation_test6_namespace.sh')
$logs = Join-Path $repo 'out/nav-test6-production-20261115-logs'
New-Item -ItemType Directory -Path $logs -Force | Out-Null
& wsl.exe @arguments 2>&1 | Tee-Object -FilePath (Join-Path $logs "$unit.log")
if ($LASTEXITCODE -ne 0) { throw 'Test6 production build failed; outputs and logs retained' }

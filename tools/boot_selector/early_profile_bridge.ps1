[CmdletBinding()]
param(
    [string]$Work = '/home/lpf/roc-h700-early-selector-20261114-v1',
    [string]$Output = '/mnt/d/Works/H700Android/out/boot-selector-integration-20261114/early-hook-v1',
    [switch]$Execute
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$unit = 'roc-h700-early-selector-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
Write-Host "EARLY_HOOK_UNIT=$unit"
if (-not $Execute) { Write-Host 'DRY_RUN'; return }
$arguments = @('-d','Ubuntu','-u','root','--','systemd-run',"--unit=$unit",'--wait','--pipe','--collect',
    '--service-type=exec','--uid=lpf','--property=CPUQuota=100%','--property=AllowedCPUs=0-1',
    '--property=MemoryHigh=5G','--property=MemoryMax=6G','--property=MemorySwapMax=512M',
    '--property=Nice=19','--property=IOSchedulingClass=idle','--property=RuntimeMaxSec=3h',
    '--property=KillMode=control-group','--property=OOMPolicy=stop','--property=TasksMax=2048',
    '/usr/bin/taskset','-c','0,1','/usr/bin/flock','-n','/tmp/h700-android10-low-pressure.lock',
    '/home/lpf/roc-h700-panel-tables-20261114-v2/venv/bin/python',
    '/mnt/d/Works/H700Android/tools/boot_selector/early_profile_bridge.py','--work',$Work,'--output',$Output)
$logs = Join-Path $repo 'out/boot-selector-integration-20261114/early-hook-logs'
New-Item -ItemType Directory -Path $logs -Force | Out-Null
& wsl.exe @arguments 2>&1 | Tee-Object -FilePath (Join-Path $logs "$unit.log")
if ($LASTEXITCODE -ne 0) { throw 'Early hook build failed; preserve attempt and logs' }

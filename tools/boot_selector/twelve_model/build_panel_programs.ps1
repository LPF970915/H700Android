[CmdletBinding()]
param(
    [string]$Work = '/home/lpf/roc-h700-twelve-panel-programs-20261116-v1',
    [string]$Output = '/mnt/d/Works/H700Android/out/twelve-model-panel-programs-20261116-v1',
    [switch]$Execute
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$unit = 'roc-h700-twelve-panels-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
Write-Host "PANEL_COMPONENT_UNIT=$unit"
Write-Host 'Ordinary components only; one CPU, 6 GiB, 512 MiB swap, idle IO, global lock'
if (-not $Execute) { Write-Host 'DRY_RUN'; return }
$arguments = @('-d','Ubuntu','-u','root','--','systemd-run',"--unit=$unit",'--wait','--pipe','--collect',
    '--service-type=exec','--uid=lpf','--property=CPUQuota=100%','--property=AllowedCPUs=0-1',
    '--property=MemoryHigh=5G','--property=MemoryMax=6G','--property=MemorySwapMax=512M',
    '--property=Nice=19','--property=IOSchedulingClass=idle','--property=RuntimeMaxSec=3h',
    '--property=KillMode=control-group','--property=OOMPolicy=stop','--property=TasksMax=2048',
    '/usr/bin/taskset','-c','0,1','/usr/bin/flock','-w','180','/tmp/h700-android10-low-pressure.lock',
    '/home/lpf/roc-h700-panel-tables-20261114-v2/venv/bin/python',
    '/mnt/d/Works/H700Android/tools/boot_selector/twelve_model/build_panel_programs.py','--work',$Work,'--output',$Output)
$logs = Join-Path $repo 'out/twelve-model-panel-programs-20261116-logs'
New-Item -ItemType Directory -Path $logs -Force | Out-Null
& wsl.exe @arguments 2>&1 | Tee-Object -FilePath (Join-Path $logs "$unit.log")
if ($LASTEXITCODE -ne 0) { throw 'Panel component attempt failed; preserve work and logs' }

[CmdletBinding()]
param(
    [string]$Work = '/home/lpf/roc-boot-state-20261114-v1',
    [string]$Output = '/mnt/d/Works/H700Android/out/boot-selector-integration-20261114/boot-state-v1',
    [string]$Distro = 'Ubuntu',
    [switch]$Execute
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$linuxRepo = '/mnt/' + $repo.Substring(0,1).ToLowerInvariant() + $repo.Substring(2).Replace([char]92,[char]47)
$unit = 'roc-boot-state-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
Write-Host "BOOT_STATE_UNIT=$unit"
Write-Host 'FIXTURE TEST ONLY: no device, mounted partition, reboot or card operation'
if (-not $Execute) { Write-Host 'DRY_RUN'; return }
$arguments = @('-d',$Distro,'-u','root','--','systemd-run',"--unit=$unit",'--wait','--pipe','--collect',
    '--service-type=exec','--uid=lpf','--property=CPUQuota=100%','--property=AllowedCPUs=0-1',
    '--property=MemoryHigh=5G','--property=MemoryMax=6G','--property=MemorySwapMax=512M',
    '--property=Nice=19','--property=IOSchedulingClass=idle','--property=RuntimeMaxSec=3h',
    '--property=KillMode=control-group','--property=OOMPolicy=stop','--property=TasksMax=2048',
    '/usr/bin/taskset','-c','0,1','/usr/bin/flock','-w','180','/tmp/h700-android10-low-pressure.lock',
    '/usr/bin/python3',"$linuxRepo/tools/boot_selector/native/build_boot_state.py",'--work',$Work,'--output',$Output)
$logDir = Join-Path $repo 'out/boot-selector-integration-20261114/native/logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
& wsl.exe @arguments 2>&1 | Tee-Object -FilePath (Join-Path $logDir "$unit.log")
if ($LASTEXITCODE -ne 0) { throw 'Boot state helper build/test failed; preserve work and logs' }

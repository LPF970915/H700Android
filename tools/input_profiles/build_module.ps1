[CmdletBinding()]
param(
    [string]$Work = '/home/lpf/roc-os-h700-input-profiles-20261116-v1',
    [string]$Output = '/mnt/d/Works/H700Android/out/test7-rg35xxh-sticks-20261116/module-build-v1',
    [switch]$Execute,
    [string]$Distro = 'Ubuntu'
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$linuxRepo = '/mnt/' + $repo.Substring(0,1).ToLowerInvariant() + $repo.Substring(2).Replace([char]92,[char]47)
if (-not $Execute) {
    & wsl.exe -d $Distro -u root --exec /usr/bin/python3 -B "$linuxRepo/tools/input_profiles/build_module.py" --work $Work --output $Output
    if ($LASTEXITCODE -ne 0) { throw 'Input module build plan failed' }
    return
}
$os = Get-CimInstance Win32_OperatingSystem
if ($os.FreePhysicalMemory -lt 6GB / 1KB) { throw 'Need at least 6 GiB free host RAM' }
if ((Get-PSDrive D).Free -lt 40GB) { throw 'Need at least 40 GiB free on D:' }
$unit = 'roc-h700-input-profiles-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
Write-Host "INPUT_MODULE_UNIT=$unit"
Write-Host 'LIMITS: one CPU; CPUs 0-1; nice 19; RAM 6 GiB; swap 512 MiB; idle IO; 3 h; global flock'
$logDir = Join-Path $repo 'out/test7-rg35xxh-sticks-20261116/module-build-logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$arguments = @('-d',$Distro,'-u','root','--','systemd-run',"--unit=$unit",'--wait','--pipe','--collect',
    '--service-type=exec','--property=CPUQuota=100%','--property=AllowedCPUs=0-1',
    '--property=MemoryHigh=5G','--property=MemoryMax=6G','--property=MemorySwapMax=512M',
    '--property=Nice=19','--property=IOSchedulingClass=idle','--property=RuntimeMaxSec=3h',
    '--property=KillMode=control-group','--property=OOMPolicy=stop','--property=TasksMax=2048',
    '/usr/bin/taskset','-c','0,1','/usr/bin/flock','-n','/tmp/h700-android10-low-pressure.lock',
    '/usr/bin/unshare','--mount','--propagation','private','/bin/bash',
    "$linuxRepo/tools/input_profiles/readonly_build.sh",$linuxRepo,$Work,$Output)
& wsl.exe @arguments 2>&1 | Tee-Object -FilePath (Join-Path $logDir "$unit.log")
if ($LASTEXITCODE -ne 0) { throw 'Input module build failed; preserve outputs and logs' }

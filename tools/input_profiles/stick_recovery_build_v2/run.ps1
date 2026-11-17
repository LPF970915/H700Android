[CmdletBinding()]
param(
    [ValidateSet('host','module','integration','record')][string]$Phase = 'module',
    [switch]$Execute
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$linuxRepo = '/mnt/' + $repo.Substring(0,1).ToLowerInvariant() + $repo.Substring(2).Replace([char]92,[char]47)
if (-not $Execute) { Write-Host "Plan: isolated ADC-control $Phase; no device writes."; return }
$os = Get-CimInstance Win32_OperatingSystem
if ($os.FreePhysicalMemory -lt 6GB / 1KB) { throw 'Need at least 6 GiB free host RAM' }
if ((Get-PSDrive D).Free -lt 8GB) { throw 'Need at least 8 GiB free on D:' }
$unit = 'roc-h700-stick-adc-control-' + $Phase + '-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
$logDir = Join-Path $repo 'out/stick-adc-control-repair-20261117-v1/build-logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
Write-Host "MODULE_UNIT=$unit"
$arguments = @('-d','Ubuntu','-u','root','--','systemd-run',"--unit=$unit",'--wait','--pipe','--collect',
    '--service-type=exec','--property=CPUQuota=100%','--property=AllowedCPUs=0-1',
    '--property=MemoryHigh=5G','--property=MemoryMax=6G','--property=MemorySwapMax=512M',
    '--property=Nice=19','--property=IOSchedulingClass=idle','--property=RuntimeMaxSec=3h',
    '--property=KillMode=control-group','--property=OOMPolicy=stop','--property=TasksMax=2048',
    '/usr/bin/taskset','-c','0,1','/usr/bin/flock','-n','/tmp/h700-android10-low-pressure.lock')
if ($Phase -eq 'module') {
    $arguments += @('/usr/bin/unshare','--mount','--propagation','private','/bin/bash',
        "$linuxRepo/tools/input_profiles/stick_recovery_build_v2/readonly_build.sh",$linuxRepo)
} else {
    $scriptPath = switch ($Phase) {
        'host' { "$linuxRepo/tools/input_profiles/stick_recovery_v4/run_host.py" }
        'integration' { "$linuxRepo/tools/input_profiles/stick_recovery_build_v2/prepare_loaders.py" }
        'record' { "$linuxRepo/tools/input_profiles/stick_recovery_build_v2/record.py" }
    }
    $arguments += @('/usr/sbin/runuser','-u','lpf','--','/usr/bin/python3','-B',$scriptPath)
    if ($Phase -eq 'host') { $arguments += @('--output',"$linuxRepo/out/stick-adc-control-repair-20261117-v1/host-final") }
}
& wsl.exe @arguments 2>&1 | Tee-Object -FilePath (Join-Path $logDir "$unit.log")
if ($LASTEXITCODE -ne 0) { throw "ADC-control $Phase failed; retain outputs and logs" }

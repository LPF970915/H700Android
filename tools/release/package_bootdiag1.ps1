[CmdletBinding()]
param([switch]$Execute,[string]$Distro='Ubuntu')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
if ((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory -lt 6GB/1KB) {throw 'Need 6GiB free host RAM'}
$unit='roc-user-bootdiag1-'+(Get-Date -Format 'yyyyMMdd-HHmmss')
Write-Host "BOOTDIAG_UNIT=$unit"
Write-Host 'LIMITS: aggregate1CPU; CPUs0-1; nice19; RAM6GiB; swap512MiB; idleIO; 3h'
if (-not $Execute) {Write-Host 'DRY_RUN: ordinary files only; pass -Execute';return}
$linuxRepo='/mnt/'+$repo.Substring(0,1).ToLowerInvariant()+$repo.Substring(2).Replace([char]92,[char]47)
$argsLinux=@('-d',$Distro,'-u','root','--','systemd-run',"--unit=$unit",'--wait','--pipe','--collect','--service-type=exec','--uid=lpf',
    '--property=CPUQuota=100%','--property=AllowedCPUs=0-1','--property=MemoryHigh=5G','--property=MemoryMax=6G','--property=MemorySwapMax=512M',
    '--property=Nice=19','--property=IOSchedulingClass=idle','--property=RuntimeMaxSec=3h','--property=KillMode=control-group','--property=OOMPolicy=stop',
    '/usr/bin/taskset','-c','0,1','/usr/bin/flock','-n','/tmp/h700-android10-low-pressure.lock','/usr/bin/python3',"$linuxRepo/tools/release/package_bootdiag1.py")
$logDir=Join-Path $repo 'out/roc-os-user-rc1-firstboot-20261105'
& wsl.exe @argsLinux 2>&1 | Tee-Object -FilePath (Join-Path $logDir "$unit.log")
if ($LASTEXITCODE -ne 0) {throw 'BootDiag packaging failed; preserve partial output and log'}

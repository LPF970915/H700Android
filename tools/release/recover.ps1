[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('inspect','backup','restore')][string]$Action,
    [Parameter(Mandatory)][string]$Image,
    [string]$Bundle,
    [switch]$Execute,
    [string]$Distro = 'Ubuntu'
)
$ErrorActionPreference = 'Stop'
if ($Execute -and $Action -ne 'restore') { throw '-Execute is restore-only' }
if ($Action -ne 'inspect' -and -not $Bundle) { throw '-Bundle required' }
function Convert-RecoveryPath([string]$value) {
    $full = [IO.Path]::GetFullPath($value)
    if ($full -notmatch '^[A-Za-z]:\\') { throw 'Only local drive paths are supported' }
    return '/mnt/' + $full.Substring(0,1).ToLowerInvariant() + ($full.Substring(2) -replace '\\','/')
}
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$script = Convert-RecoveryPath (Join-Path $PSScriptRoot 'recovery.py')
$imagePath = Convert-RecoveryPath $Image
$unit = 'roc-recovery-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + ([Guid]::NewGuid().ToString('N').Substring(0,8))
$arguments = @('-d',$Distro,'-u','root','--','systemd-run',"--unit=$unit",'--wait','--pipe','--collect',
    '--service-type=exec','--uid=lpf','--property=CPUQuota=100%','--property=AllowedCPUs=0-1',
    '--property=MemoryHigh=5G','--property=MemoryMax=6G','--property=MemorySwapMax=512M',
    '--property=Nice=19','--property=IOSchedulingClass=idle','--property=RuntimeMaxSec=3h',
    '--property=KillMode=control-group','--property=OOMPolicy=stop',
    '/usr/bin/taskset','-c','0,1','/usr/bin/flock','-n','/tmp/h700-android10-low-pressure.lock',
    '/usr/bin/python3',$script,$Action,$imagePath)
if ($Bundle) { $arguments += @('--bundle',(Convert-RecoveryPath $Bundle)) }
if ($Execute) { $arguments += '--execute' }
$logDir = Join-Path $repo 'out/source64-release-prep-20261104/recovery-logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
& wsl.exe @arguments 2>&1 | Tee-Object -FilePath (Join-Path $logDir "$unit.log")
if ($LASTEXITCODE -ne 0) { throw 'Offline recovery command failed; preserve log and partial files' }

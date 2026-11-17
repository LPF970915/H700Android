[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('production-audit','prepare','final-audit','finalize')][string]$Phase,
    [ValidatePattern('^$|^[0-9a-f]{64}$')][string]$ProofSha256 = '',
    [ValidatePattern('^v[1-9][0-9]*$')][string]$IntegrationRevision = 'v2',
    [switch]$Execute
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$os = Get-CimInstance Win32_OperatingSystem
if ($os.FreePhysicalMemory -lt 6GB / 1KB) { throw 'Need at least 6 GiB free host RAM' }
if ((Get-PSDrive D).Free -lt 40GB) { throw 'Need at least 40 GiB free on D:' }
$linuxRepo = '/mnt/' + $repo.Substring(0,1).ToLowerInvariant() + $repo.Substring(2).Replace([char]92,[char]47)
$build = '/home/lpf/roc-os-navigation-test6-build-20261115-v1'
$delivery = "$linuxRepo/out/nav-test6-production-20261115"
$work = "/home/lpf/roc-os-navigation-test6-integration-20261115-$IntegrationRevision"
$output = "$linuxRepo/out/nav-test6-integration-20261115-$IntegrationRevision"
switch ($Phase) {
    'production-audit' { $stageArgs = @("$linuxRepo/tools/release/audit_navigation_test6_art.py",
        '--system-tree',"$build/after/system",'--receipt',"$delivery/production-art.json") }
    'final-audit' { $stageArgs = @("$linuxRepo/tools/release/audit_navigation_test6_art.py",
        '--system-tree',"$work/final-tree/system",'--receipt',"$output/final-art.json",
        '--production-audit',"$delivery/production-art.json") }
    default {
        if ($ProofSha256 -eq '') { throw 'An exact completed audit SHA is required' }
        $auditPath = if ($Phase -eq 'prepare') { "$delivery/production-art.json" } else { "$output/final-art.json" }
        $stageArgs = @("$linuxRepo/tools/release/prepare_navigation_test6.py",$Phase,
            '--art-audit',$auditPath,'--art-audit-sha256',$ProofSha256,
            '--work',$work,'--output',$output)
    }
}
$unit = 'roc-navigation-test6-' + $Phase + '-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
Write-Host "STAGE_UNIT=$unit"
Write-Host 'LIMITS: aggregate1CPU; CPUs0-1; nice19; RAM6GiB; swap512MiB; idleIO;3h'
if (-not $Execute) { Write-Host 'DRY_RUN'; return }
$arguments = @('-d','Ubuntu','-u','root','--','systemd-run',"--unit=$unit",'--wait','--pipe','--collect',
    '--service-type=exec','--uid=lpf','--property=CPUQuota=100%','--property=AllowedCPUs=0-1',
    '--property=MemoryHigh=5G','--property=MemoryMax=6G','--property=MemorySwapMax=512M',
    '--property=Nice=19','--property=IOSchedulingClass=idle','--property=RuntimeMaxSec=3h',
    '--property=KillMode=control-group','--property=OOMPolicy=stop','--property=TasksMax=2048',
    '/usr/bin/taskset','-c','0,1','/usr/bin/flock','-n','/tmp/h700-android10-low-pressure.lock',
    '/usr/bin/python3','-B') + $stageArgs
$logs = Join-Path $repo 'out/nav-test6-stage-20261115-logs'
New-Item -ItemType Directory -Path $logs -Force | Out-Null
& wsl.exe @arguments 2>&1 | Tee-Object -FilePath (Join-Path $logs "$unit.log")
if ($LASTEXITCODE -ne 0) { throw 'Test6 stage failed; preserve outputs and logs' }

[CmdletBinding()]
param(
    [ValidateSet('prepare','handoff','package','verify')][string]$Phase = 'prepare',
    [string]$Manifest,
    [string]$Work = '/home/lpf/roc-os-h700-twelve-model-test8-20261116-v1',
    [string]$Output = '/mnt/d/Works/H700Android/out/roc-os-h700-twelve-model-test8-20261116',
    [switch]$Execute,
    [string]$Distro = 'Ubuntu'
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
if ($Phase -eq 'prepare' -and -not $Manifest) { throw 'Prepare requires an explicit frozen input manifest' }
$os = Get-CimInstance Win32_OperatingSystem
if ($os.FreePhysicalMemory -lt 6GB / 1KB) { throw 'Need at least 6 GiB free host RAM' }
if ((Get-PSDrive D).Free -lt 40GB) { throw 'Need at least 40 GiB free on D:' }
$linuxRepo = '/mnt/' + $repo.Substring(0,1).ToLowerInvariant() + $repo.Substring(2).Replace([char]92,[char]47)
$unit = 'roc-h700-twelve-model-test8-' + $Phase + '-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
$scriptName = if ($Phase -eq 'verify') { 'verify_h700_twelve_model.py' } else { 'package_h700_twelve_model.py' }
$pythonRuntime = '/usr/bin/python3'
$scriptPath = "$linuxRepo/tools/release/$scriptName"
$scriptArgs = @()
if ($Phase -ne 'verify') { $scriptArgs += $Phase }
$scriptArgs += @('--work',$Work,'--output',$Output)
if ($Phase -eq 'prepare') { $scriptArgs += @('--manifest',$Manifest) }
if ($Phase -eq 'handoff') {
    $scriptPath = "$linuxRepo/tools/boot_selector/twelve_model/verify_final_handoff.py"
    $pythonRuntime = '/home/lpf/roc-h700-panel-tables-20261114-v2/venv/bin/python'
    $scriptArgs = @('--prefix',"$Work/prefix.raw",'--output',"$Output/final-handoff-proof")
    if ($Execute) {
        $preparationLines = & wsl.exe -d $Distro -- cat "$Output/preparation.json"
        if ($LASTEXITCODE -ne 0) { throw 'Read the passed preparation before final handoff proof' }
        $preparation = ($preparationLines -join "`n") | ConvertFrom-Json
        if ($preparation.passed -ne $true -or $preparation.prefix_sha256 -notmatch '^[0-9a-f]{64}$') {
            throw 'A passed preparation with an exact prefix hash is required'
        }
        $scriptArgs += @('--prefix-sha256',$preparation.prefix_sha256)
    }
}
Write-Host "PACKAGE_UNIT=$unit"
Write-Host 'LIMITS: 1 CPU; CPUs 0-1; nice 19; RAM high 5 GiB/max 6 GiB; swap 512 MiB; idle IO; global flock; 3 h'
if (-not $Execute) { Write-Host 'DRY_RUN: pass -Execute for ordinary image files'; return }
$arguments = @('-d',$Distro,'-u','root','--','systemd-run',"--unit=$unit",'--wait','--pipe','--collect',
    '--service-type=exec','--uid=lpf','--property=CPUQuota=100%','--property=AllowedCPUs=0-1',
    '--property=MemoryHigh=5G','--property=MemoryMax=6G','--property=MemorySwapMax=512M',
    '--property=Nice=19','--property=IOSchedulingClass=idle','--property=RuntimeMaxSec=3h',
    '--property=KillMode=control-group','--property=OOMPolicy=stop','--property=TasksMax=2048',
    '/usr/bin/taskset','-c','0,1','/usr/bin/flock','-n','/tmp/h700-android10-low-pressure.lock',
    $pythonRuntime,'-B',$scriptPath) + $scriptArgs
$logDir = Join-Path $repo 'out/roc-os-h700-twelve-model-test8-20261116-logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
& wsl.exe @arguments 2>&1 | Tee-Object -FilePath (Join-Path $logDir "$unit.log")
if ($LASTEXITCODE -ne 0) { throw 'Test8 phase failed; preserve all outputs and logs' }
if ($Phase -eq 'handoff') {
    Write-Host 'FINAL_HANDOFF_PROOF_COMPLETE: bind the exact final-handoff-proof/result.json bytes as final-handoff.json before package'
}

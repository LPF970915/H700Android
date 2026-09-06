param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Start', 'Finish')][string]$Action,
    [ValidatePattern('^[A-Za-z0-9_-]{1,40}$')][string]$Step,
    [ValidatePattern('^COM[1-9][0-9]*$')][string]$Port = 'COM4'
)
$ErrorActionPreference = 'Stop'
$directory = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../out/input-calibration'))
New-Item -ItemType Directory -Force -Path $directory | Out-Null
$statePath = Join-Path $directory "active-$Port.json"
$invoke = Join-Path $PSScriptRoot 'invoke_rgsp_serial_command.ps1'

if ($Action -eq 'Start') {
    if (-not $Step) { throw 'Start requires a physical calibration step name.' }
    if (Test-Path -LiteralPath $statePath) {
        throw "A session is already recorded at $statePath. Finish it before starting another."
    }
    $token = Get-Date -Format 'yyyyMMdd_HHmmss'
    $remote = "/rgsp-persist/input-calibration-${token}-${Step}.log"
    $remotePid = "/data/local/tmp/rgsp-input-${token}.pid"
    $state = [ordered]@{
        version = 1
        port = $Port
        step = $Step
        remote = $remote
        remotePid = $remotePid
        local = Join-Path $directory "${token}-${Step}.log"
        status = 'starting'
        startedAt = (Get-Date).ToString('o')
    }
    # Keep recovery metadata even if UART acknowledgement is lost after arming.
    [IO.File]::WriteAllText($statePath, ($state | ConvertTo-Json), [Text.Encoding]::UTF8)
    $command = "set -e; printf 'STEP=%s\n' '$Step' > '$remote'; getevent -lp >> '$remote'; echo RAW_EVENTS >> '$remote'; nohup /system/bin/sh -c 'ulimit -f 512; exec getevent -t' </dev/null >> '$remote' 2>&1 & child=`$!; echo `$child > '$remotePid'; sleep 1; kill -0 `$child; echo INPUT_SESSION_ARMED; cat '$remotePid'"
    & ([Environment]::ProcessPath) -NoProfile -File $invoke -Port $Port `
        -ShellPath /system/bin/sh -Command $command -TimeoutSeconds 15 -Quiet
    if ($LASTEXITCODE -ne 0) {
        throw "Arming was not acknowledged; retain $statePath and inspect/finish the session."
    }
    $state.status = 'recording'
    [IO.File]::WriteAllText($statePath, ($state | ConvertTo-Json), [Text.Encoding]::UTF8)
    Write-Host "SESSION_ARMED: $Step. Recording until Finish, subject to a file-size safety limit."
    Write-Host "STATE: $statePath"
    return
}

if (-not (Test-Path -LiteralPath $statePath)) { throw 'No active session is recorded.' }
$state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
if ($state.version -ne 1 -or $state.port -ne $Port -or
    $state.remote -notmatch '^/rgsp-persist/input-calibration-[0-9_]+-[A-Za-z0-9_-]+\.log$' -or
    $state.remotePid -notmatch '^/data/local/tmp/rgsp-input-[0-9_]+\.pid$') {
    throw 'Invalid session metadata.'
}
if ($Step -and $Step -ne $state.step) { throw 'Requested step does not match the active session.' }
$target = [IO.Path]::GetFullPath($state.local)
if ((Split-Path -Parent $target) -ne $directory) { throw 'Session output is outside the calibration directory.' }
$remote = $state.remote
$remotePid = $state.remotePid
# Validate the process's output file before signaling, so a reused PID cannot
# cause an unrelated process to be stopped. Already-exited captures can be read.
$command = "set -e; child=`$(cat '$remotePid'); case `"`$child`" in ''|*[!0-9]*) exit 2;; esac; if kill -0 `$child 2>/dev/null; then test `"`$(readlink /proc/`$child/fd/1)`" = '$remote'; kill -TERM `$child; sleep 1; if kill -0 `$child 2>/dev/null; then echo CAPTURE_STILL_RUNNING; exit 3; fi; fi; sync; echo INPUT_SESSION_STOPPED; wc -c '$remote'"
& ([Environment]::ProcessPath) -NoProfile -File $invoke -Port $Port `
    -ShellPath /system/bin/sh -Command $command -TimeoutSeconds 15 -Quiet
if ($LASTEXITCODE -ne 0) { throw 'Stop was not verified; session metadata was retained.' }
& (Join-Path $PSScriptRoot 'download_rgsp_file_serial.ps1') -Port $Port `
    -RemotePath $remote -LocalPath $target
if ($LASTEXITCODE -ne 0) { throw 'Download failed; session metadata was retained for retry.' }
Remove-Item -LiteralPath $statePath
Write-Host "SESSION_FINISHED: $target"

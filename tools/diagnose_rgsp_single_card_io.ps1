#requires -RunAsAdministrator
[CmdletBinding()]
param(
    [switch]$ConfirmWrite,
    [switch]$Worker,
    [string]$RunDirectory
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$candidate = Join-Path $root 'out/rgsp-single-card-v2-20260911'
if (!$Worker) {
    $RunDirectory = Join-Path $candidate ("io-diag-" + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
    [void][IO.Directory]::CreateDirectory($RunDirectory)
    $argsLine = '-NoLogo -NoProfile -File "{0}" -Worker -RunDirectory "{1}"' -f $PSCommandPath, $RunDirectory
    if ($ConfirmWrite) { $argsLine += ' -ConfirmWrite' }
    $child = Start-Process -FilePath (Get-Process -Id $PID).Path `
        -ArgumentList $argsLine -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $RunDirectory 'stdout.log') `
        -RedirectStandardError (Join-Path $RunDirectory 'stderr.log')
    $child.PriorityClass = 'BelowNormal'
    if (!$child.WaitForExit(120000)) {
        $child.Kill()
        $child.WaitForExit()
        [IO.File]::WriteAllText((Join-Path $RunDirectory 'exit.txt'), 'TIMEOUT_KILLED_NOT_VERIFIED')
        exit 2
    }
    [IO.File]::WriteAllText((Join-Path $RunDirectory 'exit.txt'), [string]$child.ExitCode)
    exit $child.ExitCode
}
if (!(Test-Path -LiteralPath $RunDirectory -PathType Container)) { throw 'Missing run directory.' }
$log = Join-Path $RunDirectory 'stages.log'
function Log([string]$Message) {
    [IO.File]::AppendAllText($log, ((Get-Date -Format o) + " PID=$PID $Message`r`n"))
}
function Read-Exact([IO.Stream]$Stream, [byte[]]$Bytes) {
    $done = 0
    while ($done -lt $Bytes.Length) {
        $n = $Stream.Read($Bytes, $done, [Math]::Min(65536, $Bytes.Length - $done))
        if ($n -le 0) { throw 'Unexpected EOF.' }
        $done += $n
    }
}
function Hash([byte[]]$Bytes) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash($Bytes)).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
}
$mutex = $null
$held = $false
$raw = $null
$source = $null
try {
    Log 'START'
    $mutex = [Threading.Mutex]::new($false, 'Global\RGSP_000000001539_62239277056_IO')
    try { $held = $mutex.WaitOne(0) }
    catch [Threading.AbandonedMutexException] { $held = $true }
    if (!$held) { throw 'Another target-card IO operation is active.' }
    $targets = @(Get-Disk | Where-Object {
        $_.BusType -eq 'USB' -and $_.SerialNumber.Trim() -eq '000000001539' -and
        $_.Size -eq 62239277056L -and !$_.IsBoot -and !$_.IsSystem -and !$_.IsReadOnly
    })
    if ($targets.Count -ne 1) { throw 'Expected exactly one matching 64G USB target.' }
    $disk = $targets[0]
    $parts = @(Get-Partition -DiskNumber $disk.Number | Sort-Object PartitionNumber)
    $manifest = Get-Content -LiteralPath (Join-Path $candidate 'manifest.json') -Raw | ConvertFrom-Json
    if ($parts.Count -ne 8) { throw 'Expected eight v2 partitions.' }
    for ($i = 0; $i -lt 8; $i++) {
        $expected = $manifest.partitions[$i]
        if ($parts[$i].PartitionNumber -ne $expected.number -or
            $parts[$i].Offset -ne $expected.start -or
            $parts[$i].Size -ne ($expected.end_exclusive - $expected.start)) {
            throw "Partition geometry mismatch at index $i."
        }
    }
    Log "TARGET Disk=$($disk.Number) Serial=$($disk.SerialNumber) Bytes=$($disk.Size) Offline=$($disk.IsOffline)"
    if ($ConfirmWrite -and !$disk.IsOffline) { throw 'Diagnostic write requires target disk offline.' }
    $path = "\\.\PhysicalDrive$($disk.Number)"
    $image = Join-Path $root 'out/rgsp-single-card-20260911/system.raw.img'
    $source = [IO.File]::Open($image, 'Open', 'Read', 'Read')
    if ($source.Length -ne 8589934592L) { throw 'System source size mismatch.' }
    $bytes = [byte[]]::new(1MB)
    Log 'SOURCE_READ_BEGIN'
    Read-Exact $source $bytes
    $sourceHash = Hash $bytes
    Log "SOURCE_READ_OK sha256=$sourceHash"
    Log 'RAW_OPEN_BEGIN'
    $access = if ($ConfirmWrite) { [IO.FileAccess]::ReadWrite } else { [IO.FileAccess]::Read }
    $raw = [IO.FileStream]::new($path, [IO.FileMode]::Open, $access, [IO.FileShare]::None, 65536)
    Log 'RAW_OPEN_OK'
    $old = [byte[]]::new(1MB)
    [void]$raw.Seek(222298112L, [IO.SeekOrigin]::Begin)
    Log 'PREIMAGE_READ_BEGIN'
    $watch = [Diagnostics.Stopwatch]::StartNew()
    Read-Exact $raw $old
    Log "PREIMAGE_READ_OK ms=$($watch.ElapsedMilliseconds) sha256=$(Hash $old)"
    [IO.File]::WriteAllBytes((Join-Path $RunDirectory 'system-first-1m-before.bin'), $old)
    if (!$ConfirmWrite) {
        Log 'READ_ONLY_DIAGNOSTIC_OK'
        exit 0
    }
    [void]$raw.Seek(222298112L, [IO.SeekOrigin]::Begin)
    Log 'WRITE_BEGIN bytes=1048576 block=65536'
    $watch.Restart()
    for ($offset = 0; $offset -lt $bytes.Length; $offset += 65536) {
        $raw.Write($bytes, $offset, 65536)
        Log "WRITE_PROGRESS bytes=$($offset + 65536)"
    }
    Log 'FLUSH_BEGIN'
    $raw.Flush($true)
    Log "FLUSH_OK ms=$($watch.ElapsedMilliseconds)"
    $raw.Dispose()
    $raw = $null
    Log 'REOPEN_READBACK_BEGIN'
    $raw = [IO.FileStream]::new($path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::None, 65536)
    [void]$raw.Seek(222298112L, [IO.SeekOrigin]::Begin)
    Read-Exact $raw $old
    $actual = Hash $old
    Log "READBACK sha256=$actual"
    if ($actual -ne $sourceHash) { throw 'Small-write readback mismatch.' }
    Log 'SMALL_WRITE_AND_READBACK_OK_NOT_WHOLE_CARD_VERIFIED'
} catch {
    Log ("FAILED " + $_.Exception.ToString())
    exit 1
} finally {
    if ($raw) { $raw.Dispose() }
    if ($source) { $source.Dispose() }
    if ($held) { $mutex.ReleaseMutex() }
    if ($mutex) { $mutex.Dispose() }
}

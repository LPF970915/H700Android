#requires -RunAsAdministrator
[CmdletBinding()]
param([switch]$ConfirmWrite, [switch]$VerifyOnly, [switch]$Worker, [string]$RunDirectory)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'rgsp_single_card_io.ps1')
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$candidate = Join-Path $root 'out/rgsp-single-card-v2-20260911'
if ($ConfirmWrite -eq $VerifyOnly) { throw 'Choose exactly one of -ConfirmWrite or -VerifyOnly.' }
if (!$Worker) {
    $RunDirectory = Join-Path $candidate ('write-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
    [void][IO.Directory]::CreateDirectory($RunDirectory)
    $argsLine = '-NoLogo -NoProfile -File "{0}" -Worker -RunDirectory "{1}"' -f $PSCommandPath, $RunDirectory
    $argsLine += $(if ($ConfirmWrite) { ' -ConfirmWrite' } else { ' -VerifyOnly' })
    $child = Start-Process -FilePath (Get-Process -Id $PID).Path -ArgumentList $argsLine `
        -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $RunDirectory 'stdout.log') `
        -RedirectStandardError (Join-Path $RunDirectory 'stderr.log')
    $child.PriorityClass = 'BelowNormal'
    $child.ProcessorAffinity = [IntPtr]1
    $started = [DateTime]::UtcNow
    while (!$child.WaitForExit(5000)) {
        $activity = Get-Item -LiteralPath (Join-Path $RunDirectory 'stages.log') -ErrorAction SilentlyContinue
        $last = if ($activity) { $activity.LastWriteTimeUtc } else { $started }
        if (([DateTime]::UtcNow - $last).TotalSeconds -gt 120) {
            $child.Kill()
            $child.WaitForExit()
            [IO.File]::WriteAllText((Join-Path $RunDirectory 'exit.txt'), 'TIMEOUT_KILLED_NOT_VERIFIED')
            exit 2
        }
    }
    [IO.File]::WriteAllText((Join-Path $RunDirectory 'exit.txt'), [string]$child.ExitCode)
    exit $child.ExitCode
}
if (!(Test-Path -LiteralPath $RunDirectory -PathType Container)) { throw 'Missing run directory.' }
$log = Join-Path $RunDirectory 'stages.log'
function Log([string]$Message) {
    [IO.File]::AppendAllText($log, ((Get-Date -Format o) + " PID=$PID $Message`r`n"))
}
$mutex = $null
$held = $false
$stream = $null
$sources = @()
$results = @()
try {
    Log "START Write=$ConfirmWrite VerifyOnly=$VerifyOnly"
    $mutex = [Threading.Mutex]::new($false, 'Global\RGSP_000000001539_62239277056_IO')
    try { $held = $mutex.WaitOne(0) }
    catch [Threading.AbandonedMutexException] { $held = $true }
    if (!$held) { throw 'Another target-card IO operation is active.' }
    $targets = @(Get-Disk | Where-Object {
        $_.BusType -eq 'USB' -and $_.SerialNumber.Trim() -eq '000000001539' -and $_.Size -eq 62239277056L
    })
    if ($targets.Count -ne 1) { throw 'Expected exactly one target card.' }
    $disk = $targets[0]
    $parts = @(Get-Partition -DiskNumber $disk.Number | Sort-Object PartitionNumber)
    Assert-RgspSingleCardTarget $disk $parts
    Log "TARGET Disk=$($disk.Number) Serial=$($disk.SerialNumber) Bytes=$($disk.Size) Offline=$($disk.IsOffline)"
    $manifestPath = Join-Path $candidate 'manifest.json'
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    Assert-RgspSingleCardRecipe $manifest $root
    $manifestHash = (Get-FileHash -LiteralPath $manifestPath).Hash
    foreach ($r in $manifest.ranges) {
        $file = Get-Item -LiteralPath $r.path
        if ($file.Attributes -band [IO.FileAttributes]::ReparsePoint -or $file.Length -ne $r.bytes) {
            throw "Invalid source file: $($r.path)"
        }
        $source = [IO.File]::Open($r.path, 'Open', 'Read', 'Read')
        $sources += $source
        $name = [IO.Path]::GetFileName($r.path)
        $progress = { param($done,$total) Log "SOURCE $name $done/$total" }
        $actual = Invoke-RgspSingleCardRange $source $null 0 $r.bytes $progress
        if ($actual -ne $r.sha256) { throw "Source checksum mismatch: $name" }
        Log "SOURCE_OK $name $actual"
    }
    $current = Get-Disk -Number $disk.Number
    Assert-RgspSingleCardTarget $current @(Get-Partition -DiskNumber $disk.Number | Sort-Object PartitionNumber)
    $device = "\\.\PhysicalDrive$($disk.Number)"
    $access = if ($ConfirmWrite) { [IO.FileAccess]::ReadWrite } else { [IO.FileAccess]::Read }
    Log 'EXCLUSIVE_RAW_OPEN_BEGIN'
    $stream = [IO.FileStream]::new($device, [IO.FileMode]::Open, $access, [IO.FileShare]::None, 65536)
    Log 'EXCLUSIVE_RAW_OPEN_OK'
    if ($ConfirmWrite) {
        for ($i = 0; $i -lt $manifest.ranges.Count; $i++) {
            $r = $manifest.ranges[$i]
            $name = [IO.Path]::GetFileName($r.path)
            $progress = { param($done,$total) Log "WRITE $name $done/$total" }
            $actual = Invoke-RgspSingleCardRange $sources[$i] $stream $r.offset $r.bytes $progress -Copy
            if ($actual -ne $r.sha256) { throw "Source changed during write: $name" }
            Log "WRITE_FLUSH_OK $name"
        }
        $stream.Dispose()
        $stream = $null
        Log 'REOPEN_READBACK_BEGIN'
        $stream = [IO.FileStream]::new($device, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::None, 65536)
    }
    foreach ($r in $manifest.ranges) {
        $name = [IO.Path]::GetFileName($r.path)
        $progress = { param($done,$total) Log "READBACK $name $done/$total" }
        $actual = Invoke-RgspSingleCardRange $stream $null $r.offset $r.bytes $progress
        if ($actual -ne $r.sha256) { throw "Readback mismatch: $name expected=$($r.sha256) actual=$actual" }
        Log "READBACK_OK $name $actual"
        $results += @{ name=$name; offset=$r.offset; bytes=$r.bytes; sha256=$actual }
    }
    $progress = { param($done,$total) Log "BOOT_READBACK $done/$total" }
    $bootHash = Invoke-RgspSingleCardRange $stream $null 155189248L 67108864L $progress
    if ($bootHash -ne $manifest.boot_sha256) { throw 'Embedded Android boot checksum mismatch.' }
    $stream.Dispose()
    $stream = $null
    foreach ($s in $sources) { $s.Dispose() }
    $sources = @()
    $receipt = @{
        status='WRITE_AND_READBACK_VERIFIED'; physical_boot_verified=$false
        timestamp=(Get-Date -Format o); disk_number=$disk.Number
        target_serial=$disk.SerialNumber; target_bytes=$disk.Size
        write_performed=[bool]$ConfirmWrite; ranges=$results; boot_sha256=$bootHash
        manifest_sha256=$manifestHash; writer_sha256=(Get-FileHash -LiteralPath $PSCommandPath).Hash
        helpers_sha256=(Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'rgsp_single_card_io.ps1')).Hash
        handles_closed=$true; disk_left_offline=$true; original_work_card_writes=$false
        roms='Preformatted FAT32 metadata written and byte-for-byte verified; no drive letter assigned.'
    }
    [IO.File]::WriteAllText((Join-Path $RunDirectory 'result.json'), ($receipt | ConvertTo-Json -Depth 8))
    Log 'WRITE_AND_READBACK_VERIFIED_HANDLES_CLOSED_PHYSICAL_BOOT_UNTESTED'
} catch {
    Log ("FAILED " + $_.Exception.ToString())
    exit 1
} finally {
    if ($stream) { $stream.Dispose() }
    foreach ($s in $sources) { $s.Dispose() }
    if ($held) { $mutex.ReleaseMutex() }
    if ($mutex) { $mutex.Dispose() }
}

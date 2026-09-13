#requires -RunAsAdministrator
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ImagePath,
    [Parameter(Mandatory)][int]$DiskNumber,
    [Parameter(Mandatory)][string]$RunDirectory,
    [switch]$SkipPhysicalTailClear
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Add-Type -Path (Join-Path $PSScriptRoot 'RgspVolumeLock.cs')
[IO.Directory]::CreateDirectory($RunDirectory) | Out-Null
$log = Join-Path $RunDirectory 'direct-flash.log'
function Log([string]$Message) {
    [IO.File]::AppendAllText($log, "$(Get-Date -Format o) $Message`r`n")
    Write-Host $Message
}
$locks = [Collections.Generic.List[Microsoft.Win32.SafeHandles.SafeFileHandle]]::new()
$source = $null
$raw = $null
try {
    $disk = Get-Disk -Number $DiskNumber
    if ($disk.BusType -ne 'USB' -or $disk.Size -ne 125069950976L -or
        $disk.SerialNumber.Trim() -ne '000000001539' -or $disk.IsBoot -or
        $disk.IsSystem -or $disk.IsReadOnly) { throw 'Target disk identity mismatch.' }
    $image = Get-Item -LiteralPath $ImagePath
    if ($image.Length -ne 32434554368L -or $image.Length % 512 -ne 0) {
        throw 'Unexpected image size.'
    }
    $manifest = Get-Content -LiteralPath ($ImagePath -replace '\.img$','.json') -Raw | ConvertFrom-Json
    if ($manifest.status -ne 'OFFLINE_VERIFIED_READY_FOR_FLASH') { throw 'Image manifest is not verified.' }
    Log "TARGET disk=$DiskNumber bytes=$($disk.Size) serial=$($disk.SerialNumber)"
    Log "SOURCE bytes=$($image.Length) sha=$($manifest.sha256)"
    $paths = @(Get-Partition -DiskNumber $DiskNumber | ForEach-Object {
        $_.AccessPaths | Where-Object { $_ -match '^\\\\\?\\Volume\{[0-9a-fA-F-]+\}\\$' }
    } | Sort-Object -Unique)
    foreach ($path in $paths) {
        Log "LOCK $path"
        $locks.Add([RgspVolumeLock]::LockAndDismount($path))
    }
    Log "VOLUMES_DISMOUNTED count=$($locks.Count)"
    $device = "\\.\PhysicalDrive$DiskNumber"
    $source = [IO.File]::Open($image.FullName,'Open','Read','Read')
    $raw = [IO.FileStream]::new($device,'Open','ReadWrite','None',8MB)
    if ($disk.Size -gt $source.Length + 1MB -and -not $SkipPhysicalTailClear) {
        Log 'CLEARING_PHYSICAL_TAIL'
        [void]$raw.Seek($disk.Size-1MB,'Begin')
        $zeros = [byte[]]::new(1MB)
        $raw.Write($zeros,0,$zeros.Length)
        $raw.Flush($true)
    } elseif ($SkipPhysicalTailClear) {
        Log 'SKIP_PHYSICAL_TAIL_CLEAR_NONESSENTIAL'
    }
    [void]$source.Seek(0,'Begin')
    [void]$raw.Seek(0,'Begin')
    $buffer = [byte[]]::new(8MB)
    [long]$done = 0
    $timer = [Diagnostics.Stopwatch]::StartNew()
    while ($done -lt $source.Length) {
        $n = $source.Read($buffer,0,[int][Math]::Min([long]$buffer.Length,$source.Length-$done))
        if ($n -le 0) { throw 'Unexpected image EOF.' }
        $raw.Write($buffer,0,$n)
        $done += $n
        if ($timer.Elapsed.TotalSeconds -ge 10) {
            Log ("WRITE {0}/{1} pct={2:N1} MiBps={3:N1}" -f $done,$source.Length,($done*100.0/$source.Length),($done/$timer.Elapsed.TotalSeconds/1MB))
            $timer.Restart()
        }
    }
    $raw.Flush($true)
    $raw.Dispose(); $raw=$null
    Log 'WRITE_COMPLETE_BEGIN_READBACK'
    $raw = [IO.FileStream]::new($device,'Open','Read','None',8MB)
    $hash = [Security.Cryptography.IncrementalHash]::CreateHash([Security.Cryptography.HashAlgorithmName]::SHA256)
    $done = 0; $timer.Restart()
    while ($done -lt $source.Length) {
        $n = $raw.Read($buffer,0,[int][Math]::Min([long]$buffer.Length,$source.Length-$done))
        if ($n -le 0) { throw 'Unexpected card EOF.' }
        $hash.AppendData($buffer,0,$n)
        $done += $n
        if ($timer.Elapsed.TotalSeconds -ge 10) {
            Log ("READBACK {0}/{1} pct={2:N1}" -f $done,$source.Length,($done*100.0/$source.Length))
            $timer.Restart()
        }
    }
    $actual = [Convert]::ToHexString($hash.GetHashAndReset()).ToLowerInvariant()
    $hash.Dispose()
    if ($actual -ne $manifest.sha256) { throw "Readback hash mismatch: $actual" }
    Log "READBACK_VERIFIED sha=$actual"
    @{ status='DIRECT_WRITE_AND_READBACK_VERIFIED'; disk=$DiskNumber; bytes=$image.Length;
       image=$image.FullName; sha256=$actual; volumes_locked=$locks.Count;
       physical_boot_verified=$false; completed=(Get-Date -Format o) } |
       ConvertTo-Json | Set-Content -LiteralPath (Join-Path $RunDirectory 'result.json')
}
catch {
    Log "FAILED $($_.Exception.Message)"
    exit 1
}
finally {
    if ($raw) { $raw.Dispose() }
    if ($source) { $source.Dispose() }
    foreach ($handle in $locks) { $handle.Dispose() }
}

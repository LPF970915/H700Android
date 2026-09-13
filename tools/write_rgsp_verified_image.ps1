#requires -RunAsAdministrator
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ImagePath,
    [Parameter(Mandatory)][string]$ManifestPath,
    [Parameter(Mandatory)][string]$ExpectedUniqueId,
    [Parameter(Mandatory)][long]$ExpectedSize,
    [Parameter(Mandatory)][string]$ExpectedHeadSha256,
    [Parameter(Mandatory)][string]$RunDirectory,
    [switch]$ConfirmWrite
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'rgsp_vendor_io.ps1')
Add-Type -Path (Join-Path $PSScriptRoot 'RgspVolumeLock.cs')
[IO.Directory]::CreateDirectory($RunDirectory) | Out-Null
$log = Join-Path $RunDirectory 'stages.log'
function Log([string]$message) {
    [IO.File]::AppendAllText($log,"$([DateTime]::Now.ToString('o')) $message`r`n")
}
function Target {
    $found = @(Get-Disk | Where-Object {
        $_.UniqueId -eq $ExpectedUniqueId -and $_.Size -eq $ExpectedSize -and
        $_.BusType -eq 'USB' -and !$_.IsBoot -and !$_.IsSystem -and !$_.IsReadOnly
    })
    if ($found.Count -ne 1) { throw 'Approved card identity is absent or ambiguous' }
    return $found[0]
}
$source = $null
$raw = $null
$hash = $null
$volumeLocks = [Collections.Generic.List[Microsoft.Win32.SafeHandles.SafeFileHandle]]::new()
$mediaEjected = $false
$mutex = [Threading.Mutex]::new($false,'Global\RGSP_CARD_WRITER')
$held = $false
try {
    $held = $mutex.WaitOne(0)
    if (!$held) { throw 'Another verified writer is active' }
    if (!$ConfirmWrite) { throw 'Explicit -ConfirmWrite required' }
    Log "START PID=$PID"
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    if ($manifest.status -ne 'OFFLINE_VERIFIED_READY_FOR_FLASH') {
        throw 'Image has not passed offline validation'
    }
    $file = Get-Item -LiteralPath $ImagePath
    if (($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
        $file.Length -ne $manifest.image_bytes -or $file.Length % 512 -ne 0 -or
        $file.Length -gt $ExpectedSize) { throw 'Image length/type mismatch' }
    $source = [IO.File]::Open($file.FullName,'Open','Read','Read')
    Log 'SOURCE_HASH_BEGIN'
    $hash = [Security.Cryptography.IncrementalHash]::CreateHash(
        [Security.Cryptography.HashAlgorithmName]::SHA256)
    $buffer = [byte[]]::new(4MB)
    [long]$sourceDone = 0
    $sourceTimer = [Diagnostics.Stopwatch]::StartNew()
    $sourceReport = 0.0
    while ($sourceDone -lt $source.Length) {
        $n = $source.Read($buffer,0,[int][Math]::Min([long]$buffer.Length,[long]($source.Length-$sourceDone)))
        if ($n -le 0) { throw 'Unexpected source EOF during validation' }
        $hash.AppendData($buffer,0,$n)
        $sourceDone += $n
        if ($sourceTimer.Elapsed.TotalSeconds-$sourceReport -ge 10) {
            Log ("SOURCE_HASH {0}/{1} pct={2:N1}" -f $sourceDone,$source.Length,($sourceDone*100.0/$source.Length))
            $sourceReport=$sourceTimer.Elapsed.TotalSeconds
        }
    }
    $expected = [Convert]::ToHexString($hash.GetHashAndReset()).ToLowerInvariant()
    $hash.Dispose()
    $hash = $null
    if ($expected -ne $manifest.sha256) { throw 'Source hash mismatch' }
    Log "SOURCE_HASH_OK $expected"
    $disk = Target
    $device = "\\.\PhysicalDrive$($disk.Number)"
    Log "TARGET number=$($disk.Number) bytes=$($disk.Size) unique=$($disk.UniqueId)"
    $raw = [IO.File]::Open($device,'Open','Read','ReadWrite')
    if ((Get-RgspRangeHash $raw 0 1MB) -ne $ExpectedHeadSha256.ToLowerInvariant()) {
        throw 'Card contents changed since read-only identification; refusing to write'
    }
    $raw.Dispose()
    $raw = $null
    if (!$disk.IsOffline) {
        # Windows cannot offline removable SD media. Hold locks on every
        # exposed volume until the complete physical-drive readback finishes.
        $paths = @(Get-Partition -DiskNumber $disk.Number | ForEach-Object {
            $_.AccessPaths | Where-Object { $_ -match '^\\\\\?\\Volume\{[0-9a-fA-F-]+\}\\$' }
        } | Sort-Object -Unique)
        foreach ($path in $paths) {
            Log "VOLUME_LOCK_BEGIN $path"
            $handle = [RgspVolumeLock]::LockAndDismount($path)
            $volumeLocks.Add($handle)
            Log "VOLUME_LOCKED_DISMOUNTED $path"
        }
        Log "VOLUME_ISOLATION_OK count=$($volumeLocks.Count)"
    }
    $disk = Target
    $device = "\\.\PhysicalDrive$($disk.Number)"
    Log 'ISOLATED_EXCLUSIVE_WRITE_BEGIN'
    $raw = [IO.FileStream]::new($device,'Open','ReadWrite','None',65536)
    if ((Get-RgspRangeHash $raw 0 1MB) -ne $ExpectedHeadSha256.ToLowerInvariant()) {
        throw 'Preimage changed before exclusive write; refusing'
    }
    # Retire stale GPTs from previous larger-card layouts before copying the image.
    if ($ExpectedSize - $source.Length -gt 1MB) {
        [void]$raw.Seek($ExpectedSize-1MB,'Begin')
        $raw.Write([byte[]]::new(1MB),0,1MB)
        $raw.Flush($true)
    }
    [void]$source.Seek(0,'Begin')
    [void]$raw.Seek(0,'Begin')
    $buffer = [byte[]]::new(4MB)
    [long]$done = 0
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $lastReport = 0.0
    while ($done -lt $source.Length) {
        $n = $source.Read($buffer,0,[int][Math]::Min([long]$buffer.Length,[long]($source.Length-$done)))
        if ($n -le 0) { throw 'Unexpected source EOF' }
        $raw.Write($buffer,0,$n)
        $done += $n
        if ($timer.Elapsed.TotalSeconds-$lastReport -ge 10 -or $done -eq $source.Length) {
            $speed=$done/[Math]::Max(0.1,$timer.Elapsed.TotalSeconds)/1MB
            Log ("WRITE {0}/{1} pct={2:N1} MiBps={3:N1}" -f $done,$source.Length,($done*100.0/$source.Length),$speed)
            $lastReport=$timer.Elapsed.TotalSeconds
        }
    }
    $raw.Flush($true)
    $raw.Dispose()
    $raw = $null
    Log 'WRITE_FLUSHED_REOPENING_FOR_FULL_READBACK'
    $raw = [IO.FileStream]::new($device,'Open','Read','None',65536)
    $hash = [Security.Cryptography.IncrementalHash]::CreateHash(
        [Security.Cryptography.HashAlgorithmName]::SHA256)
    $done = 0
    $timer.Restart()
    $lastReport = 0.0
    while ($done -lt $source.Length) {
        $n = $raw.Read($buffer,0,[int][Math]::Min([long]$buffer.Length,[long]($source.Length-$done)))
        if ($n -le 0) { throw 'Unexpected device EOF' }
        $hash.AppendData($buffer,0,$n)
        $done += $n
        if ($timer.Elapsed.TotalSeconds-$lastReport -ge 10 -or $done -eq $source.Length) {
            Log ("READBACK {0}/{1} pct={2:N1}" -f $done,$source.Length,($done*100.0/$source.Length))
            $lastReport=$timer.Elapsed.TotalSeconds
        }
    }
    $actual = [Convert]::ToHexString($hash.GetHashAndReset()).ToLowerInvariant()
    if ($actual -ne $expected) { throw "READBACK_MISMATCH expected=$expected actual=$actual" }
    foreach ($offset in @(222298112L,8812232704L,10959716352L)) {
        [void]$raw.Seek($offset+1024,'Begin')
        $sector=[byte[]]::new(512)
        if ($raw.Read($sector,0,512) -ne 512 -or $sector[56] -ne 0x53 -or $sector[57] -ne 0xef) {
            throw "Missing ext4 superblock at $offset"
        }
    }
    foreach ($handle in $volumeLocks) { $handle.Dispose() }
    $volumeLocks.Clear()
    try {
        [RgspVolumeLock]::Control($raw.SafeFileHandle,0x002d4808)
        $mediaEjected = $true
        Log 'MEDIA_EJECTED'
    } catch {
        Log "EJECT_NOT_AVAILABLE use Windows safe removal: $($_.Exception.Message)"
    }
    $raw.Dispose()
    $raw = $null
    $source.Dispose()
    $source = $null
    @{
        status='WRITE_AND_FULL_IMAGE_READBACK_VERIFIED'
        image=$ImagePath; image_bytes=$manifest.image_bytes; sha256=$actual
        disk_size=$ExpectedSize; unique_id=$ExpectedUniqueId
        physical_boot_verified=$false; expansion='pending first boot'
        disk_left_offline=[bool]$disk.IsOffline; handles_closed=$true
        volumes_locked_during_write=$true; media_ejected=$mediaEjected
        completed=[DateTime]::Now.ToString('o')
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $RunDirectory 'result.json')
    Log 'VERIFIED_HANDLES_CLOSED_PHYSICAL_BOOT_NOT_YET_TESTED'
} catch {
    Log "FAILED $($_.Exception.ToString())"
    exit 1
} finally {
    if ($raw) { $raw.Dispose() }
    if ($source) { $source.Dispose() }
    if ($hash) { $hash.Dispose() }
    foreach ($handle in $volumeLocks) { $handle.Dispose() }
    if ($held) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}

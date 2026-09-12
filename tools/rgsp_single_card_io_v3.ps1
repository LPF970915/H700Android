# Pure helpers; importing this file never opens a physical disk.
Set-StrictMode -Version Latest

function Assert-RgspSingleCardTarget($Disk, $Parts) {
    if ($Disk.BusType -ne 'USB' -or $Disk.SerialNumber.Trim() -ne '000000001539' -or
        $Disk.Size -ne 62239277056L -or $Disk.IsBoot -or $Disk.IsSystem -or
        $Disk.IsReadOnly) { throw 'Target identity/read-only gate failed.' }
    $starts = @(37748736L,104857600L,138412032L,155189248L,222298112L,8812232704L,10959716352L,28139585536L)
    $ends = @(104857600L,138412032L,155189248L,222298112L,8812232704L,10959716352L,28139585536L,62239275520L)
    if (@($Parts).Count -ne 8) { throw 'Expected eight v2 partitions.' }
    for ($i = 0; $i -lt 8; $i++) {
        if ($Parts[$i].PartitionNumber -ne $i + 1 -or $Parts[$i].Offset -ne $starts[$i] -or
            $Parts[$i].Size -ne $ends[$i] - $starts[$i]) { throw "Partition geometry mismatch: $i" }
    }
}

function Assert-RgspSingleCardRecipe($Manifest, [string]$Root) {
    # Basic target validation
    if ($Manifest.target_bytes -ne 62239277056L -or $Manifest.target_serial -ne '000000001539') {
        throw 'Manifest target mismatch.'
    }
    
    # Validate we have 6 ranges
    if (@($Manifest.ranges).Count -ne 6) { throw 'Expected six write ranges.' }
    
    # Expected offsets and sizes for v3b structure
    $expectedLayout = @(
        @{offset=0L; bytes=222298112L; name='prefix'},
        @{offset=222298112L; bytes=8589934592L; name='system'},
        @{offset=8812232704L; bytes=2147483648L; name='vendor'},
        @{offset=10959716352L; bytes=17179869184L; name='data'},
        @{offset=28139585536L; bytes=9437184L; name='metadata'},
        @{offset=62239275520L; bytes=1536L; name='gpt-tail'}
    )
    
    # Validate each range
    for ($i = 0; $i -lt 6; $i++) {
        $r = $Manifest.ranges[$i]
        $exp = $expectedLayout[$i]
        
        # Check offset and size match expected layout
        if ($r.offset -ne $exp.offset -or $r.bytes -ne $exp.bytes) {
            throw "Range $i ($($exp.name)): layout mismatch. Expected offset=$($exp.offset) bytes=$($exp.bytes), got offset=$($r.offset) bytes=$($r.bytes)"
        }
        
        # Validate SHA256 format
        if ($r.sha256 -notmatch '^[0-9a-f]{64}$') {
            throw "Range $i ($($exp.name)): invalid SHA256 format"
        }
        
        # Validate path exists
        if (!(Test-Path $r.path)) {
            throw "Range $i ($($exp.name)): source file not found: $($r.path)"
        }
        
        # Validate file size matches expected bytes
        $fileSize = (Get-Item $r.path).Length
        if ($fileSize -ne $r.bytes) {
            throw "Range $i ($($exp.name)): file size mismatch. Expected $($r.bytes), got $fileSize"
        }
    }
    
    Write-Host "Manifest validation passed: 6 ranges, layout correct, all files exist" -ForegroundColor Green
}

function Invoke-RgspSingleCardRange([IO.Stream]$Source, [IO.Stream]$Destination,
    [long]$Offset, [long]$Length, [scriptblock]$Progress, [switch]$Copy) {
    if ($Offset -lt 0 -or $Length -le 0 -or ($Copy -and !$Destination)) {
        throw 'Invalid range.'
    }
    if ($Copy) {
        [void]$Source.Seek(0, 'Begin')
        [void]$Destination.Seek($Offset, 'Begin')
    } else { [void]$Source.Seek($Offset, 'Begin') }
    $buffer = [byte[]]::new(65536)
    $hash = [Security.Cryptography.SHA256]::Create()
    $watch = [Diagnostics.Stopwatch]::StartNew()
    $lastReport = 0L
    $nextFlush = 67108864L
    $done = 0L
    try {
        & $Progress 0L $Length
        while ($done -lt $Length) {
            $n = $Source.Read($buffer, 0, [int][Math]::Min([long]$buffer.Length, [long]($Length - $done)))
            if ($n -le 0) { throw 'Unexpected EOF.' }
            if ($Copy) { $Destination.Write($buffer, 0, $n) }
            [void]$hash.TransformBlock($buffer, 0, $n, $buffer, 0)
            $done += $n
            if ($Copy -and $done -ge $nextFlush) {
                if ($Destination -is [IO.FileStream]) { $Destination.Flush($true) }
                else { $Destination.Flush() }
                $nextFlush += 64MB
            }
            if ($watch.ElapsedMilliseconds - $lastReport -ge 5000) {
                & $Progress $done $Length
                $lastReport = $watch.ElapsedMilliseconds
            }
        }
        if ($Copy) {
            if ($Destination -is [IO.FileStream]) { $Destination.Flush($true) }
            else { $Destination.Flush() }
        }
        [void]$hash.TransformFinalBlock([byte[]]@(), 0, 0)
        & $Progress $done $Length
        return [BitConverter]::ToString($hash.Hash).Replace('-', '').ToLowerInvariant()
    } finally { $hash.Dispose() }
}

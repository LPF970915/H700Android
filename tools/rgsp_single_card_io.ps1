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
    if ($Manifest.target_bytes -ne 62239277056L -or $Manifest.target_serial -ne '000000001539') {
        throw 'Manifest target mismatch.'
    }
    $expected = @(
        @('rgsp-single-card-v2-20260911/prefix-212m.bin',0L,222298112L),
        @('rgsp-single-card-20260911/system.raw.img',222298112L,8589934592L),
        @('rgsp-single-card-20260911/vendor.raw.img',8812232704L,2147483648L),
        @('rgsp-single-card-20260911/data.raw.img',10959716352L,17179869184L),
        @('rgsp-single-card-v2-20260911/roms-metadata.bin',28139585536L,9437184L),
        @('rgsp-single-card-v2-20260911/gpt-tail.bin',62239275520L,1536L)
    )
    if (@($Manifest.ranges).Count -ne 6) { throw 'Expected six write ranges.' }
    for ($i = 0; $i -lt 6; $i++) {
        $r = $Manifest.ranges[$i]
        $path = [IO.Path]::GetFullPath((Join-Path (Join-Path $Root 'out') $expected[$i][0]))
        if ([IO.Path]::GetFullPath($r.path) -ne $path -or $r.offset -ne $expected[$i][1] -or
            $r.bytes -ne $expected[$i][2] -or $r.sha256 -notmatch '^[0-9a-f]{64}$') {
            throw "Manifest range rejected: $i"
        }
    }
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

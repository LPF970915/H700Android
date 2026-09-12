#requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'
$base = (Resolve-Path '.\out\rgsp-single-card-v2-20260911').Path
$resultPath = Join-Path $base 'written-prefix-check.txt'
$raw = $null
try {
    $d = @(Get-Disk | Where-Object {
        $_.BusType -eq 'USB' -and $_.SerialNumber.Trim() -eq '000000001539' -and
        $_.Size -eq 62239277056L
    })
    if ($d.Count -ne 1) { throw 'Target identity mismatch.' }
    $raw = [IO.File]::Open("\\.\PhysicalDrive$($d[0].Number)", 'Open', 'Read', 'ReadWrite')
    $buf = [byte[]]::new(4MB)
    $sha = [Security.Cryptography.SHA256]::Create()
    $head = [IO.MemoryStream]::new()
    try {
        $left = 222298112L
        while ($left -gt 0) {
            $want = [int][Math]::Min([long]$buf.Length, $left)
            $n = $raw.Read($buf, 0, $want)
            if ($n -ne $want) { throw "Short read at $($222298112L - $left): $n/$want" }
            $head.Write($buf, 0, $n)
            [void]$sha.TransformBlock($buf, 0, $n, $buf, 0)
            $left -= $n
        }
        [void]$sha.TransformFinalBlock([byte[]]@(), 0, 0)
        $actual = ([BitConverter]::ToString($sha.Hash) -replace '-', '').ToLowerInvariant()
        $expected = (Get-FileHash (Join-Path $base 'prefix-212m.bin')).Hash.ToLowerInvariant()
        $all = $head.ToArray()
        function Hash-Range([byte[]]$Bytes, [int]$Offset, [int]$Length) {
            ([BitConverter]::ToString([Security.Cryptography.SHA256]::HashData($Bytes[$Offset..($Offset+$Length-1)])) -replace '-', '').ToLowerInvariant()
        }
        $lines = @(
            "PREFIX bytes=$($all.Length) actual=$actual expected=$expected match=$($actual -eq $expected)",
            "BOOT_PACKAGE_LBA24576 sha256=$(Hash-Range $all (24576*512) (1310720))",
            "BOOT_PACKAGE_LBA32800 sha256=$(Hash-Range $all (32800*512) (1310720))",
            "ENV_HEAD sha256=$(Hash-Range $all (132*1MB) 131072)",
            "ANDROID_BOOT_P4 sha256=$(Hash-Range $all 155189248 67108864)"
        )
        Set-Content -LiteralPath $resultPath -Value $lines
    } finally { $head.Dispose(); $sha.Dispose() }
} catch {
    Set-Content -LiteralPath $resultPath -Value ("PREFIX_CHECK_FAILED " + $_.Exception.ToString())
    throw
} finally { if ($raw) { $raw.Dispose() } }

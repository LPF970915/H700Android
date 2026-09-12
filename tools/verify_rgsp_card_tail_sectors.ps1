#requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'
$out = (Resolve-Path '.\out\rgsp-single-card-v2-20260911').Path
$result = Join-Path $out 'tail-sector-readback.txt'
try {
    $disk = @(Get-Disk | Where-Object {
        $_.BusType -eq 'USB' -and $_.SerialNumber.Trim() -eq '000000001539' -and
        $_.Size -eq 62239277056L
    })
    if ($disk.Count -ne 1) { throw 'Target identity mismatch.' }
    $raw = [IO.File]::Open("\\.\PhysicalDrive$($disk[0].Number)", 'Open', 'Read', 'ReadWrite')
    try {
        $hash = [Security.Cryptography.SHA256]::Create()
        try {
            for ($lba = 121561085L; $lba -le 121561087L; $lba++) {
                $buf = [byte[]]::new(512)
                [void]$raw.Seek($lba * 512L, [IO.SeekOrigin]::Begin)
                $done = 0
                while ($done -lt 512) {
                    $n = $raw.Read($buf, $done, 512 - $done)
                    if ($n -le 0) { throw "EOF at LBA $lba after $done bytes." }
                    $done += $n
                }
                [void]$hash.TransformBlock($buf, 0, 512, $buf, 0)
            }
            [void]$hash.TransformFinalBlock([byte[]]@(), 0, 0)
            $actual = ([BitConverter]::ToString($hash.Hash) -replace '-', '').ToLowerInvariant()
            $expected = (Get-FileHash (Join-Path $out 'gpt-tail.bin')).Hash.ToLowerInvariant()
            Set-Content $result "TAIL_SECTOR_READBACK actual=$actual expected=$expected match=$($actual -eq $expected)"
        } finally { $hash.Dispose() }
    } finally { $raw.Dispose() }
} catch {
    Set-Content $result ("TAIL_SECTOR_READBACK_FAILED " + $_.Exception.ToString())
    throw
}

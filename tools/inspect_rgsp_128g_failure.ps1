#requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$out = Join-Path $root 'out/rgsp-v4-card-evidence'
[IO.Directory]::CreateDirectory($out) | Out-Null
Start-Transcript -LiteralPath (Join-Path $out 'capture.log') -Force | Out-Null
$stream = $null
try {
    $matches = @(Get-Disk | Where-Object {
        $_.Size -eq 125069950976L -and $_.BusType -eq 'USB' -and
        $_.SerialNumber.Trim() -eq '000000001539' -and !$_.IsBoot -and !$_.IsSystem
    })
    if ($matches.Count -ne 1) { throw 'Exactly one approved 128G card required' }
    $disk = $matches[0]
    $disk | Select-Object Number,Size,UniqueId,IsOffline | ConvertTo-Json |
        Set-Content -LiteralPath (Join-Path $out 'disk.json')
    Write-Host 'OPEN_READONLY'
    $stream = [IO.FileStream]::new("\\.\PhysicalDrive$($disk.Number)", 'Open', 'Read', 'ReadWrite', 65536)
    foreach ($r in @(
        @{Name='head.bin'; Offset=0L; Bytes=1MB},
        @{Name='roms-head.bin'; Offset=28139585536L; Bytes=16MB},
        @{Name='system-head.bin'; Offset=222298112L; Bytes=1MB},
        @{Name='data-head.bin'; Offset=10959716352L; Bytes=1MB},
        @{Name='tail.bin'; Offset=$disk.Size-1MB; Bytes=1MB}
    )) {
        [void]$stream.Seek($r.Offset,'Begin')
        $b = [byte[]]::new($r.Bytes)
        $n = 0
        while ($n -lt $b.Length) {
            $read = $stream.Read($b,$n,$b.Length-$n)
            if ($read -le 0) { throw 'Unexpected EOF' }
            $n += $read
        }
        [IO.File]::WriteAllBytes((Join-Path $out $r.Name),$b)
        Write-Host "CAPTURED $($r.Name) $n"
    }
    Write-Host 'READONLY_CAPTURE_COMPLETE'
} catch {
    Write-Host "FAILED $($_.Exception.Message)"
    exit 1
} finally {
    if ($stream) { $stream.Dispose() }
    Stop-Transcript | Out-Null
}

param(
    [string]$Port = 'COM4',
    [int]$BaudRate = 115200,
    [int]$TimeoutSeconds = 180,
    [int]$CaptureSeconds = 600,
    [string]$OutputDirectory = 'out/logs/uart/rgsp'
)

$ErrorActionPreference = 'Stop'

if ($Port -notin [System.IO.Ports.SerialPort]::GetPortNames()) {
    throw "Serial port '$Port' is not present."
}

$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$outputPath = [System.IO.Path]::GetFullPath((Join-Path $OutputDirectory "rgsp_diag5_uboot_recovery_${timestamp}_${BaudRate}.log"))
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $outputPath) | Out-Null

$serial = [System.IO.Ports.SerialPort]::new(
    $Port,
    $BaudRate,
    [System.IO.Ports.Parity]::None,
    8,
    [System.IO.Ports.StopBits]::One
)
$serial.Handshake = [System.IO.Ports.Handshake]::None
$serial.ReadTimeout = 200
$serial.WriteTimeout = 1000
$serial.DtrEnable = $false
$serial.RtsEnable = $false
$serial.Encoding = [System.Text.Encoding]::UTF8
$transcript = [System.Text.StringBuilder]::new()

function Read-Chunk {
    param([int]$Milliseconds = 250)

    $deadline = (Get-Date).AddMilliseconds($Milliseconds)
    while ((Get-Date) -lt $deadline) {
        $chunk = $serial.ReadExisting()
        if ($chunk.Length -gt 0) {
            [void]$transcript.Append($chunk)
            [System.IO.File]::AppendAllText($outputPath, $chunk, [System.Text.Encoding]::UTF8)
            [Console]::Write($chunk)
        }
        Start-Sleep -Milliseconds 10
    }
}

function Send-Key {
    param([byte]$Value)

    $bytes = [byte[]]@($Value)
    $serial.BaseStream.Write($bytes, 0, 1)
    $serial.BaseStream.Flush()
}

function Send-Line {
    param([string]$Text)

    Write-Host "U-Boot> $Text"
    $serial.Write($Text + "`r")
    Read-Chunk -Milliseconds 1200
}

[System.IO.File]::WriteAllText($outputPath, '', [System.Text.Encoding]::UTF8)

try {
    $serial.Open()
    Write-Host "Waiting for hardware reset on $Port. Recovery log: $outputPath"

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $burstStart = $null
    $nextKey = $null
    $keyBytes = [byte[]](0x20, 0x0D, 0x0A, 0x20, 0x20, 0x20)
    $keyIndex = 0

    while ((Get-Date) -lt $deadline) {
        $chunk = $serial.ReadExisting()
        if ($chunk.Length -gt 0) {
            [void]$transcript.Append($chunk)
            [System.IO.File]::AppendAllText($outputPath, $chunk, [System.Text.Encoding]::UTF8)
            [Console]::Write($chunk)
            if ($null -eq $burstStart -and $transcript.ToString() -match '(?i)U-Boot 2018\.05') {
                $burstStart = (Get-Date).AddMilliseconds(40)
                $nextKey = $burstStart
            }
            if ($transcript.ToString() -match '(?m)=>\s*$') {
                break
            }
        }

        if ($null -ne $burstStart -and (Get-Date) -ge $nextKey -and (Get-Date) -lt $burstStart.AddSeconds(2.5)) {
            Send-Key -Value $keyBytes[$keyIndex]
            $keyIndex = ($keyIndex + 1) % $keyBytes.Length
            $nextKey = (Get-Date).AddMilliseconds(8)
        }
        Start-Sleep -Milliseconds 10
    }

    if ($transcript.ToString() -notmatch '(?m)=>\s*$') {
        throw 'U-Boot prompt was not reached before timeout.'
    }

    # The on-card diag5 payload is complete; only its legacy boot header kept
    # the previous ramdisk size. Patch that one byte in RAM, then boot it.
    Send-Line 'sunxi_flash read 45000000 boot'
    Send-Line 'md.b 45000010 4'
    Send-Line 'mw.b 45000010 eb 1'
    Send-Line 'md.b 45000010 4'
    Send-Line 'bootm 45000000'

    $captureDeadline = (Get-Date).AddSeconds($CaptureSeconds)
    while ((Get-Date) -lt $captureDeadline) {
        Read-Chunk -Milliseconds 250
    }
} finally {
    if ($serial.IsOpen) {
        $serial.Close()
    }
    $serial.Dispose()
    Write-Host "Capture saved: $outputPath"
}

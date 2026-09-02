param(
    [string]$Port = "COM4",
    [int]$BaudRate = 115200,
    [int]$TimeoutSeconds = 90,
    [string]$OutputDirectory = "out/logs/uart/rgsp"
)

$ErrorActionPreference = "Stop"

if ($Port -notin [System.IO.Ports.SerialPort]::GetPortNames()) {
    throw "Serial port '$Port' is not present. Available ports: $([System.IO.Ports.SerialPort]::GetPortNames() -join ', ')"
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outputPath = [System.IO.Path]::GetFullPath((Join-Path $OutputDirectory "rgsp_uboot_mmc_probe_${timestamp}_${BaudRate}.log"))
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

function Read-Serial {
    param([int]$Milliseconds = 250)
    $deadline = (Get-Date).AddMilliseconds($Milliseconds)
    while ((Get-Date) -lt $deadline) {
        $chunk = $serial.ReadExisting()
        if ($chunk.Length -gt 0) {
            [void]$transcript.Append($chunk)
            [Console]::Write($chunk)
        }
        Start-Sleep -Milliseconds 25
    }
}

function Wait-Pattern {
    param(
        [string]$Pattern,
        [datetime]$Deadline
    )
    while ((Get-Date) -lt $Deadline) {
        $chunk = $serial.ReadExisting()
        if ($chunk.Length -gt 0) {
            [void]$transcript.Append($chunk)
            [Console]::Write($chunk)
            if ($Pattern -eq $autobootPattern -and $transcript.ToString() -match $Pattern) {
                # U-Boot accepts a key only during a very short autoboot window.
                $serial.Write(" ")
                return $true
            }
            if ($Pattern -ne $autobootPattern -and $transcript.ToString() -match $Pattern) {
                return $true
            }
        }
        Start-Sleep -Milliseconds 25
    }
    return $false
}

function Send-Line {
    param([string]$Text)
    $serial.Write($Text + "`r")
    Read-Serial -Milliseconds 1200
}

$autobootPattern = '(?i)Hit any key to stop autoboot'
$promptPattern = '(?m)(=>|[#\$])\s*$'
$foundPrompt = $false

try {
    $serial.Open()
    Write-Host "Probing U-Boot MMC on $Port at $BaudRate 8N1. Transcript: $outputPath"
    if (-not (Wait-Pattern -Pattern $autobootPattern -Deadline (Get-Date).AddSeconds($TimeoutSeconds))) {
        throw "U-Boot autoboot prompt was not observed before timeout."
    }

    if (-not (Wait-Pattern -Pattern $promptPattern -Deadline (Get-Date).AddSeconds(10))) {
        throw "U-Boot prompt was not reached after stopping autoboot."
    }
    $foundPrompt = $true

    foreach ($command in @(
        "mmc list",
        "mmc dev 0",
        "mmc info",
        "mmc dev 1",
        "mmc info",
        "fatls mmc 1:1",
        "ext4ls mmc 1:2 /",
        "mmc dev 2",
        "mmc info",
        "fatls mmc 2:1",
        "ext4ls mmc 2:2 /"
    )) {
        Write-Host "U-Boot> $command"
        Send-Line $command
    }

    Write-Host "U-Boot> reset"
    Send-Line "reset"
    Read-Serial -Milliseconds 10000
}
finally {
    [System.IO.File]::WriteAllText($outputPath, $transcript.ToString(), [System.Text.Encoding]::UTF8)
    if ($serial.IsOpen) {
        $serial.Close()
    }
    $serial.Dispose()
    Write-Host "Transcript retained at: $outputPath"
}

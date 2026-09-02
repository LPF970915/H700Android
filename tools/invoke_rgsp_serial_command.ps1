param(
    [string]$Port = "COM4",
    [Parameter(Mandatory = $true)]
    [string]$Command,
    [int]$BaudRate = 115200,
    [int]$TimeoutSeconds = 30,
    [string]$Username = "root",
    [string]$Password = "root",
    [string]$OutputDirectory = "out/logs/uart/rgsp",
    [switch]$FireAndForget
)

$ErrorActionPreference = "Stop"

if ($Port -notin [System.IO.Ports.SerialPort]::GetPortNames()) {
    throw "Serial port '$Port' is not present. Available ports: $([System.IO.Ports.SerialPort]::GetPortNames() -join ', ')"
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outputPath = Join-Path $OutputDirectory "rgsp_serial_exec_${timestamp}_${BaudRate}.log"
$absoluteOutputPath = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $outputPath))
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $absoluteOutputPath) | Out-Null

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

function Read-SerialUntil {
    param(
        [string[]]$Patterns,
        [datetime]$Deadline
    )

    while ((Get-Date) -lt $Deadline) {
        $chunk = $serial.ReadExisting()
        if ($chunk.Length -gt 0) {
            [void]$transcript.Append($chunk)
            [Console]::Write($chunk)
            foreach ($pattern in $Patterns) {
                if ($transcript.ToString() -match $pattern) {
                    return $pattern
                }
            }
        }
        Start-Sleep -Milliseconds 50
    }

    return $null
}

function Write-SerialLine {
    param([string]$Text)
    $serial.Write($Text + "`r")
}

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$token = [Guid]::NewGuid().ToString("N")
$beginMarker = "__CODEX_SERIAL_BEGIN_${token}__"
$endMarker = "__CODEX_SERIAL_END_${token}__"
$loginPattern = '(?im)\blogin\s*:\s*$'
$passwordPattern = '(?im)(password|密码)\s*[:：>]?\s*$'

try {
    $serial.Open()
    Write-Host "Using $Port at $BaudRate 8N1. Transcript: $absoluteOutputPath"
    Write-SerialLine ""

    $promptPattern = '(?m)[#\$]\s*$'
    $state = Read-SerialUntil -Patterns @($loginPattern, $promptPattern) -Deadline $deadline
    if ($state -eq $loginPattern) {
        Write-SerialLine $Username
        Start-Sleep -Milliseconds 350
        Write-SerialLine $Password
        $state = Read-SerialUntil -Patterns @($promptPattern, '(?i)login incorrect') -Deadline $deadline
    }

    if ($state -ne $promptPattern) {
        throw "No Linux shell prompt was reached before timeout. Confirm board RX is connected to USB-TTL TX and the device is at the Linux login console."
    }

    $escapedCommand = $Command.Replace("'", "'`"'`"'")
    $wireCommand = "printf '\n$beginMarker\n'; /bin/sh -c '$escapedCommand'; rc=`$?; printf '\n${endMarker}:%s\n' `"`$rc`""
    Write-SerialLine $wireCommand

    if ($FireAndForget) {
        Start-Sleep -Milliseconds 500
        Write-Host "Fire-and-forget command sent; remote shell continues independently."
        return
    }

    $endPattern = [regex]::Escape($endMarker) + ':(\d+)'
    if (-not (Read-SerialUntil -Patterns @($endPattern) -Deadline $deadline)) {
        throw "The command did not return an end marker before timeout."
    }

    $match = [regex]::Match($transcript.ToString(), $endPattern)
    if (-not $match.Success) {
        throw "The command end marker was malformed."
    }
    $exitCode = [int]$match.Groups[1].Value
    Write-Host ""
    Write-Host "Remote exit code: $exitCode"
    exit $exitCode
} finally {
    [System.IO.File]::WriteAllText($absoluteOutputPath, $transcript.ToString(), [System.Text.Encoding]::UTF8)
    if ($serial.IsOpen) {
        $serial.Close()
    }
    $serial.Dispose()
    Write-Host "Transcript retained at: $absoluteOutputPath"
}

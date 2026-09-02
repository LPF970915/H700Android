param(
    [string]$Port,
    [int]$BaudRate = 115200,
    [string]$OutputDirectory = "out/logs/uart/rgsp",
    [switch]$List
)

$ErrorActionPreference = "Stop"

function Get-SerialPorts {
    Get-CimInstance Win32_SerialPort |
        Sort-Object DeviceID |
        Select-Object DeviceID, Name, Description, PNPDeviceID
}

if ($List -or [string]::IsNullOrWhiteSpace($Port)) {
    $ports = @(Get-SerialPorts)
    if ($ports.Count -eq 0) {
        Write-Host "No serial ports were found. Plug in the USB-TTL adapter and check its driver."
    } else {
        $ports | Format-Table -AutoSize
    }

    if ([string]::IsNullOrWhiteSpace($Port)) {
        Write-Host ""
        Write-Host "Start capture with:"
        Write-Host ".\tools\capture_rgsp_uart.ps1 -Port COMx"
        exit 0
    }
}

$portNames = [System.IO.Ports.SerialPort]::GetPortNames()
if ($Port -notin $portNames) {
    throw "Serial port '$Port' is not present. Available ports: $($portNames -join ', ')"
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outputPath = Join-Path $OutputDirectory "rgsp_uart_${timestamp}_${BaudRate}.log"
$absoluteOutputPath = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $outputPath))
$absoluteOutputDirectory = Split-Path -Parent $absoluteOutputPath
New-Item -ItemType Directory -Force -Path $absoluteOutputDirectory | Out-Null

$serial = [System.IO.Ports.SerialPort]::new(
    $Port,
    $BaudRate,
    [System.IO.Ports.Parity]::None,
    8,
    [System.IO.Ports.StopBits]::One
)
$serial.Handshake = [System.IO.Ports.Handshake]::None
$serial.ReadTimeout = 250
$serial.WriteTimeout = 1000
$serial.DtrEnable = $false
$serial.RtsEnable = $false
$serial.Encoding = [System.Text.Encoding]::UTF8

$log = [System.IO.File]::Open(
    $absoluteOutputPath,
    [System.IO.FileMode]::CreateNew,
    [System.IO.FileAccess]::Write,
    [System.IO.FileShare]::Read
)
$buffer = [byte[]]::new(4096)

try {
    $serial.Open()
    Write-Host "Capturing $Port at $BaudRate 8N1, no flow control."
    Write-Host "Log: $absoluteOutputPath"
    Write-Host "Cold-start the RGSP now. Press Ctrl+C to stop."

    while ($true) {
        try {
            $count = $serial.BaseStream.Read($buffer, 0, $buffer.Length)
            if ($count -gt 0) {
                $log.Write($buffer, 0, $count)
                $log.Flush()
                [Console]::Write([System.Text.Encoding]::UTF8.GetString($buffer, 0, $count))
            }
        } catch [System.TimeoutException] {
            continue
        }
    }
} finally {
    if ($serial.IsOpen) {
        $serial.Close()
    }
    $serial.Dispose()
    $log.Dispose()
    Write-Host ""
    Write-Host "Capture closed. Log retained at: $absoluteOutputPath"
}


# UTRA Serial Session Capture Tool
# Captures serial output from H700 device boot process
param(
    [Parameter(Mandatory=$true)]
    [string]$COMPort = 'COM4',
    
    [Parameter(Mandatory=$false)]
    [int]$Baud = 115200,
    
    [Parameter(Mandatory=$false)]
    [string]$LogPath = $null,
    
    [Parameter(Mandatory=$false)]
    [int]$TimeoutSeconds = 300
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (!$LogPath) {
    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $LogPath = Join-Path $PSScriptRoot "..\logs\serial-$timestamp.log"
}

$logDir = Split-Path -Parent $LogPath
if (!(Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

Write-Host "UTRA Serial Session" -ForegroundColor Cyan
Write-Host "Port: $COMPort @ $Baud baud"
Write-Host "Log: $LogPath"
Write-Host "Timeout: $TimeoutSeconds seconds"
Write-Host "Press Ctrl+C to stop"
Write-Host ('-' * 60)

try {
    $port = New-Object System.IO.Ports.SerialPort $COMPort, $Baud, 'None', 8, 'One'
    $port.ReadTimeout = 1000
    $port.Open()
    
    $logFile = [IO.File]::AppendText($LogPath)
    $startTime = Get-Date
    $lastData = Get-Date
    
    Write-Host "Serial port opened. Waiting for data..." -ForegroundColor Green
    
    while ($true) {
        try {
            $line = $port.ReadLine()
            $timestamp = Get-Date -Format 'HH:mm:ss.fff'
            $output = "[$timestamp] $line"
            Write-Host $output
            $logFile.WriteLine($output)
            $logFile.Flush()
            $lastData = Get-Date
        } catch [TimeoutException] {
            if ((Get-Date) - $lastData -gt [TimeSpan]::FromSeconds($TimeoutSeconds)) {
                Write-Host "`nTimeout: No data for $TimeoutSeconds seconds" -ForegroundColor Yellow
                break
            }
        }
    }
} finally {
    if ($logFile) { $logFile.Close() }
    if ($port -and $port.IsOpen) { $port.Close() }
    Write-Host "`nSession closed. Log saved to: $LogPath" -ForegroundColor Cyan
}

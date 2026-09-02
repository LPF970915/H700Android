param(
    [string]$Port = "COM4",
    [int]$BaudRate = 115200,
    [int]$TimeoutSeconds = 180,
    [string]$OutputDirectory = "out/logs/uart/rgsp"
)

$ErrorActionPreference = "Stop"
if ($Port -notin [System.IO.Ports.SerialPort]::GetPortNames()) { throw "Serial port '$Port' is not present." }
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outputPath = [System.IO.Path]::GetFullPath((Join-Path $OutputDirectory "rgsp_reboot_uboot_mmc_${timestamp}_${BaudRate}.log"))
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $outputPath) | Out-Null
$serial = [System.IO.Ports.SerialPort]::new($Port,$BaudRate,[System.IO.Ports.Parity]::None,8,[System.IO.Ports.StopBits]::One)
$serial.Handshake = [System.IO.Ports.Handshake]::None; $serial.ReadTimeout = 200; $serial.WriteTimeout = 1000
$serial.DtrEnable = $false; $serial.RtsEnable = $false; $serial.Encoding = [System.Text.Encoding]::UTF8
$transcript = [Text.StringBuilder]::new()
function Read-Chunk([int]$ms=250) {
  $end=(Get-Date).AddMilliseconds($ms)
  while((Get-Date)-lt $end) { $c=$serial.ReadExisting(); if($c.Length){[void]$transcript.Append($c);[Console]::Write($c)}; Start-Sleep -Milliseconds 20 }
}
function Wait-Any([string[]]$patterns,[datetime]$deadline) {
  while((Get-Date)-lt $deadline) {
    $c=$serial.ReadExisting()
    if($c.Length){[void]$transcript.Append($c);[Console]::Write($c); foreach($p in $patterns){if($transcript.ToString()-match $p){return $p}}}
    Start-Sleep -Milliseconds 20
  }
  return $null
}
function Send([string]$s){$serial.Write($s+"`r"); Read-Chunk 300}
$login='(?im)(login|username|\u7528\u6237\u540D)\s*[:\uFF1A]\s*$'
$password='(?im)(password|\u5BC6\u7801)\s*[:\uFF1A]\s*$'
$prompt='(?m)[#\$]\s*$'
$autoboot='(?i)Hit any key to stop autoboot'
try {
  $serial.Open(); Write-Host "Serial reboot+U-Boot probe on $Port. Transcript: $outputPath"
  # Wake a quiet getty so the login prompt is emitted before matching.
  $serial.Write("`r`n")
  Read-Chunk 500
  $state=Wait-Any @($login,$prompt) ((Get-Date).AddSeconds(30))
  if ($transcript.ToString() -match '(?i)login:\s*$') { $state=$login }
  if($state -eq $login){
    Send 'root'
    Start-Sleep -Milliseconds 500
    Send 'root'
    $state=Wait-Any @($prompt) ((Get-Date).AddSeconds(25))
  }
  if($state -ne $prompt){throw 'Linux shell prompt was not reached.'}
  Send 'sleep 3; /sbin/reboot -f'
  # The vendor U-Boot prompt is reported too late over this UART. Spam a key
  # from immediately after reboot until the autoboot window is covered.
  1..160 | ForEach-Object { $serial.Write(' '); Read-Chunk 50 }
  $state=Wait-Any @('(?m)=>\s*$') ((Get-Date).AddSeconds(8))
  if($state -ne '(?m)=>\s*$'){throw 'U-Boot prompt was not reached after stopping autoboot.'}
  foreach($cmd in @('mmc list','mmc dev 0','mmc info','mmc dev 1','mmc info','fatls mmc 1:1','ext4ls mmc 1:2 /','mmc dev 2','mmc info','fatls mmc 2:1','ext4ls mmc 2:2 /')){Write-Host "U-Boot> $cmd"; Send $cmd}
  Write-Host 'U-Boot> reset'; Send 'reset'; Read-Chunk 10000
} finally {
  [IO.File]::WriteAllText($outputPath,$transcript.ToString(),[Text.Encoding]::UTF8); if($serial.IsOpen){$serial.Close()}; $serial.Dispose(); Write-Host "Transcript retained at: $outputPath"
}

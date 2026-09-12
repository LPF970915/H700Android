param(
  [string]$Port = 'COM4',
  [Parameter(Mandatory = $true)][string]$PrepareCommand,
  [Parameter(Mandatory = $true)][string]$AndroidCommand,
  [int]$TimeoutSeconds = 120
)

$ErrorActionPreference = 'Stop'
$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$out = [IO.Path]::GetFullPath("out/logs/uart/rgsp/rgsp_android_probe_${timestamp}_115200.log")
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $out) | Out-Null
[IO.File]::WriteAllText($out, '', [Text.Encoding]::UTF8)

$serial = [IO.Ports.SerialPort]::new($Port, 115200, [IO.Ports.Parity]::None, 8, [IO.Ports.StopBits]::One)
$serial.Handshake = [IO.Ports.Handshake]::None
$serial.ReadTimeout = 200
$serial.WriteTimeout = 1000
$serial.DtrEnable = $false
$serial.RtsEnable = $false
$serial.Encoding = [Text.Encoding]::UTF8
$transcript = [Text.StringBuilder]::new()
$probeEnd = '__RGSP_ANDROID_CONSOLE_PROBE_END__'

function Read-SerialChunk {
  $chunk = $serial.ReadExisting()
  if ($chunk.Length -gt 0) {
    [void]$transcript.Append($chunk)
    [IO.File]::AppendAllText($out, $chunk, [Text.Encoding]::UTF8)
    [Console]::Write($chunk)
  }
}

try {
  $serial.Open()
  Write-Host "Android console probe: $out"
  $serial.Write("`r")
  $linuxDeadline = (Get-Date).AddSeconds(30)
  while ((Get-Date) -lt $linuxDeadline) {
    Read-SerialChunk
    if ($transcript.ToString() -match '(?im)login\s*:|root@[^\r\n]*[#\$]\s*$') { break }
    Start-Sleep -Milliseconds 50
  }
  if ($transcript.ToString() -match '(?im)login\s*:') {
    $serial.Write("root`r")
    Start-Sleep -Milliseconds 400
    Read-SerialChunk
    $serial.Write("root`r")
    Start-Sleep -Milliseconds 700
    Read-SerialChunk
  }

  $serial.Write($PrepareCommand.TrimEnd() + "`r")
  $androidDeadline = (Get-Date).AddSeconds($TimeoutSeconds)
  $probeSent = $false
  while ((Get-Date) -lt $androidDeadline) {
    Read-SerialChunk
    if (-not $probeSent -and $transcript.ToString() -match '(?m)(?:console|rgsp):/\s*[#$]\s*$') {
      $wire = "echo __RGSP_ANDROID_CONSOLE_PROBE_BEGIN__; " +
        $AndroidCommand.TrimEnd() + 
        "; rc=`$?; echo ANDROID_PROBE_RC=`$rc; echo $probeEnd"
      $serial.Write($wire + "`r")
      $probeSent = $true
    }
    if ($probeSent -and $transcript.ToString().Contains($probeEnd)) { break }
    Start-Sleep -Milliseconds 50
  }
  if (-not $probeSent) { throw 'Android console prompt was not detected before timeout' }
  if (-not $transcript.ToString().Contains($probeEnd)) { throw 'Android probe did not finish before timeout' }
  Write-Host "ANDROID_CONSOLE_PROBE_OK: $out"
} finally {
  if ($serial.IsOpen) { $serial.Close() }
  $serial.Dispose()
}

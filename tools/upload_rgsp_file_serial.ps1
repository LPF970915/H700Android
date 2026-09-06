param(
  [string]$Port = 'COM4',
  [Parameter(Mandatory = $true)][string]$LocalPath,
  [Parameter(Mandatory = $true)][string]$RemotePath
)

$ErrorActionPreference = 'Stop'
if ($RemotePath -notmatch '^/[A-Za-z0-9_./@:+-]+$') { throw 'Unsupported remote path.' }

$serial = [IO.Ports.SerialPort]::new(
  $Port, 115200, [IO.Ports.Parity]::None, 8, [IO.Ports.StopBits]::One
)
$serial.Handshake = 'None'
$serial.ReadTimeout = 200
$serial.WriteTimeout = 1000
$serial.Encoding = [Text.Encoding]::UTF8
$transcript = [Text.StringBuilder]::new()
$transferStarted = $false
$transferCompleted = $false

function Read-Now {
  $chunk = $serial.ReadExisting()
  if ($chunk.Length) {
    [void]$transcript.Append($chunk)
    [Console]::Write($chunk)
  }
}

function Send-Line([string]$Text) {
  $serial.Write($Text + "`r")
}

function Wait-Prompt {
  $deadline = (Get-Date).AddSeconds(60)
  while ((Get-Date) -lt $deadline) {
    Read-Now
    if ($transcript.ToString() -match '(?m)[#\$]\s*$') { return }
    if ($transcript.ToString() -match '(?im)login\s*:\s*$') { Send-Line 'root' }
    if ($transcript.ToString() -match '(?im)(password|密码)\s*[:：>]?\s*$') { Send-Line 'root' }
    Start-Sleep -Milliseconds 50
  }
  throw 'prompt timeout'
}

try {
  $serial.Open()
  Send-Line ''
  Wait-Prompt

  $base64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($LocalPath))
  Send-Line "stty -echo; base64 -d > '$RemotePath'"
  $transferStarted = $true
  Start-Sleep -Milliseconds 500

  for ($offset = 0; $offset -lt $base64.Length; $offset += 512) {
    $length = [Math]::Min(512, $base64.Length - $offset)
    $serial.Write($base64.Substring($offset, $length) + "`n")
    Start-Sleep -Milliseconds 60
  }

  $serial.BaseStream.Flush()
  Start-Sleep -Milliseconds 500
  $serial.BaseStream.Write([byte[]](4), 0, 1)
  $serial.BaseStream.Flush()
  Start-Sleep -Milliseconds 1000
  Read-Now
  Send-Line 'stty sane'
  Start-Sleep -Milliseconds 500
  Read-Now
  Send-Line ''
  Wait-Prompt
  $transferCompleted = $true
  Write-Host "UPLOADED $LocalPath -> $RemotePath"
} finally {
  if ($serial.IsOpen) {
    if ($transferStarted -and -not $transferCompleted) {
      try {
        $serial.BaseStream.Write([byte[]](3), 0, 1)
        $serial.BaseStream.Flush()
        Start-Sleep -Milliseconds 300
        Send-Line 'stty sane'
      } catch {}
    }
    $serial.Close()
  }
  $serial.Dispose()
}

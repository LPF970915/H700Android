param([string]$Port = 'COM4', [int]$TimeoutSeconds = 1200)

$ErrorActionPreference = 'Stop'
$serial = [IO.Ports.SerialPort]::new($Port, 115200, [IO.Ports.Parity]::None, 8, [IO.Ports.StopBits]::One)
$serial.Handshake = 'None'
$serial.ReadTimeout = 200
$serial.WriteTimeout = 1000
$serial.DtrEnable = $false
$serial.RtsEnable = $false
$serial.Encoding = [Text.Encoding]::UTF8
$transcript = [Text.StringBuilder]::new()

function Read-Chunk {
  $chunk = $serial.ReadExisting()
  if ($chunk.Length -gt 0) {
    [void]$transcript.Append($chunk)
    [Console]::Write($chunk)
  }
}

function Send-Line([string]$line) {
  $serial.Write($line + "`r")
}

function Wait-Shell([int]$seconds = 60) {
  $deadline = (Get-Date).AddSeconds($seconds)
  $loginSent = $false
  $passwordSent = $false
  while ((Get-Date) -lt $deadline) {
    Read-Chunk
    $text = $transcript.ToString()
    if (-not $loginSent -and $text -match '(?im)login\s*:\s*$') {
      Send-Line 'root'
      $loginSent = $true
      Start-Sleep -Milliseconds 500
    } elseif ($loginSent -and -not $passwordSent -and $text -match '(?im)(password|密码)\s*[:：>]?\s*$') {
      Send-Line 'root'
      $passwordSent = $true
      Start-Sleep -Milliseconds 800
    } elseif ($text -match '(?m)[#\$]\s*$') {
      return
    }
    Start-Sleep -Milliseconds 50
  }
  throw 'Linux shell prompt not reached'
}

function Upload-Base64([string]$remote, [byte[]]$bytes) {
  $base64 = [Convert]::ToBase64String($bytes)
  Send-Line "stty -icanon min 1 time 0 -echo; base64 -d > $remote"
  Start-Sleep -Milliseconds 300
  $chunkSize = 8192
  for ($offset = 0; $offset -lt $base64.Length; $offset += $chunkSize) {
    $length = [Math]::Min($chunkSize, $base64.Length - $offset)
    $serial.Write($base64.Substring($offset, $length))
    Read-Chunk
    Start-Sleep -Milliseconds 2
  }
  $serial.Write("`r")
  Start-Sleep -Milliseconds 100
  $serial.BaseStream.Write([byte[]](4), 0, 1)
  Start-Sleep -Milliseconds 700
  Read-Chunk
  Send-Line 'stty sane'
  Start-Sleep -Milliseconds 700
  Read-Chunk
}

function Run-Command([string]$command, [int]$seconds = 300) {
  $token = [Guid]::NewGuid().ToString('N')
  $end = "__CODEX_SERIAL_END_${token}__"
  $escaped = $command.Replace("'", "'`"'`"'")
  Send-Line "printf '\n$end\n'; /bin/sh -c '$escaped'; rc=`$?; printf '\n${end}:%s\n' `"`$rc`""
  $deadline = (Get-Date).AddSeconds($seconds)
  while ((Get-Date) -lt $deadline) {
    Read-Chunk
    if ($transcript.ToString() -match ([regex]::Escape($end) + ':\d+')) { break }
    Start-Sleep -Milliseconds 50
  }
  $match = [regex]::Match($transcript.ToString(), ([regex]::Escape($end) + ':(\d+)'))
  if (-not $match.Success) { throw "command timeout: $command" }
  if ([int]$match.Groups[1].Value -ne 0) { throw "command failed: $command" }
}

$log = "out/logs/uart/rgsp/fix56/rgsp_fix56_upload_apply_prepare_$(Get-Date -Format yyyyMMdd_HHmmss)_115200.log"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $log) | Out-Null

try {
  $serial.Open()
  Send-Line ''
  Start-Sleep -Milliseconds 700
  Read-Chunk
  Wait-Shell

  Upload-Base64 '/tmp/rgsp-fix56-payload.tar.gz' ([IO.File]::ReadAllBytes('out/fix56-h616-lights-ion/fix56-h616-lights-ion-payload.tar.gz'))
  Upload-Base64 '/tmp/rgsp-fix56-payload.sha256' ([IO.File]::ReadAllBytes('out/fix56-h616-lights-ion/payload.sha256'))
  Upload-Base64 '/tmp/apply_rgsp_android_fix56_h616_lights_ion.sh' ([IO.File]::ReadAllBytes('device/apply_rgsp_android_fix56_h616_lights_ion.sh'))
  Upload-Base64 '/tmp/prepare_rgsp_android_fix56_test.sh' ([IO.File]::ReadAllBytes('device/prepare_rgsp_android_fix56_test.sh'))

  Run-Command "rm -rf /tmp/rgsp-fix56-payload; mkdir -p /tmp/rgsp-fix56-payload; tar -xzf /tmp/rgsp-fix56-payload.tar.gz -C /tmp/rgsp-fix56-payload; chmod 0755 /tmp/apply_rgsp_android_fix56_h616_lights_ion.sh /tmp/prepare_rgsp_android_fix56_test.sh; cd /tmp/rgsp-fix56-payload && sha256sum -c /tmp/rgsp-fix56-payload.sha256; /bin/sh /tmp/apply_rgsp_android_fix56_h616_lights_ion.sh; /bin/sh /tmp/prepare_rgsp_android_fix56_test.sh" 900
  Write-Host 'FIX56_APPLY_AND_PREP_OK'
} finally {
  if ($serial.IsOpen) { $serial.Close() }
  $serial.Dispose()
  [IO.File]::WriteAllText([IO.Path]::GetFullPath($log), $transcript.ToString(), [Text.Encoding]::UTF8)
}

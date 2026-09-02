param(
  [string]$Port = 'COM4',
  [int]$CaptureSeconds = 1200
)

$ErrorActionPreference = 'Stop'
$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$out = [IO.Path]::GetFullPath("out/logs/uart/rgsp/rgsp_uart_fix42_${timestamp}_115200.log")
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $out) | Out-Null
$jarGz = [IO.Path]::GetFullPath('work/fix42-tools/services-watchdog-bypass.jar.gz')
$payload = [Convert]::ToBase64String([IO.File]::ReadAllBytes($jarGz))
$applyPayload = [Convert]::ToBase64String([IO.File]::ReadAllBytes([IO.Path]::GetFullPath('device/apply_rgsp_android_fix42_watchdog.sh')))
$preparePayload = [Convert]::ToBase64String([IO.File]::ReadAllBytes([IO.Path]::GetFullPath('device/prepare_rgsp_android_fix42_test.sh')))
$serial = [IO.Ports.SerialPort]::new($Port,115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$serial.Handshake=[IO.Ports.Handshake]::None
$serial.ReadTimeout=200
$serial.WriteTimeout=1000
$serial.DtrEnable=$false
$serial.RtsEnable=$false
$serial.Encoding=[Text.Encoding]::UTF8
$sb=[Text.StringBuilder]::new()

function Read-Chunk {
  $x=$serial.ReadExisting()
  if($x.Length -gt 0){ [void]$sb.Append($x) }
}
function Wait-Prompt([int]$seconds=30) {
  $deadline=(Get-Date).AddSeconds($seconds)
  while((Get-Date)-lt $deadline){ Read-Chunk; if($sb.ToString() -match '(?m)[#\$]\s*$'){ return }; Start-Sleep -Milliseconds 50 }
  throw 'Linux shell prompt not reached'
}
function Ensure-Shell([int]$seconds=30) {
  $deadline=(Get-Date).AddSeconds($seconds)
  $loginSent=$false; $passwordSent=$false
  while((Get-Date)-lt $deadline){
    Read-Chunk
    $t=$sb.ToString()
    if(-not $loginSent -and $t -match '(?im)login\s*:'){ Send-Line 'root'; $loginSent=$true; Start-Sleep -Milliseconds 400; continue }
    if($loginSent -and -not $passwordSent -and $t -match '(?im)(password|密码)\s*[:：]?\s*$'){ Send-Line 'root'; $passwordSent=$true; Start-Sleep -Milliseconds 800; continue }
    if($t -match '(?m)[#\$]\s*$'){ return }
    Start-Sleep -Milliseconds 50
  }
  throw 'Linux shell prompt not reached'
}
function Send-Line([string]$line) { $serial.Write($line + "`r") }
function Run-Command([string]$cmd,[int]$seconds=180) {
  $token=[Guid]::NewGuid().ToString('N'); $begin="__CODEX_SERIAL_BEGIN_${token}__"; $end="__CODEX_SERIAL_END_${token}__"
  Send-Line("printf '\n$begin\n'; /bin/sh -c '" + $cmd.Replace("'", "'`"'`"'") + "'; rc=`$?; printf '\n${end}:%s\n' `"`$rc`"")
  $deadline=(Get-Date).AddSeconds($seconds)
  while((Get-Date)-lt $deadline){ Read-Chunk; if($sb.ToString() -match ([regex]::Escape($end)+':\d+')){ break }; Start-Sleep -Milliseconds 50 }
  $m=[regex]::Match($sb.ToString(),([regex]::Escape($end)+':(\d+)')); if(-not $m.Success){ throw "command timeout: $cmd" }; if([int]$m.Groups[1].Value -ne 0){ throw "command failed: $cmd" }
}
function Upload-Base64([string]$remote,[string]$data,[int]$seconds=120) {
  Send-Line "stty -icanon min 1 time 0 -echo; base64 -d > $remote"
  Start-Sleep -Milliseconds 300
  $chunk=8192
  for($i=0;$i -lt $data.Length;$i+=$chunk){
    $n=[Math]::Min($chunk,$data.Length-$i)
    $serial.Write($data.Substring($i,$n))
    Read-Chunk
    Start-Sleep -Milliseconds 2
  }
  $serial.Write("`r")
  $serial.BaseStream.Write([byte[]](4),0,1); Start-Sleep -Milliseconds 500; Read-Chunk
  Send-Line 'stty icanon echo'; Start-Sleep -Milliseconds 800; Read-Chunk
}

try {
  $serial.Open(); Write-Host "fix42 UART capture: $out"
  Send-Line ''; Start-Sleep -Milliseconds 800; Read-Chunk
  Upload-Base64 '/tmp/apply_rgsp_android_fix42_watchdog.sh' $applyPayload
  Upload-Base64 '/tmp/prepare_rgsp_android_fix42_test.sh' $preparePayload
  Write-Host "Uploading compressed services.jar ($([math]::Round($payload.Length/1MB,2)) MiB base64)..."
  Upload-Base64 '/mnt/sdcard/rgsp-services-watchdog-bypass.jar.gz' $payload 600
  Run-Command "gunzip -c /mnt/sdcard/rgsp-services-watchdog-bypass.jar.gz > /mnt/sdcard/rgsp-services-watchdog-bypass.jar && sha256sum /mnt/sdcard/rgsp-services-watchdog-bypass.jar"
  Run-Command "chmod 0755 /tmp/apply_rgsp_android_fix42_watchdog.sh /tmp/prepare_rgsp_android_fix42_test.sh; cp /mnt/sdcard/rgsp-services-watchdog-bypass.jar /mnt/sdcard/rgsp-services-watchdog-bypass.jar"
  Run-Command "/bin/sh /tmp/apply_rgsp_android_fix42_watchdog.sh"
  Run-Command "/bin/sh /tmp/prepare_rgsp_android_fix42_test.sh" 240
  Write-Host 'FIX42_PREPARE_WRITE_OK: UART capture remains active. Please press the RGSP reset/power button now.'
  $deadline=(Get-Date).AddSeconds($CaptureSeconds)
  while((Get-Date)-lt $deadline){ Read-Chunk; Start-Sleep -Milliseconds 50 }
} finally {
  if($serial.IsOpen){$serial.Close()}; $serial.Dispose(); [IO.File]::WriteAllText($out,$sb.ToString(),[Text.Encoding]::UTF8); Write-Host "Fix42 capture saved: $out"
}

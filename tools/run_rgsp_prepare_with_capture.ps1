param(
  [string]$Port = 'COM4',
  [Parameter(Mandatory = $true)][string]$Command,
  [int]$CaptureSeconds = 600
)

$ErrorActionPreference = 'Stop'
$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$out = [IO.Path]::GetFullPath("out/logs/uart/rgsp/rgsp_uart_fix36_${timestamp}_115200.log")
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $out) | Out-Null
$serial = [IO.Ports.SerialPort]::new($Port,115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$serial.Handshake=[IO.Ports.Handshake]::None
$serial.ReadTimeout=200
$serial.WriteTimeout=1000
$serial.DtrEnable=$false
$serial.RtsEnable=$false
$serial.Encoding=[Text.Encoding]::UTF8
$sb=[Text.StringBuilder]::new()
$deadline=(Get-Date).AddSeconds(30)
$token=[Guid]::NewGuid().ToString('N')
$begin="__CODEX_SERIAL_BEGIN_${token}__"
$end="__CODEX_SERIAL_END_${token}__"

function Read-Chunk {
  $x=$serial.ReadExisting()
  if($x.Length -gt 0){ [void]$sb.Append($x); [Console]::Write($x) }
}

try {
  $serial.Open()
  Write-Host "Combined prepare/write plus UART capture: $out"
  $serial.Write("`r")
  while((Get-Date)-lt $deadline){ Read-Chunk; if($sb.ToString() -match '(?im)login\s*:|root@[^\r\n]*[#\$]\s*$'){break}; Start-Sleep -Milliseconds 50 }
  if($sb.ToString() -match '(?im)login\s*:'){
    $serial.Write("root`r"); Start-Sleep -Milliseconds 500; Read-Chunk
    $serial.Write("root`r"); Start-Sleep -Milliseconds 800; Read-Chunk
  }
  $wire = "printf '\n${begin}\n'; ${Command}; rc=`$?; printf '\n${end}:%s\n' `"`$rc`""
  $serial.Write($wire + "`r")
  $endDeadline=(Get-Date).AddSeconds(150)
  while((Get-Date)-lt $endDeadline){ Read-Chunk; if($sb.ToString() -match ([regex]::Escape($end)+':\d+')){break}; Start-Sleep -Milliseconds 50 }
  if($sb.ToString() -notmatch ([regex]::Escape($end)+':(\d+)')){ throw 'prepare command did not return end marker' }
  $rc=[int]([regex]::Match($sb.ToString(),([regex]::Escape($end)+':(\d+)')).Groups[1].Value)
  Write-Host "Prepare/write remote exit code: $rc"
  if($rc -ne 0){ throw "prepare/write failed with exit code $rc" }
  Write-Host 'PREPARE_WRITE_OK: UART capture remains active. Reboot the RGSP now.'
  $captureDeadline=(Get-Date).AddSeconds($CaptureSeconds)
  while((Get-Date)-lt $captureDeadline){ Read-Chunk; Start-Sleep -Milliseconds 50 }
} finally {
  if($serial.IsOpen){$serial.Close()}
  $serial.Dispose()
  [IO.File]::WriteAllText($out,$sb.ToString(),[Text.Encoding]::UTF8)
  Write-Host "Capture saved: $out"
}

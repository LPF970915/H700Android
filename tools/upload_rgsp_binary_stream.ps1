param(
  [string]$Port = 'COM4',
  [Parameter(Mandatory = $true)][string]$LocalPath,
  [Parameter(Mandatory = $true)][string]$RemotePath,
  [int]$BlockBytes = 4096,
  [int]$DelayMilliseconds = 390
)

$ErrorActionPreference = 'Stop'
if ($BlockBytes -ne 4096) { throw 'BlockBytes must be 4096 for this UART profile.' }
$data = [IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $LocalPath))
$size = $data.Length
$blocks = [Math]::Ceiling($size / $BlockBytes)
$padded = [byte[]]::new($blocks * $BlockBytes)
[Array]::Copy($data, $padded, $size)
$command = "stty raw -echo -ixon -ixoff -icrnl; set -e; rm -f '$RemotePath'; dd iflag=fullblock of='$RemotePath' bs=$BlockBytes count=$blocks status=none; truncate -s $size '$RemotePath'; stty sane; echo __RGSP_BINARY_STREAM_DONE__"

$serial = [IO.Ports.SerialPort]::new($Port,115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$serial.Handshake='None'; $serial.ReadTimeout=200; $serial.WriteTimeout=3000
$serial.DtrEnable=$false; $serial.RtsEnable=$false; $serial.Encoding=[Text.Encoding]::ASCII
$transcript = [Text.StringBuilder]::new()
function Read-Now { $x=$serial.ReadExisting(); if($x){[void]$transcript.Append($x);[Console]::Write($x)} }
function Wait-Prompt([int]$seconds=60) {
  $deadline=(Get-Date).AddSeconds($seconds)
  while((Get-Date)-lt$deadline){
    Read-Now
    if($transcript.ToString()-match '(?m)[#\$]\s*$'){return $true}
    if($transcript.ToString()-match '(?im)login\s*:\s*$'){$serial.Write("root`r")}
    if($transcript.ToString()-match '(?im)(password|密码)\s*[:：>]?\s*$'){$serial.Write("root`r")}
    Start-Sleep -Milliseconds 40
  }
  return $false
}
try {
  $serial.Open(); $serial.Write("`r"); if(-not (Wait-Prompt)){throw 'Linux prompt timeout.'}
  Write-Host "Binary stream upload $LocalPath -> $RemotePath ($size bytes, $blocks blocks)"
  $serial.Write($command + "`r")
  # Let the shell finish switching the line discipline before raw bytes start.
  Start-Sleep -Seconds 3
  $sent=0; $last=0
  while($sent -lt $padded.Length){
    $n=[Math]::Min($BlockBytes,$padded.Length-$sent)
    $serial.BaseStream.Write($padded,$sent,$n); $serial.BaseStream.Flush(); $sent += $n
    if($sent-$last -ge 262144 -or $sent -eq $padded.Length){Write-Host ("  {0:P0}" -f ($sent/$padded.Length));$last=$sent}
    Start-Sleep -Milliseconds $DelayMilliseconds
  }
  $deadline=(Get-Date).AddSeconds(30)
  while((Get-Date)-lt$deadline){Read-Now;if($transcript.ToString()-match '__RGSP_BINARY_STREAM_DONE__'){break};Start-Sleep -Milliseconds 50}
  if($transcript.ToString() -notmatch '__RGSP_BINARY_STREAM_DONE__'){throw 'Binary stream completion marker timeout.'}
  if(-not (Wait-Prompt 30)){throw 'Prompt timeout after binary stream upload.'}
  Write-Host "BINARY_STREAM_UPLOAD_OK $LocalPath -> $RemotePath"
} finally { if($serial.IsOpen){$serial.Close()};$serial.Dispose() }

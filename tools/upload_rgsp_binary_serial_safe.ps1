param(
  [string]$Port = 'COM4',
  [Parameter(Mandatory = $true)][string]$LocalPath,
  [Parameter(Mandatory = $true)][string]$RemotePath,
  [int]$ChunkBytes = 4096,
  [int]$DelayMilliseconds = 390
)

$ErrorActionPreference = 'Stop'
$data = [IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $LocalPath))
$size = $data.Length
if ($ChunkBytes -lt 512 -or $ChunkBytes -gt 8192) { throw 'ChunkBytes must be between 512 and 8192.' }
$full = [Math]::Floor($size / 1048576)
$tail = $size - ($full * 1048576)
$command = "stty raw -echo -ixon -ixoff -icrnl; rm -f '$RemotePath'; dd of='$RemotePath' bs=1048576 count=$full status=none; dd of='$RemotePath' bs=1 count=$tail oflag=append conv=notrunc status=none"
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
$rawStarted=$false
try {
  $serial.Open(); $serial.Write("`r"); if(-not (Wait-Prompt)){throw 'Linux prompt timeout.'}
  Write-Host "Binary-safe upload $LocalPath -> $RemotePath ($size bytes)"
  $serial.Write($command + "`r"); $rawStarted=$true; Start-Sleep -Milliseconds 700
  $sent=0; $last=0
  while($sent -lt $size){
    $n=[Math]::Min($ChunkBytes,$size-$sent)
    $serial.BaseStream.Write($data,$sent,$n); $serial.BaseStream.Flush(); $sent += $n
    if($sent-$last -ge 262144 -or $sent -eq $size){Write-Host ("  {0:P0}" -f ($sent/$size));$last=$sent}
    Start-Sleep -Milliseconds $DelayMilliseconds
  }
  Start-Sleep -Seconds 3
  $serial.Write("stty sane`r"); Start-Sleep -Seconds 2; $serial.Write("`r")
  if(-not (Wait-Prompt 60)){throw 'Prompt timeout after binary upload.'}
  Write-Host "BINARY_SAFE_UPLOAD_OK $LocalPath -> $RemotePath"
} finally {
  if($serial.IsOpen){
    if($rawStarted){try{$serial.Write("`u{0004}");Start-Sleep -Milliseconds 500;$serial.Write("stty sane`r")}catch{}}
    $serial.Close()
  }
  $serial.Dispose()
}

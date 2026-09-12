param(
  [string]$Port = 'COM4',
  [Parameter(Mandatory = $true)][string]$LocalPath,
  [Parameter(Mandatory = $true)][string]$RemotePath
)

$ErrorActionPreference = 'Stop'
$data = [IO.File]::ReadAllBytes($LocalPath)
$size = $data.Length
$fullMiB = [Math]::Floor($size / 1048576)
$tail = $size - ($fullMiB * 1048576)
$command = "stty raw -echo -ixon -ixoff -icrnl; dd of=$RemotePath bs=1048576 count=$fullMiB status=none; dd of=$RemotePath bs=1 count=$tail oflag=append conv=notrunc status=none"

$s = [IO.Ports.SerialPort]::new($Port,115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$s.Handshake = 'None'; $s.ReadTimeout = 200; $s.WriteTimeout = 1000
$s.DtrEnable = $false; $s.RtsEnable = $false; $s.Encoding = [Text.Encoding]::ASCII
$sb = [Text.StringBuilder]::new()
function Read-Now { $x=$s.ReadExisting(); if($x){[void]$sb.Append($x);[Console]::Write($x)} }
function Wait-Prompt {
  $d=(Get-Date).AddSeconds(60)
  while((Get-Date)-lt$d){ Read-Now; if($sb.ToString()-match '(?m)[#\$]\s*$'){return}; if($sb.ToString()-match '(?im)login\s*:\s*$'){$s.Write("root`r")}; if($sb.ToString()-match '(?im)(password|密码)\s*[:：>]?\s*$'){$s.Write("root`r")}; Start-Sleep -Milliseconds 50 }
  throw 'prompt timeout'
}

try {
  $s.Open(); $s.Write("`r"); Wait-Prompt
  Write-Host "Binary upload $LocalPath -> $RemotePath ($size bytes)"
  $s.Write($command + "`r")
  Start-Sleep -Milliseconds 500
  $chunk = 4096; $sent = 0; $lastReport = 0
  while($sent -lt $size){
    $n=[Math]::Min($chunk,$size-$sent)
    $s.BaseStream.Write($data,$sent,$n); $s.BaseStream.Flush(); $sent += $n
    if($sent-$lastReport -ge 262144){Write-Host ("  {0:P0}" -f ($sent/$size));$lastReport=$sent}
    Start-Sleep -Milliseconds 380
  }
  Start-Sleep -Milliseconds 1500
  $s.Write('stty sane'); $s.Write("`r"); Start-Sleep -Milliseconds 1500; Read-Now
  $s.Write("`r"); Wait-Prompt
  Write-Host "BINARY_UPLOAD_OK $LocalPath -> $RemotePath"
} finally {
  if($s.IsOpen){$s.Close()}; $s.Dispose()
}

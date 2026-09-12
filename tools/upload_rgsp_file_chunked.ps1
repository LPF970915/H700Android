param(
  [string]$Port = 'COM4',
  [Parameter(Mandatory = $true)][string]$LocalPath,
  [Parameter(Mandatory = $true)][string]$RemotePath,
  [int]$ChunkChars = 1024
)

$ErrorActionPreference = 'Stop'
$b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($LocalPath))
$s = [IO.Ports.SerialPort]::new($Port,115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$s.Handshake='None'; $s.ReadTimeout=200; $s.WriteTimeout=2000
$s.DtrEnable=$false; $s.RtsEnable=$false; $s.Encoding=[Text.Encoding]::ASCII
$sb=[Text.StringBuilder]::new()
function Read-Now { $x=$s.ReadExisting(); if($x){[void]$sb.Append($x);[Console]::Write($x)} }
function Wait-Prompt {
  $d=(Get-Date).AddSeconds(60)
  while((Get-Date)-lt$d){Read-Now; if($sb.ToString()-match '(?m)[#\$]\s*$'){return}; if($sb.ToString()-match '(?im)login\s*:\s*$'){$s.Write("root`r")}; if($sb.ToString()-match '(?im)(password|密码)\s*[:：>]?\s*$'){$s.Write("root`r")}; Start-Sleep -Milliseconds 40}
  throw 'prompt timeout'
}
function Wait-Marker([string]$marker) {
  $d=(Get-Date).AddSeconds(20)
  while((Get-Date)-lt$d){Read-Now; if($sb.ToString().Contains($marker)){return}; Start-Sleep -Milliseconds 25}
  throw "chunk acknowledgement timeout: $marker"
}

try {
  $s.Open(); $s.Write("`r"); Wait-Prompt
  $s.Write("rm -f '$RemotePath'; stty sane`r"); Start-Sleep -Milliseconds 300; Wait-Prompt
  # Suppress command echo during the long transfer.  The acknowledgement is
  # still printed explicitly by each shell command and remains visible.
  $s.Write("stty -echo`r"); Start-Sleep -Milliseconds 800; Read-Now
  $total=[Math]::Ceiling($b64.Length/$ChunkChars); $sent=0
  for($n=0;$n-lt$total;$n++){
    $take=[Math]::Min($ChunkChars,$b64.Length-$sent)
    $part=$b64.Substring($sent,$take)
    $marker="__RGSP_CHUNK_${n}__"
    # Do not place the complete marker in the echoed command text; otherwise
    # Wait-Marker can acknowledge a chunk before the shell executes it.
    $markerPrefix='__RGSP_CHUNK_'
    $markerSuffix="${n}__"
    $s.Write("printf '%s' '$part' | base64 -d >> '$RemotePath' && printf '%s%s\n' '$markerPrefix' '$markerSuffix'`r")
    Wait-Marker $marker
    $sent += $take
    if(($n % 16) -eq 0 -or $n -eq ($total-1)){Write-Host ("  {0:P0} ({1}/{2})" -f ($sent/$b64.Length),($n+1),$total)}
  }
  $s.Write("stty sane`r"); Start-Sleep -Milliseconds 300
  Wait-Prompt
  Write-Host "CHUNKED_UPLOAD_OK $LocalPath -> $RemotePath"
} finally { if($s.IsOpen){$s.Close()}; $s.Dispose() }

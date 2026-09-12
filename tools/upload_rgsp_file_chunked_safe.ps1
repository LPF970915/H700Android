param(
  [string]$Port = 'COM4',
  [Parameter(Mandatory = $true)][string]$LocalPath,
  [Parameter(Mandatory = $true)][string]$RemotePath,
  [int]$ChunkChars = 1024,
  [int]$MaxRetries = 4
)

$ErrorActionPreference = 'Stop'
if ($ChunkChars -lt 128 -or $ChunkChars -gt 2048) { throw 'ChunkChars must be between 128 and 2048.' }
$bytes = [IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $LocalPath))
$b64 = [Convert]::ToBase64String($bytes)
$serial = [IO.Ports.SerialPort]::new($Port,115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$serial.Handshake='None'; $serial.ReadTimeout=200; $serial.WriteTimeout=3000
$serial.DtrEnable=$false; $serial.RtsEnable=$false; $serial.Encoding=[Text.Encoding]::ASCII
$transcript = [Text.StringBuilder]::new()
$recent = [Text.StringBuilder]::new()

function Read-Now {
  $x = $serial.ReadExisting()
  if ($x) { [void]$transcript.Append($x); [void]$recent.Append($x); [Console]::Write($x) }
}

function Wait-Pattern([string]$pattern, [int]$seconds = 30) {
  $deadline = (Get-Date).AddSeconds($seconds)
  while ((Get-Date) -lt $deadline) {
    Read-Now
    if ($recent.ToString() -match $pattern) { return $true }
    Start-Sleep -Milliseconds 30
  }
  return $false
}

function Reset-Recent { [void]$recent.Clear() }

function Send-Line([string]$line) {
  $serial.Write($line + "`r")
}

try {
  $serial.Open()
  $serial.Write("`r")
  if (-not (Wait-Pattern '(?m)[#\$]\s*$|(?im)login\s*:\s*$' 30)) { throw 'Linux prompt timeout.' }
  if ($transcript.ToString() -match '(?im)login\s*:\s*$') {
    Send-Line 'root'; Start-Sleep -Milliseconds 300; Send-Line 'root'
    if (-not (Wait-Pattern '(?m)[#\$]\s*$' 30)) { throw 'Root shell prompt timeout.' }
  }

  $tmp = "$RemotePath.safe-part"
  Reset-Recent
  Send-Line "rm -f '$RemotePath' '$tmp'; stty sane"
  if (-not (Wait-Pattern '(?m)[#\$]\s*$' 30)) { throw 'Initial cleanup failed.' }

  $total = [Math]::Ceiling($b64.Length / $ChunkChars)
  for ($n = 0; $n -lt $total; $n++) {
    $offset = $n * $ChunkChars
    $take = [Math]::Min($ChunkChars, $b64.Length - $offset)
    $part = $b64.Substring($offset, $take)
    $rawStart = [Math]::Floor($offset * 3 / 4)
    $rawEnd = [Math]::Min($bytes.Length, [Math]::Ceiling(($offset + $take) * 3 / 4))
    $rawLen = $rawEnd - $rawStart
    $chunkBytes = [byte[]]::new($rawLen)
    if ($rawLen -gt 0) { [Array]::Copy($bytes, $rawStart, $chunkBytes, 0, $rawLen) }
    $chunkSha = ([Security.Cryptography.SHA256]::Create()).ComputeHash($chunkBytes) | ForEach-Object { $_.ToString('x2') }
    $chunkSha = -join $chunkSha
    $marker = "__RGSP_SAFE_${n}_OK__"
    $success = $false
    for ($attempt = 1; $attempt -le $MaxRetries -and -not $success; $attempt++) {
      Reset-Recent
      $wire = "rm -f '$tmp'; printf '%s' '$part' | base64 -d > '$tmp' && test `$(stat -c %s '$tmp') = '$rawLen' && test `$(sha256sum '$tmp' | awk '{print `$1}') = '$chunkSha' && cat '$tmp' >> '$RemotePath' && rm -f '$tmp' && echo '$marker'"
      Send-Line $wire
      if ((Wait-Pattern ("(?m)^" + [regex]::Escape($marker) + "\s*$") 12)) {
        if (Wait-Pattern '(?m)[#\$]\s*$' 5) { $success = $true }
      } else {
        # Drain the prompt/error before retrying this chunk. The target file is
        # unchanged unless the complete decoded block passed both checks.
        [void](Wait-Pattern '(?m)[#\$]\s*$' 3)
      }
      if (-not $success) { Start-Sleep -Milliseconds 120 }
    }
    if (-not $success) { throw "Chunk $n failed after $MaxRetries attempts." }
    if (($n % 16) -eq 0 -or $n -eq ($total - 1)) { Write-Host ("  {0:P0} ({1}/{2})" -f (($offset + $take) / $b64.Length), ($n + 1), $total) }
  }
  Send-Line "test `$(stat -c %s '$RemotePath') = '$($bytes.Length)'"
  if (-not (Wait-Pattern '(?m)[#\$]\s*$' 30)) { throw 'Final size check failed.' }
  Write-Host "SAFE_UPLOAD_OK $LocalPath -> $RemotePath"
} finally {
  if ($serial.IsOpen) { $serial.Close() }
  $serial.Dispose()
}

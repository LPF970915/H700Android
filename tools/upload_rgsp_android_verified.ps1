param(
    [Parameter(Mandatory = $true)][string]$LocalPath,
    [Parameter(Mandatory = $true)][string]$RemotePath,
    [string]$Port = 'COM4',
    [ValidateRange(390, 1000)][int]$DelayMilliseconds = 390
)

$ErrorActionPreference = 'Stop'
if ($RemotePath -notmatch '^/data/local/tmp/[A-Za-z0-9_-][A-Za-z0-9_.-]*$') {
    throw 'Only a single file under /data/local/tmp is supported.'
}
$data = [IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $LocalPath))
if ($data.Length -eq 0) { throw 'Empty payload.' }
$sha = (Get-FileHash -LiteralPath $LocalPath -Algorithm SHA256).Hash.ToLowerInvariant()
$id = [Guid]::NewGuid().ToString('N')
$partial = "$RemotePath.$id.part"
$ready = "__RGSP_READY_${id}__"
$done = "__RGSP_DONE_${id}__"
$failed = "__RGSP_FAILED_${id}__"
# Include the wire time at 115200 8N1 (~10 bits per byte), not only the
# inter-block delay. Otherwise large payloads time out before the sender ends.
$wireSeconds = $data.Length / 11520.0
$delaySeconds = ($data.Length / 4096.0) * $DelayMilliseconds / 1000.0
$seconds = [int][Math]::Ceiling($wireSeconds + $delaySeconds) + 180
$logDirectory = Join-Path (Get-Location) 'out/logs/uart/uploads'
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$logPath = Join-Path $logDirectory "$id.log"
$serial = [IO.Ports.SerialPort]::new($Port, 115200, 'None', 8, 'One')
$serial.Handshake = 'None'
$serial.DtrEnable = $false
$serial.RtsEnable = $false
$serial.WriteTimeout = 5000
$serial.Encoding = [Text.Encoding]::ASCII
$transcript = [Text.StringBuilder]::new()
$recent = [Text.StringBuilder]::new()
function Read-Available {
    $text = $serial.ReadExisting()
    if ($text) {
        [void]$transcript.Append($text)
        [void]$recent.Append($text)
    }
}
function Wait-Marker([string]$pattern, [int]$timeout) {
    $deadline = (Get-Date).AddSeconds($timeout)
    while ((Get-Date) -lt $deadline) {
        Read-Available
        if ($recent.ToString() -match $pattern) { return $true }
        Start-Sleep -Milliseconds 40
    }
    return $false
}

# head -c handles short UART reads; a deadline restores the terminal if input stops.
# Split markers keep the shell's echoed command from satisfying a response check.
$command = "saved=`$(stty -g); stty raw -echo -isig -ixon -ixoff -icrnl -iuclc -istrip -parmrk; " +
    "printf '\n__RGSP_READY_%s__\n' '$id'; " +
    "timeout --foreground $seconds head -c $($data.Length) > '$partial'; rc=`$?; " +
    "stty `"`$saved`"; " +
    "if [ `"`$rc`" = 0 ] && [ `"`$(stat -c %s '$partial')`" = '$($data.Length)' ] " +
    "&& [ `"`$(sha256sum '$partial' | cut -d ' ' -f 1)`" = '$sha' ] " +
    "&& mv '$partial' '$RemotePath'; then printf '\n__RGSP_DONE_%s__\n' '$id'; " +
    "else printf '\n__RGSP_FAILED_%s__\n' '$id'; fi"
try {
    $serial.Open()
    $serial.Write("`r")
    if (-not (Wait-Marker '(?m)^rgsp:/[^\r\n]*#\s*$' 15)) {
        throw 'Expected an already logged-in RGSP Android root prompt.'
    }
    [void]$recent.Clear()
    $serial.Write($command + "`r")
    if (-not (Wait-Marker ("(?m)^" + $ready + "\r?$") 10)) {
        throw 'Receiver was not ready; no payload sent.'
    }
    Write-Host "Receiver ready: $($data.Length) bytes, SHA256 $sha"
    [void]$recent.Clear()
    $lastProgress = Get-Date
    for ($offset = 0; $offset -lt $data.Length; $offset += 4096) {
        $length = [Math]::Min(4096, $data.Length - $offset)
        $serial.BaseStream.Write($data, $offset, $length)
        $serial.BaseStream.Flush()
        Start-Sleep -Milliseconds $DelayMilliseconds
        Read-Available
        if ($recent.ToString() -match "(?m)^$failed\r?$") {
            throw 'Receiver failed; payload has not been committed.'
        }
        if (((Get-Date) - $lastProgress).TotalSeconds -ge 25) {
            Write-Host ("Uploaded {0:P1}" -f (($offset + $length) / $data.Length))
            $lastProgress = Get-Date
        }
    }
    if (-not (Wait-Marker ("(?m)^(" + $done + "|" + $failed + ")\r?$") 125)) {
        throw 'No verified completion; do not use the remote payload.'
    }
    if ($recent.ToString() -notmatch "(?m)^$done\r?$") {
        throw 'Remote size or SHA256 check failed.'
    }
    Write-Host "UPLOAD_VERIFIED: $RemotePath ($($data.Length) bytes, SHA256 $sha)"
} finally {
    # Do not inject shell bytes into an active raw receiver on a failed transfer.
    if ($serial.IsOpen) { $serial.Close() }
    $serial.Dispose()
    [IO.File]::WriteAllText($logPath, $transcript.ToString())
    Write-Host "Transcript: $logPath"
}

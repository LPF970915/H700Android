param(
    [Parameter(Mandatory = $true)][string]$LocalPath,
    [Parameter(Mandatory = $true)][string]$RemotePath,
    [string]$Port = 'COM4'
)
$ErrorActionPreference = 'Stop'
if ($RemotePath -notmatch '^/tmp/rgsp-[A-Za-z0-9_.-]+$') {
    throw 'Only a single temporary ramdisk file is supported.'
}
$bytes = [IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $LocalPath))
if ($bytes.Length -eq 0 -or $bytes.Length -gt 65536) { throw 'Expected a small payload.' }
$sha = (Get-FileHash -LiteralPath $LocalPath -Algorithm SHA256).Hash.ToLowerInvariant()
$id = [Guid]::NewGuid().ToString('N')
$partial = "/tmp/rgsp-upload-$id"
$serial = [IO.Ports.SerialPort]::new($Port, 115200, 'None', 8, 'One')
$serial.DtrEnable = $false
$serial.RtsEnable = $false
$serial.WriteTimeout = 5000
$serial.Encoding = [Text.Encoding]::ASCII
$transcript = [Text.StringBuilder]::new()
function Wait-Response([string]$Pattern) {
    $recent = ''
    $deadline = (Get-Date).AddSeconds(20)
    while ((Get-Date) -lt $deadline) {
        $text = $serial.ReadExisting()
        [void]$transcript.Append($text)
        $recent += $text
        if ($recent -match $Pattern) { return }
        Start-Sleep -Milliseconds 30
    }
    throw 'Ramdisk response timeout; do not use the incomplete payload.'
}
function Send-Checked([string]$Command, [string]$Step) {
    $serial.Write("$Command && printf '\n__RGSP_TEXT_%s_%s__\n' '$id' '$Step'`r")
    Wait-Response "(?m)^__RGSP_TEXT_${id}_${Step}__\r?$"
}
try {
    $serial.Open()
    $serial.Write("`r")
    Wait-Response '(?m)^/ #\s*$'
    Send-Checked "test ! -e '$partial' && touch '$partial'" 'start'
    # This ramdisk's ash truncates long input lines; stay well below 1 KiB.
    for ($offset = 0; $offset -lt $bytes.Length; $offset += 128) {
        $end = [Math]::Min($bytes.Length, $offset + 128)
        $escaped = -join ($bytes[$offset..($end - 1)] | ForEach-Object {
            '\' + [Convert]::ToString($_, 8).PadLeft(3, '0')
        })
        Send-Checked "printf '$escaped' >> '$partial'" "$offset"
    }
    Send-Checked "test `"`$(sha256sum '$partial' | cut -d ' ' -f 1)`" = '$sha' && mv '$partial' '$RemotePath'" 'done'
    Write-Output "RAMDISK_UPLOAD_VERIFIED $RemotePath bytes=$($bytes.Length) sha256=$sha"
} finally {
    $serial.Dispose()
    $logDir = Join-Path (Get-Location) 'out/logs/uart/uploads'
    [IO.Directory]::CreateDirectory($logDir) | Out-Null
    [IO.File]::WriteAllText((Join-Path $logDir "$id.log"), $transcript.ToString())
}

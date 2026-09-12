param(
    [Parameter(Mandatory = $true)][string]$RemotePath,
    [Parameter(Mandatory = $true)][string]$LocalPath,
    [string]$Port = 'COM4',
    [ValidateSet('/bin/sh', '/system/bin/sh')][string]$ShellPath = '/system/bin/sh',
    [int]$TimeoutSeconds = 120
)
$ErrorActionPreference = 'Stop'
if ($RemotePath -notmatch '^/[A-Za-z0-9_./@:+-]+$') { throw 'Unsupported remote path.' }
$id = [Guid]::NewGuid().ToString('N')
$logDir = "out/logs/uart/download-$id"
$begin = "__RGSP_FILE_${id}_BEGIN__"
$end = "__RGSP_FILE_${id}_END__"
# Split markers in the command so terminal echo cannot masquerade as output.
$command = "test -f '$RemotePath' && printf '\n__RGSP_FILE_%s_BEGIN__\n' '$id' && base64 '$RemotePath' && printf '\n__RGSP_FILE_%s_END__\n' '$id' && sha256sum '$RemotePath'"
$helper = Join-Path $PSScriptRoot 'invoke_rgsp_serial_command.ps1'
$processPath = if ([string]::IsNullOrWhiteSpace([Environment]::ProcessPath)) {
    (Get-Command pwsh.exe -ErrorAction Stop).Source
} else {
    [Environment]::ProcessPath
}
& $processPath -NoProfile -File $helper -Port $Port -ShellPath $ShellPath `
    -Command $command -TimeoutSeconds $TimeoutSeconds -OutputDirectory $logDir -Quiet
if ($LASTEXITCODE -ne 0) { throw "Remote transfer failed: $LASTEXITCODE" }
$log = Get-ChildItem -LiteralPath $logDir -Filter '*.log' | Select-Object -First 1
$text = [IO.File]::ReadAllText($log.FullName)
$pattern = [regex]::Escape($begin) + '\r?\n(?<body>[\sA-Za-z0-9+/=]+?)' +
    [regex]::Escape($end) + '\s+(?<sha>[a-f0-9]{64})'
$match = [regex]::Match($text, $pattern)
if (-not $match.Success) { throw "Transfer framing was corrupted; inspect $($log.FullName)" }
$bytes = [Convert]::FromBase64String($match.Groups['body'].Value)
$sha = [Security.Cryptography.SHA256]::Create()
try { $actual = -join ($sha.ComputeHash($bytes) | ForEach-Object { $_.ToString('x2') }) }
finally { $sha.Dispose() }
if ($actual -ne $match.Groups['sha'].Value) { throw 'Downloaded content SHA256 mismatch.' }
$target = [IO.Path]::GetFullPath($LocalPath)
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
[IO.File]::WriteAllBytes($target, $bytes)
Write-Host "DOWNLOAD_VERIFIED: $target ($($bytes.Length) bytes, SHA256 $actual)"

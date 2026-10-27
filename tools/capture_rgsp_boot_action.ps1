param(
    [ValidateSet('ResumeRamdisk', 'AndroidReboot', 'CaptureOnly')]
    [string]$Action = 'CaptureOnly',
    [ValidateRange(10, 300)][int]$Seconds = 75,
    [string]$Port = 'COM4'
)
$ErrorActionPreference = 'Stop'
$directory = Join-Path (Get-Location) 'out/logs/uart/reboot'
[IO.Directory]::CreateDirectory($directory) | Out-Null
$path = Join-Path $directory ("{0}_{1}.log" -f (Get-Date -Format yyyyMMdd_HHmmss), $Action)
$serial = [IO.Ports.SerialPort]::new($Port, 115200, 'None', 8, 'One')
$serial.DtrEnable = $false
$serial.RtsEnable = $false
$serial.WriteTimeout = 5000
$log = [IO.StreamWriter]::new($path, $false, [Text.Encoding]::UTF8)
$log.AutoFlush = $true
function Read-Available {
    $text = $serial.ReadExisting()
    if ($text) { $log.Write($text) }
    return $text
}
try {
    $serial.Open()
    if ($Action -ne 'CaptureOnly') {
        $serial.Write("`r")
        $prompt = ''
        $deadline = (Get-Date).AddSeconds(10)
        $pattern = if ($Action -eq 'ResumeRamdisk') { '(?m)^/ #\s*$' } else { '(?m)^rgsp:/[^\r\n]*#\s*$' }
        while ((Get-Date) -lt $deadline -and $prompt -notmatch $pattern) {
            $prompt += Read-Available
            Start-Sleep -Milliseconds 50
        }
        if ($prompt -notmatch $pattern) { throw 'Expected target shell not found; no action sent.' }
        $command = if ($Action -eq 'ResumeRamdisk') {
            'if [ -f /grow/check-fat.sh ] && [ -f /init ]; then exec /init; fi'
        } else {
            'if [ "$(getprop ro.product.device)" = rgsp ] && [ "$(getprop ro.serialno)" = 5c001089d750c872012 ]; then setprop sys.powerctl reboot; fi'
        }
        $serial.Write($command + "`r")
    }
    Write-Output "CAPTURE_STARTED action=$Action seconds=$Seconds log=$path"
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        $text = Read-Available
        if ($text -match 'rgsp-grow|rgsp-fat-check|Unmounting|Umounted|Cannot umount|powerctl_shutdown|capacity preparation|universal v5') {
            Write-Output $text
        }
        Start-Sleep -Milliseconds 30
    }
    Write-Output "CAPTURE_COMPLETE log=$path"
} finally {
    $serial.Dispose()
    $log.Dispose()
}

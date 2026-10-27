$port = new-Object System.IO.Ports.SerialPort COM4,115200,None,8,one
$port.Open()

Write-Host "=== Monitoring H700 Serial Output (30 seconds) ===" -ForegroundColor Green
Write-Host "Looking for display/backlight/flicker related messages...`n" -ForegroundColor Yellow

$startTime = Get-Date
while(((Get-Date) - $startTime).TotalSeconds -lt 30) {
    if($port.BytesToRead -gt 0) {
        $data = $port.ReadExisting()
        if($data -match "display|backlight|lcd|panel|flicker|vsync|fps|brightness") {
            Write-Host $data -ForegroundColor Cyan
        } else {
            Write-Host $data -ForegroundColor Gray
        }
    }
    Start-Sleep -Milliseconds 100
}

$port.Close()
Write-Host "`n=== Monitoring Complete ===" -ForegroundColor Green

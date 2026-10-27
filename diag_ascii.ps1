$port = new-Object System.IO.Ports.SerialPort COM4,115200,None,8,one
$port.ReadTimeout = 3000
$port.Open()

Write-Host "=== Serial Connected ===" -ForegroundColor Green
Write-Host "Sending wake-up commands..." -ForegroundColor Yellow

for($i=0; $i -lt 3; $i++) {
    $port.WriteLine("")
    Start-Sleep -Milliseconds 300
}

Start-Sleep -Milliseconds 500
$buffer = $port.ReadExisting()
Write-Host $buffer

Write-Host "`n--- Diagnostic Commands ---`n" -ForegroundColor Cyan

Write-Host "[1] Check backlight directory" -ForegroundColor Yellow
$port.WriteLine("ls /sys/class/backlight/")
Start-Sleep -Milliseconds 1500
Write-Host $port.ReadExisting()

Write-Host "`n[2] Check graphics devices" -ForegroundColor Yellow
$port.WriteLine("ls /dev/graphics/")
Start-Sleep -Milliseconds 1500
Write-Host $port.ReadExisting()

Write-Host "`n[3] Display properties" -ForegroundColor Yellow
$port.WriteLine("getprop | grep display")
Start-Sleep -Milliseconds 2000
Write-Host $port.ReadExisting()

Write-Host "`n[4] Check dmesg for display errors" -ForegroundColor Yellow
$port.WriteLine("dmesg | grep -i 'error\|fail' | grep -i 'display\|lcd\|panel' | tail -20")
Start-Sleep -Milliseconds 2000
Write-Host $port.ReadExisting()

Write-Host "`n[5] Get screen info" -ForegroundColor Yellow
$port.WriteLine("wm size")
Start-Sleep -Milliseconds 1000
Write-Host $port.ReadExisting()

Write-Host "`n[6] Get refresh rate" -ForegroundColor Yellow
$port.WriteLine("wm density")
Start-Sleep -Milliseconds 1000
Write-Host $port.ReadExisting()

Write-Host "`nWaiting for remaining output..." -ForegroundColor Yellow
Start-Sleep -Seconds 3
$remaining = $port.ReadExisting()
if($remaining) { Write-Host $remaining }

$port.Close()
Write-Host "`nSerial closed" -ForegroundColor Green

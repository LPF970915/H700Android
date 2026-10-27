$port = new-Object System.IO.Ports.SerialPort COM4,115200,None,8,one
$port.Open()

function Send-SlowCommand($cmd) {
    foreach($char in $cmd.ToCharArray()) {
        $port.Write($char)
        Start-Sleep -Milliseconds 10
    }
    $port.Write("`n")
    Start-Sleep -Milliseconds 1500
    return $port.ReadExisting()
}

Write-Host "=== H700 Screen Flicker Diagnosis ===" -ForegroundColor Green

# Wake up shell
$port.WriteLine("")
Start-Sleep -Milliseconds 500
$port.ReadExisting() | Out-Null

Write-Host "`n[1] Backlight devices:" -ForegroundColor Cyan
$result = Send-SlowCommand "ls /sys/class/backlight/"
Write-Host $result

Write-Host "`n[2] Graphics devices:" -ForegroundColor Cyan
$result = Send-SlowCommand "ls /dev/graphics/"
Write-Host $result

Write-Host "`n[3] Display properties:" -ForegroundColor Cyan
$result = Send-SlowCommand "getprop | grep display"
Write-Host $result

Write-Host "`n[4] Screen resolution:" -ForegroundColor Cyan
$result = Send-SlowCommand "wm size"
Write-Host $result

Write-Host "`n[5] Screen density:" -ForegroundColor Cyan
$result = Send-SlowCommand "wm density"
Write-Host $result

Write-Host "`n[6] Power supply status:" -ForegroundColor Cyan
$result = Send-SlowCommand "cat /sys/class/power_supply/battery/status"
Write-Host $result

Write-Host "`n[7] CPU governor:" -ForegroundColor Cyan
$result = Send-SlowCommand "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
Write-Host $result

Write-Host "`n[8] Check for display errors in kernel log:" -ForegroundColor Cyan
$result = Send-SlowCommand "dmesg | tail -30"
Write-Host $result

$port.Close()
Write-Host "`n=== Diagnosis Complete ===" -ForegroundColor Green

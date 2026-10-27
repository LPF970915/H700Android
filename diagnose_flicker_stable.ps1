$port = new-Object System.IO.Ports.SerialPort COM4,115200,None,8,one
$port.Open()
$port.NewLine = "`n"

function Send-Command($cmd, $waitMs = 1000) {
    $port.ReadExisting() | Out-Null  # 清空缓冲区
    $port.WriteLine($cmd)
    Start-Sleep -Milliseconds $waitMs
    return $port.ReadExisting()
}

Write-Host "=== H700 屏幕闪烁诊断 ===" -ForegroundColor Green

Write-Host "`n[1] 检查背光设备..." -ForegroundColor Cyan
$result = Send-Command "ls -la /sys/class/backlight/" 1500
Write-Host $result

Write-Host "`n[2] 检查背光亮度当前值..." -ForegroundColor Cyan
$result = Send-Command "find /sys/class/backlight -name brightness -exec cat {} \;" 1500
Write-Host $result

Write-Host "`n[3] 检查背光最大值..." -ForegroundColor Cyan
$result = Send-Command "find /sys/class/backlight -name max_brightness -exec cat {} \;" 1500
Write-Host $result

Write-Host "`n[4] 检查显示相关内核消息（最近50条）..." -ForegroundColor Cyan
$result = Send-Command "dmesg | grep -iE 'display|backlight|lcd|panel|pwm' | tail -50" 2000
Write-Host $result

Write-Host "`n[5] 检查电池和电源状态..." -ForegroundColor Cyan
$result = Send-Command "cat /sys/class/power_supply/battery/uevent" 1500
Write-Host $result

Write-Host "`n[6] 检查CPU调频策略..." -ForegroundColor Cyan
$result = Send-Command "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor" 1000
Write-Host $result

Write-Host "`n[7] 获取当前CPU频率..." -ForegroundColor Cyan
$result = Send-Command "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq" 1000
Write-Host $result

Write-Host "`n=== 诊断数据收集完成 ===" -ForegroundColor Green

$port.Close()

$port = new-Object System.IO.Ports.SerialPort COM4,115200,None,8,one
$port.Open()
Write-Host "=== 已连接到H700 Android系统 ===" -ForegroundColor Green
Write-Host "开始屏幕闪烁问题诊断...`n" -ForegroundColor Cyan

# 1. 检查背光设置
Write-Host "[1/6] 检查背光设置..." -ForegroundColor Yellow
$port.WriteLine("cat /sys/class/backlight/*/brightness")
Start-Sleep -Milliseconds 800
$output1 = $port.ReadExisting()
Write-Host $output1

# 2. 检查背光最大值
Write-Host "`n[2/6] 检查背光最大值..." -ForegroundColor Yellow
$port.WriteLine("cat /sys/class/backlight/*/max_brightness")
Start-Sleep -Milliseconds 800
$output2 = $port.ReadExisting()
Write-Host $output2

# 3. 检查显示驱动日志
Write-Host "`n[3/6] 检查显示相关内核日志..." -ForegroundColor Yellow
$port.WriteLine("dmesg | grep -i 'display\|backlight\|lcd\|panel'")
Start-Sleep -Milliseconds 1000
$output3 = $port.ReadExisting()
Write-Host $output3

# 4. 检查帧率和vsync
Write-Host "`n[4/6] 检查帧率统计..." -ForegroundColor Yellow
$port.WriteLine("dumpsys SurfaceFlinger | grep -A 5 'Display'")
Start-Sleep -Milliseconds 1000
$output4 = $port.ReadExisting()
Write-Host $output4

# 5. 检查电源管理
Write-Host "`n[5/6] 检查电源状态..." -ForegroundColor Yellow
$port.WriteLine("dumpsys battery")
Start-Sleep -Milliseconds 1000
$output5 = $port.ReadExisting()
Write-Host $output5

# 6. 检查CPU频率（可能影响显示稳定性）
Write-Host "`n[6/6] 检查CPU频率..." -ForegroundColor Yellow
$port.WriteLine("cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq 2>/dev/null | head -4")
Start-Sleep -Milliseconds 800
$output6 = $port.ReadExisting()
Write-Host $output6

Write-Host "`n=== 诊断完成 ===" -ForegroundColor Green
Write-Host "保持连接以进行进一步调试...`n"

# 保持shell可交互
$port.WriteLine("")
Start-Sleep -Milliseconds 300
Write-Host $port.ReadExisting()

$port.Close()

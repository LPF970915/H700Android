$port = new-Object System.IO.Ports.SerialPort COM4,115200,None,8,one
$port.ReadTimeout = 3000
$port.Open()

Write-Host "=== 串口已连接 ===" -ForegroundColor Green
Write-Host "发送唤醒命令..." -ForegroundColor Yellow

# 发送多个回车唤醒shell
for($i=0; $i -lt 3; $i++) {
    $port.WriteLine("")
    Start-Sleep -Milliseconds 300
}

Start-Sleep -Milliseconds 500
$buffer = $port.ReadExisting()
Write-Host $buffer

Write-Host "`n--- 执行诊断命令 ---`n" -ForegroundColor Cyan

# 命令1: 检查背光目录
Write-Host "[CMD] ls /sys/class/backlight/" -ForegroundColor Yellow
$port.WriteLine("ls /sys/class/backlight/")
Start-Sleep -Milliseconds 1500
$output = $port.ReadExisting()
Write-Host $output

# 命令2: 检查显示设备
Write-Host "`n[CMD] ls /dev/graphics/" -ForegroundColor Yellow
$port.WriteLine("ls /dev/graphics/")
Start-Sleep -Milliseconds 1500
$output = $port.ReadExisting()
Write-Host $output

# 命令3: 获取显示属性
Write-Host "`n[CMD] getprop | grep display" -ForegroundColor Yellow
$port.WriteLine("getprop | grep display")
Start-Sleep -Milliseconds 2000
$output = $port.ReadExisting()
Write-Host $output

# 命令4: 检查SurfaceFlinger状态
Write-Host "`n[CMD] dumpsys SurfaceFlinger --latency" -ForegroundColor Yellow
$port.WriteLine("dumpsys SurfaceFlinger --latency")
Start-Sleep -Milliseconds 2000
$output = $port.ReadExisting()
Write-Host $output

Write-Host "`n=== 等待更多输出（5秒）... ===" -ForegroundColor Yellow
Start-Sleep -Seconds 5
$remaining = $port.ReadExisting()
if($remaining) {
    Write-Host $remaining
}

$port.Close()
Write-Host "`n串口已关闭" -ForegroundColor Green

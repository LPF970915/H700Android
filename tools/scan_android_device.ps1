$adb = "C:\Users\LPF\AppData\Local\Android\Sdk\platform-tools\adb.exe"
$localIP = "192.168.31.211"
$subnet = $localIP -replace '\.\d+$', ''

Write-Host "正在扫描 $subnet.0/24 网段中的Android设备..." -ForegroundColor Cyan
Write-Host "你的电脑IP: $localIP" -ForegroundColor Yellow

# 尝试常见的Android设备IP范围
$found = @()
for ($i = 100; $i -lt 255; $i++) {
    if ($i % 10 -eq 0) {
        Write-Host "." -NoNewline
    }
    
    $testIP = "$subnet.$i"
    if ($testIP -eq $localIP) { continue }
    
    # 快速ping测试
    $ping = Test-Connection -ComputerName $testIP -Count 1 -Quiet -TimeoutSeconds 1
    if ($ping) {
        Write-Host "`n尝试连接 $testIP..." -ForegroundColor Yellow
        $result = & $adb connect "${testIP}:5555" 2>&1
        if ($result -match "connected|already") {
            $found += $testIP
            Write-Host "✓ 找到Android设备: $testIP" -ForegroundColor Green
        }
    }
}

Write-Host "`n"
if ($found.Count -gt 0) {
    Write-Host "找到 $($found.Count) 个Android设备:" -ForegroundColor Green
    $found | ForEach-Object { Write-Host "  - $_" -ForegroundColor Cyan }
} else {
    Write-Host "未找到Android设备" -ForegroundColor Red
    Write-Host "请在设备上手动查看IP地址:" -ForegroundColor Yellow
    Write-Host "  设置 -> 关于设备 -> 状态 -> IP地址" -ForegroundColor Yellow
}

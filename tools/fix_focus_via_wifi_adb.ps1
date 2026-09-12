# RGSP焦点导航修复 - WiFi ADB自动化脚本
# 使用方法: .\tools\fix_focus_via_wifi_adb.ps1 -DeviceIP <设备IP>

param(
    [Parameter(Mandatory=$true)]
    [string]$DeviceIP
)

$adb = "C:\Users\LPF\AppData\Local\Android\Sdk\platform-tools\adb.exe"
$port = 5555

Write-Host "=== RGSP焦点导航修复流程 ===" -ForegroundColor Cyan

# 1. 连接WiFi ADB
Write-Host "`n[1/6] 连接到设备 ${DeviceIP}..." -ForegroundColor Yellow
& $adb connect "${DeviceIP}:${port}"

if ($LASTEXITCODE -ne 0) {
    Write-Host "连接失败，请确认设备已连接WiFi且ADB端口已开启" -ForegroundColor Red
    exit 1
}

Start-Sleep -Seconds 2

# 2. 验证连接
Write-Host "`n[2/6] 验证ADB连接..." -ForegroundColor Yellow
& $adb devices -l

# 3. 推送修复脚本
Write-Host "`n[3/6] 推送修复脚本到设备..." -ForegroundColor Yellow
& $adb push tools\rgsp_focus_fix.sh /data/local/tmp/

# 4. 执行修复脚本
Write-Host "`n[4/6] 执行焦点修复..." -ForegroundColor Yellow
& $adb shell "sh /data/local/tmp/rgsp_focus_fix.sh"

# 5. 验证设置
Write-Host "`n[5/6] 验证TV UI模式..." -ForegroundColor Yellow
$uiMode = & $adb shell "settings get global ui_mode_type"
Write-Host "当前UI模式: $uiMode (期望值: 4)" -ForegroundColor Cyan

# 6. 清理
Write-Host "`n[6/6] 清理临时文件..." -ForegroundColor Yellow
& $adb shell "rm /data/local/tmp/rgsp_focus_fix.sh"

Write-Host "`n=== 修复完成 ===" -ForegroundColor Green
Write-Host "建议重启SystemUI使设置生效: adb shell pkill -f systemui" -ForegroundColor Yellow

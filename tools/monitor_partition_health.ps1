# H700 Android 10 - 分区健康监控脚本
# 用途: 自动监控p1(system)和data分区的健康状态
# 使用: 在Android系统运行时通过ADB执行

param(
    [string]$DeviceSerial = "",
    [int]$IntervalSeconds = 300,  # 默认5分钟检查一次
    [int]$MaxIterations = 0,       # 0表示无限循环
    [string]$LogFile = "D:\Works\H700Android\logs\partition-monitor-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"
)

$adbPath = "C:\Users\LPF\AppData\Local\Android\Sdk\platform-tools\adb.exe"

if (-not (Test-Path $adbPath)) {
    Write-Host "错误: ADB未找到: $adbPath" -ForegroundColor Red
    exit 1
}

# 创建日志目录
$logDir = Split-Path $LogFile -Parent
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logLine = "[$timestamp] [$Level] $Message"
    Write-Host $logLine
    Add-Content -Path $LogFile -Value $logLine
}

function Get-AdbCommand {
    param([string]$Command)
    if ($DeviceSerial) {
        return "& '$adbPath' -s $DeviceSerial $Command"
    } else {
        return "& '$adbPath' $Command"
    }
}

function Test-AdbConnection {
    try {
        $devices = & $adbPath devices | Select-Object -Skip 1 | Where-Object { $_ -match '\t' }
        if ($devices.Count -eq 0) {
            return $false
        }
        return $true
    } catch {
        return $false
    }
}

function Get-PartitionInfo {
    try {
        # 获取挂载信息
        $mountInfo = & $adbPath shell "mount | grep -E '(system|vendor|data)'"
        
        # 获取磁盘使用情况
        $dfInfo = & $adbPath shell "df -h | grep -E '(system|vendor|data)'"
        
        # 获取块设备信息
        $blockInfo = & $adbPath shell "ls -l /dev/block/by-name/ | grep -E '(system|vendor|data)'"
        
        return @{
            Mount = $mountInfo
            DiskUsage = $dfInfo
            BlockDevices = $blockInfo
        }
    } catch {
        Write-Log "获取分区信息失败: $_" "ERROR"
        return $null
    }
}

function Check-FileSystemErrors {
    try {
        # 检查dmesg中的文件系统错误
        $dmesgErrors = & $adbPath shell "dmesg | grep -iE '(ext4.*error|I/O error|filesystem.*corrupt)' | tail -20"
        
        # 检查logcat中的存储相关错误
        $logcatErrors = & $adbPath shell "logcat -d -s StorageManagerService:E vold:E | tail -20"
        
        return @{
            DmesgErrors = $dmesgErrors
            LogcatErrors = $logcatErrors
        }
    } catch {
        Write-Log "检查文件系统错误失败: $_" "ERROR"
        return $null
    }
}

function Check-SystemHealth {
    try {
        # 检查系统运行时间
        $uptime = & $adbPath shell "uptime"
        
        # 检查关键进程
        $processes = & $adbPath shell "ps -A | grep -E '(system_server|surfaceflinger|zygote)'"
        
        # 检查内存使用
        $meminfo = & $adbPath shell "cat /proc/meminfo | grep -E '(MemTotal|MemFree|MemAvailable)'"
        
        return @{
            Uptime = $uptime
            KeyProcesses = $processes
            Memory = $meminfo
        }
    } catch {
        Write-Log "检查系统健康失败: $_" "ERROR"
        return $null
    }
}

function Analyze-PartitionStatus {
    param($PartitionInfo, $ErrorInfo, $SystemHealth)
    
    $issues = @()
    
    # 检查是否有文件系统错误
    if ($ErrorInfo.DmesgErrors -and $ErrorInfo.DmesgErrors.Count -gt 0) {
        $issues += "检测到dmesg文件系统错误"
    }
    
    if ($ErrorInfo.LogcatErrors -and $ErrorInfo.LogcatErrors.Count -gt 0) {
        $issues += "检测到logcat存储错误"
    }
    
    # 检查分区是否正常挂载
    if (-not ($PartitionInfo.Mount -match 'system')) {
        $issues += "system分区未正常挂载"
    }
    
    if (-not ($PartitionInfo.Mount -match 'vendor')) {
        $issues += "vendor分区未正常挂载"
    }
    
    if (-not ($PartitionInfo.Mount -match 'data')) {
        $issues += "data分区未正常挂载"
    }
    
    # 检查关键进程
    if (-not ($SystemHealth.KeyProcesses -match 'system_server')) {
        $issues += "system_server进程未运行"
    }
    
    return $issues
}

# 主循环
Write-Log "========================================" "INFO"
Write-Log "分区健康监控启动" "INFO"
Write-Log "日志文件: $LogFile" "INFO"
Write-Log "检查间隔: $IntervalSeconds 秒" "INFO"
Write-Log "========================================" "INFO"

$iteration = 0

while ($true) {
    $iteration++
    
    Write-Log "----------------------------------------" "INFO"
    Write-Log "第 $iteration 次检查" "INFO"
    
    # 检查ADB连接
    if (-not (Test-AdbConnection)) {
        Write-Log "ADB未连接，等待设备..." "WARN"
        Start-Sleep -Seconds $IntervalSeconds
        continue
    }
    
    Write-Log "ADB已连接" "INFO"
    
    # 获取分区信息
    $partitionInfo = Get-PartitionInfo
    if ($partitionInfo) {
        Write-Log "分区挂载信息:" "INFO"
        $partitionInfo.Mount | ForEach-Object { Write-Log "  $_" "INFO" }
        
        Write-Log "磁盘使用情况:" "INFO"
        $partitionInfo.DiskUsage | ForEach-Object { Write-Log "  $_" "INFO" }
    }
    
    # 检查文件系统错误
    $errorInfo = Check-FileSystemErrors
    if ($errorInfo) {
        if ($errorInfo.DmesgErrors) {
            Write-Log "Dmesg错误:" "WARN"
            $errorInfo.DmesgErrors | ForEach-Object { Write-Log "  $_" "WARN" }
        }
        
        if ($errorInfo.LogcatErrors) {
            Write-Log "Logcat存储错误:" "WARN"
            $errorInfo.LogcatErrors | ForEach-Object { Write-Log "  $_" "WARN" }
        }
    }
    
    # 检查系统健康
    $systemHealth = Check-SystemHealth
    if ($systemHealth) {
        Write-Log "系统运行时间: $($systemHealth.Uptime)" "INFO"
        Write-Log "内存信息:" "INFO"
        $systemHealth.Memory | ForEach-Object { Write-Log "  $_" "INFO" }
    }
    
    # 分析状态
    $issues = Analyze-PartitionStatus $partitionInfo $errorInfo $systemHealth
    
    if ($issues.Count -gt 0) {
        Write-Log "⚠️ 发现 $($issues.Count) 个问题:" "ERROR"
        $issues | ForEach-Object { Write-Log "  - $_" "ERROR" }
    } else {
        Write-Log "✓ 所有检查通过，系统健康" "INFO"
    }
    
    # 检查是否达到最大迭代次数
    if ($MaxIterations -gt 0 -and $iteration -ge $MaxIterations) {
        Write-Log "达到最大迭代次数 ($MaxIterations)，退出监控" "INFO"
        break
    }
    
    Write-Log "下次检查时间: $(Get-Date -Date (Get-Date).AddSeconds($IntervalSeconds) -Format 'HH:mm:ss')" "INFO"
    Start-Sleep -Seconds $IntervalSeconds
}

Write-Log "监控结束" "INFO"

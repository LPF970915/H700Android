# H700Android 项目清理脚本
# 生成日期: 2026-09-12

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "H700Android 项目清理工具" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$totalFreed = 0

# 1. 清理.bak备份文件
Write-Host "[1] 清理.bak备份文件..." -ForegroundColor Yellow
$bakFiles = Get-ChildItem -Path . -Recurse -Filter "*.bak" -ErrorAction SilentlyContinue
if ($bakFiles.Count -gt 0) {
    $bakSize = ($bakFiles | Measure-Object -Property Length -Sum).Sum
    Write-Host "  找到 $($bakFiles.Count) 个文件 ($([math]::Round($bakSize/1MB,2)) MB)" -ForegroundColor Gray
    $bakFiles | Remove-Item -Force -ErrorAction SilentlyContinue
    $totalFreed += $bakSize
    Write-Host "  ✓ 已清理" -ForegroundColor Green
} else {
    Write-Host "  无需清理" -ForegroundColor Green
}
Write-Host ""

# 2. 清理旧的构建输出目录（保留最新的和当前镜像）
Write-Host "[2] 清理旧的构建输出..." -ForegroundColor Yellow
$keepDirs = @("rgsp-single-card-v3b-20260912", "H700_Android_SingleCard_v3b.img")
$oldBuilds = Get-ChildItem -Path "out" -Directory -ErrorAction SilentlyContinue | 
              Where-Object { $_.Name -notlike "*20260912*" -and $_.Name -notin $keepDirs }

if ($oldBuilds.Count -gt 0) {
    Write-Host "  计划清理 $($oldBuilds.Count) 个旧目录:" -ForegroundColor Gray
    foreach ($dir in $oldBuilds) {
        $size = (Get-ChildItem -Path $dir.FullName -Recurse -File -ErrorAction SilentlyContinue | 
                 Measure-Object -Property Length -Sum).Sum
        if ($size -gt 100MB) {
            Write-Host "    $($dir.Name) ($([math]::Round($size/1GB,2)) GB)" -ForegroundColor Gray
        }
    }
    
    Write-Host ""
    $confirm = Read-Host "  确认清理这些目录? (y/N)"
    if ($confirm -eq 'y' -or $confirm -eq 'Y') {
        foreach ($dir in $oldBuilds) {
            $size = (Get-ChildItem -Path $dir.FullName -Recurse -File -ErrorAction SilentlyContinue | 
                     Measure-Object -Property Length -Sum).Sum
            Write-Host "  正在清理: $($dir.Name)..." -ForegroundColor Gray
            Remove-Item -Path $dir.FullName -Recurse -Force -ErrorAction SilentlyContinue
            $totalFreed += $size
        }
        Write-Host "  ✓ 已清理" -ForegroundColor Green
    } else {
        Write-Host "  ⊗ 已跳过" -ForegroundColor Yellow
    }
} else {
    Write-Host "  无需清理" -ForegroundColor Green
}
Write-Host ""

# 3. 清理大型日志文件（保留最近的）
Write-Host "[3] 清理旧日志文件..." -ForegroundColor Yellow
$allLogs = Get-ChildItem -Path "out\logs" -Recurse -Include "*.log" -ErrorAction SilentlyContinue | 
           Where-Object { $_.Length -gt 5MB }
if ($allLogs.Count -gt 0) {
    $logSize = ($allLogs | Measure-Object -Property Length -Sum).Sum
    Write-Host "  找到 $($allLogs.Count) 个大型日志文件 ($([math]::Round($logSize/1MB,2)) MB)" -ForegroundColor Gray
    Write-Host "  保留最近5个，清理其余" -ForegroundColor Gray
    
    $toDelete = $allLogs | Sort-Object LastWriteTime | Select-Object -SkipLast 5
    if ($toDelete.Count -gt 0) {
        $deleteSize = ($toDelete | Measure-Object -Property Length -Sum).Sum
        Write-Host ""
        $confirm = Read-Host "  确认清理 $($toDelete.Count) 个旧日志? (y/N)"
        if ($confirm -eq 'y' -or $confirm -eq 'Y') {
            $toDelete | Remove-Item -Force -ErrorAction SilentlyContinue
            $totalFreed += $deleteSize
            Write-Host "  ✓ 已清理" -ForegroundColor Green
        } else {
            Write-Host "  ⊗ 已跳过" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  ✓ 所有日志都是最近的，无需清理" -ForegroundColor Green
    }
} else {
    Write-Host "  无大型日志文件" -ForegroundColor Green
}
Write-Host ""

# 4. 清理重复的APK文件
Write-Host "[4] 清理重复的APK文件..." -ForegroundColor Yellow
$apkFiles = Get-ChildItem -Path "out" -Recurse -Filter "*.apk" -ErrorAction SilentlyContinue
$apkGroups = $apkFiles | Group-Object -Property Name | Where-Object { $_.Count -gt 1 }

if ($apkGroups.Count -gt 0) {
    Write-Host "  找到 $($apkGroups.Count) 组重复APK:" -ForegroundColor Gray
    foreach ($group in $apkGroups) {
        Write-Host "    $($group.Name) - $($group.Count) 个副本" -ForegroundColor Gray
    }
    
    Write-Host ""
    $confirm = Read-Host "  每组保留最新版本，清理其余? (y/N)"
    if ($confirm -eq 'y' -or $confirm -eq 'Y') {
        foreach ($group in $apkGroups) {
            $toDelete = $group.Group | Sort-Object LastWriteTime | Select-Object -SkipLast 1
            foreach ($file in $toDelete) {
                Write-Host "  删除: $($file.FullName)" -ForegroundColor Gray
                $totalFreed += $file.Length
                Remove-Item -Path $file.FullName -Force -ErrorAction SilentlyContinue
            }
        }
        Write-Host "  ✓ 已清理" -ForegroundColor Green
    } else {
        Write-Host "  ⊗ 已跳过" -ForegroundColor Yellow
    }
} else {
    Write-Host "  无重复APK" -ForegroundColor Green
}
Write-Host ""

# 5. 清理临时文件
Write-Host "[5] 清理临时文件..." -ForegroundColor Yellow
$tempFiles = Get-ChildItem -Path . -Include "*.tmp","*~",".tmp" -Recurse -ErrorAction SilentlyContinue
if ($tempFiles.Count -gt 0) {
    $tempSize = ($tempFiles | Measure-Object -Property Length -Sum).Sum
    Write-Host "  找到 $($tempFiles.Count) 个文件 ($([math]::Round($tempSize/1MB,2)) MB)" -ForegroundColor Gray
    $tempFiles | Remove-Item -Force -ErrorAction SilentlyContinue
    $totalFreed += $tempSize
    Write-Host "  ✓ 已清理" -ForegroundColor Green
} else {
    Write-Host "  无需清理" -ForegroundColor Green
}
Write-Host ""

# 总结
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "清理完成" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "总共释放空间: $([math]::Round($totalFreed/1GB,2)) GB" -ForegroundColor Green
Write-Host ""

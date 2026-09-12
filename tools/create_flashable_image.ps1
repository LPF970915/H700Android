# H700 Android Single Card - Create Flashable Image
# 生成可用Rufus/Win32DiskImager等工具直接烧录的完整镜像

param(
    [string]$ManifestPath = "D:\Works\H700Android\out\rgsp-single-card-v3b-20260912\manifest.json",
    [string]$OutputImage = "D:\Works\H700Android\out\H700_Android_SingleCard_v3b.img"
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "H700 Android 单卡系统镜像生成工具" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 读取manifest
Write-Host "[1/5] 读取manifest配置..." -ForegroundColor Yellow
if (-not (Test-Path $ManifestPath)) {
    throw "Manifest文件不存在: $ManifestPath"
}

$manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json
$totalBytes = [int64]$manifest.target_bytes
$totalGB = [math]::Round($totalBytes / 1GB, 2)

Write-Host "  目标镜像大小: $totalGB GB ($totalBytes bytes)" -ForegroundColor Gray
Write-Host "  组件数量: $($manifest.ranges.Count)" -ForegroundColor Gray
Write-Host ""

# 验证所有源文件
Write-Host "[2/5] 验证源文件完整性..." -ForegroundColor Yellow
foreach ($range in $manifest.ranges) {
    $path = $range.path
    if (-not (Test-Path $path)) {
        throw "源文件不存在: $path"
    }
    
    $file = Get-Item $path
    $sizeMB = [math]::Round($file.Length / 1MB, 2)
    Write-Host "  ✓ $(Split-Path $path -Leaf) - $sizeMB MB" -ForegroundColor Green
}
Write-Host ""

# 检查输出空间
Write-Host "[3/5] 检查磁盘空间..." -ForegroundColor Yellow
$outputDir = Split-Path $OutputImage -Parent
if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

$drive = (Get-Item $outputDir).PSDrive
$freeSpace = (Get-PSDrive $drive.Name).Free
$freeGB = [math]::Round($freeSpace / 1GB, 2)
$requiredGB = [math]::Round($totalBytes / 1GB, 2)

Write-Host "  可用空间: $freeGB GB" -ForegroundColor Gray
Write-Host "  需要空间: $requiredGB GB" -ForegroundColor Gray

if ($freeSpace -lt $totalBytes) {
    throw "磁盘空间不足！需要 $requiredGB GB，但只有 $freeGB GB 可用"
}
Write-Host "  ✓ 磁盘空间充足" -ForegroundColor Green
Write-Host ""

# 创建镜像文件
Write-Host "[4/5] 创建完整镜像文件..." -ForegroundColor Yellow
Write-Host "  输出路径: $OutputImage" -ForegroundColor Gray

$outFile = $null
$inFile = $null

try {
    # 创建空文件
    $outFile = [System.IO.File]::Open($OutputImage, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    $outFile.SetLength($totalBytes)
    
    Write-Host "  ✓ 已创建 $totalGB GB 空镜像" -ForegroundColor Green
    Write-Host ""
    
    # 写入各个组件
    Write-Host "[5/5] 写入系统组件..." -ForegroundColor Yellow
    $bufferSize = 64MB
    $buffer = New-Object byte[] $bufferSize
    
    foreach ($range in $manifest.ranges) {
        $name = Split-Path $range.path -Leaf
        $rangeBytes = [int64]$range.bytes
        $rangeOffset = [int64]$range.offset
        $sizeMB = [math]::Round($rangeBytes / 1MB, 2)
        $offsetMB = [math]::Round($rangeOffset / 1MB, 2)
        
        Write-Host "  写入 $name ($sizeMB MB @ $offsetMB MB)..." -ForegroundColor Cyan
        
        $inFile = [System.IO.File]::OpenRead($range.path)
        $outFile.Seek($rangeOffset, [System.IO.SeekOrigin]::Begin) | Out-Null
        
        $bytesRemaining = $rangeBytes
        $bytesWritten = [int64]0
        $lastProgressUpdate = [int64]0
        
        while ($bytesRemaining -gt 0) {
            $toRead = [Math]::Min([int64]$bufferSize, $bytesRemaining)
            $bytesRead = $inFile.Read($buffer, 0, [int]$toRead)
            
            if ($bytesRead -eq 0) { break }
            
            $outFile.Write($buffer, 0, $bytesRead)
            $bytesWritten += $bytesRead
            $bytesRemaining -= $bytesRead
            
            # 每100MB或完成时显示进度
            if (($bytesWritten - $lastProgressUpdate) -ge 100MB -or $bytesRemaining -eq 0) {
                $percent = [math]::Round(($bytesWritten / $rangeBytes) * 100, 1)
                $writtenMB = [math]::Round($bytesWritten / 1MB, 1)
                Write-Host "    进度: $percent% ($writtenMB MB)" -ForegroundColor Gray
                $lastProgressUpdate = $bytesWritten
            }
        }
        
        $inFile.Close()
        $inFile = $null
        Write-Host "    ✓ 完成" -ForegroundColor Green
    }
    
    $outFile.Flush()
    $outFile.Close()
    $outFile = $null
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "镜像创建成功！" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "输出文件: $OutputImage" -ForegroundColor Cyan
    Write-Host "文件大小: $totalGB GB" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "现在可以使用以下工具烧录:" -ForegroundColor Yellow
    Write-Host "  - Rufus (推荐)" -ForegroundColor White
    Write-Host "  - Win32DiskImager" -ForegroundColor White
    Write-Host "  - balenaEtcher" -ForegroundColor White
    
} catch {
    Write-Host ""
    Write-Host "错误: $($_.Exception.Message)" -ForegroundColor Red
    throw
} finally {
    if ($inFile) { $inFile.Close() }
    if ($outFile) { $outFile.Close() }
}

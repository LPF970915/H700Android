$ErrorActionPreference = "Stop"

$imgPath = "D:\Works\H700Android\out\H700_Android_SingleCard_v3b.img"
$diskNumber = 3

Write-Host "开始烧录镜像到 Disk $diskNumber..." -ForegroundColor Green

# 打开镜像文件
$imgFile = [System.IO.File]::Open($imgPath, 'Open', 'Read', 'Read')
$imgSize = $imgFile.Length
Write-Host "镜像大小: $([math]::Round($imgSize/1GB,2)) GB"

# 打开磁盘设备
$diskPath = "\\.\PhysicalDrive$diskNumber"
$disk = [System.IO.File]::Open($diskPath, 'Open', 'Write', 'None')

# 写入数据
$bufferSize = 4MB
$buffer = New-Object byte[] $bufferSize
$written = 0
$lastPercent = -1

while ($true) {
    $read = $imgFile.Read($buffer, 0, $bufferSize)
    if ($read -eq 0) { break }
    
    $disk.Write($buffer, 0, $read)
    $written += $read
    
    $percent = [math]::Floor(($written / $imgSize) * 100)
    if ($percent -ne $lastPercent -and $percent % 5 -eq 0) {
        Write-Host "进度: $percent% ($([math]::Round($written/1GB,2)) GB / $([math]::Round($imgSize/1GB,2)) GB)"
        $lastPercent = $percent
    }
}

$disk.Flush()
$disk.Close()
$imgFile.Close()

Write-Host "✅ 烧录完成！" -ForegroundColor Green

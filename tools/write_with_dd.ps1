$ErrorActionPreference = "Stop"
$VerbosePreference = "Continue"

$srcDir = "D:\Works\H700Android\out\rgsp-single-card-v3b-20260912"
$ddExe = "C:\Program Files\Git\usr\bin\dd.exe"
$targetDisk = "\\.\PhysicalDrive3"

# 写入段定义
$segments = @(
    @{Name="prefix-212m.bin"; Offset=0; Size=222298112}
    @{Name="system.raw.img"; Offset=222298112; Size=8589934592}
    @{Name="vendor.raw.img"; Offset=8812232704; Size=2147483648}
    @{Name="data.raw.img"; Offset=10959716352; Size=17179869184}
    @{Name="roms-metadata.bin"; Offset=28139585536; Size=9437184}
    @{Name="gpt-tail.bin"; Offset=62239275520; Size=1536}
)

Write-Host "开始使用dd写入到 $targetDisk"

foreach ($seg in $segments) {
    $srcFile = Join-Path $srcDir $seg.Name
    $seekBlocks = [Math]::Floor($seg.Offset / 1MB)
    
    Write-Host "`n正在写入: $($seg.Name)"
    Write-Host "  源文件: $srcFile"
    Write-Host "  偏移: $($seg.Offset) bytes (seek=$seekBlocks blocks)"
    Write-Host "  大小: $($seg.Size) bytes"
    
    & $ddExe if=$srcFile of=$targetDisk bs=1M seek=$seekBlocks conv=notrunc status=progress
    
    if ($LASTEXITCODE -ne 0) {
        throw "dd写入失败: $($seg.Name), exit code: $LASTEXITCODE"
    }
    
    Write-Host "  完成: $($seg.Name)"
}

Write-Host "`n所有段写入完成!"

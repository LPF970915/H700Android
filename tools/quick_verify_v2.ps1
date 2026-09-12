$ErrorActionPreference = "Stop"
$logFile = "D:\Works\H700Android\out\rgsp-single-card-v3b-20260912\verify_result.txt"

try {
    $targetDisk = "\\.\PhysicalDrive3"
    
    # 以只读方式打开
    $disk = [IO.File]::Open($targetDisk, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
    
    $results = @()
    
    # 读取GPT头 (sector 1)
    $disk.Seek(512, [IO.SeekOrigin]::Begin) | Out-Null
    $gptHeader = New-Object byte[] 92
    $disk.Read($gptHeader, 0, 92) | Out-Null
    
    $signature = [Text.Encoding]::ASCII.GetString($gptHeader[0..7])
    $results += "GPT Signature: $signature"
    
    if ($signature -eq "EFI PART") {
        $results += "✓ GPT头验证成功"
    } else {
        $results += "✗ GPT头验证失败"
    }
    
    # 读取boot.img magic (offset 0)
    $disk.Seek(0, [IO.SeekOrigin]::Begin) | Out-Null
    $bootMagic = New-Object byte[] 8
    $disk.Read($bootMagic, 0, 8) | Out-Null
    
    $bootStr = [Text.Encoding]::ASCII.GetString($bootMagic)
    $results += "Boot magic: $bootStr"
    
    if ($bootStr -eq "ANDROID!") {
        $results += "✓ boot.img头验证成功"
    } else {
        $results += "✗ boot.img头验证失败"
    }
    
    # 读取ramdisk的gzip magic
    $disk.Seek(66584576, [IO.SeekOrigin]::Begin) | Out-Null
    $ramdiskMagic = New-Object byte[] 2
    $disk.Read($ramdiskMagic, 0, 2) | Out-Null
    
    $results += "Ramdisk magic: 0x{0:X2}{1:X2}" -f $ramdiskMagic[0],$ramdiskMagic[1]
    
    if ($ramdiskMagic[0] -eq 0x1f -and $ramdiskMagic[1] -eq 0x8b) {
        $results += "✓ ramdisk gzip magic验证成功"
    } else {
        $results += "✗ ramdisk gzip magic验证失败"
    }
    
    # 读取system.img的ext4 magic
    $disk.Seek(222298112 + 1024 + 56, [IO.SeekOrigin]::Begin) | Out-Null
    $ext4Magic = New-Object byte[] 2
    $disk.Read($ext4Magic, 0, 2) | Out-Null
    
    $results += "System ext4 magic: 0x{0:X2}{1:X2}" -f $ext4Magic[0],$ext4Magic[1]
    
    if ($ext4Magic[0] -eq 0x53 -and $ext4Magic[1] -eq 0xef) {
        $results += "✓ system.img ext4 magic验证成功"
    } else {
        $results += "✗ system.img ext4 magic验证失败"
    }
    
    $disk.Close()
    
    $results += ""
    $results += "基本验证完成 - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    
    $results | Out-File -FilePath $logFile -Encoding utf8
    
    Write-Host "验证完成，结果已写入: $logFile"
    
} catch {
    "ERROR: $_" | Out-File -FilePath $logFile -Encoding utf8
    throw
}

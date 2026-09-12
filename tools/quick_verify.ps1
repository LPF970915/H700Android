$ErrorActionPreference = "Stop"

$targetDisk = "\\.\PhysicalDrive3"

# 以只读方式打开
$disk = [IO.File]::Open($targetDisk, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)

# 读取GPT头 (sector 1)
$disk.Seek(512, [IO.SeekOrigin]::Begin) | Out-Null
$gptHeader = New-Object byte[] 92
$disk.Read($gptHeader, 0, 92) | Out-Null

$signature = [Text.Encoding]::ASCII.GetString($gptHeader[0..7])
Write-Host "GPT Signature: $signature"

if ($signature -eq "EFI PART") {
    Write-Host "✓ GPT头验证成功"
} else {
    Write-Host "✗ GPT头验证失败"
}

# 读取boot.img magic (offset 0, sector 0)
$disk.Seek(0, [IO.SeekOrigin]::Begin) | Out-Null
$bootMagic = New-Object byte[] 8
$disk.Read($bootMagic, 0, 8) | Out-Null

$bootStr = [Text.Encoding]::ASCII.GetString($bootMagic)
Write-Host "Boot magic: $bootStr"

if ($bootStr -eq "ANDROID!") {
    Write-Host "✓ boot.img头验证成功"
} else {
    Write-Host "✗ boot.img头验证失败"
}

# 读取ramdisk位置的magic
$disk.Seek(66584576, [IO.SeekOrigin]::Begin) | Out-Null
$ramdiskMagic = New-Object byte[] 2
$disk.Read($ramdiskMagic, 0, 2) | Out-Null

if ($ramdiskMagic[0] -eq 0x1f -and $ramdiskMagic[1] -eq 0x8b) {
    Write-Host "✓ ramdisk gzip magic验证成功"
} else {
    Write-Host "✗ ramdisk gzip magic验证失败"
}

$disk.Close()
Write-Host "`n基本验证完成"

@echo off
echo ====== ??????????? ======
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; try { $disk=[IO.File]::Open('\\.\PhysicalDrive3',[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite); Write-Host '? ??????'; $disk.Seek(512,[IO.SeekOrigin]::Begin)|Out-Null; $gpt=New-Object byte[] 8; $disk.Read($gpt,0,8)|Out-Null; $sig=[Text.Encoding]::ASCII.GetString($gpt); Write-Host \"GPT Signature: $sig\"; if($sig -eq 'EFI PART'){Write-Host '? GPT???'}else{Write-Host '? GPT???'}; $disk.Seek(0,[IO.SeekOrigin]::Begin)|Out-Null; $boot=New-Object byte[] 8; $disk.Read($boot,0,8)|Out-Null; $bootStr=[Text.Encoding]::ASCII.GetString($boot); Write-Host \"Boot magic: $bootStr\"; if($bootStr -eq 'ANDROID!'){Write-Host '? boot.img??'}else{Write-Host '? boot.img??'}; $disk.Seek(66584576,[IO.SeekOrigin]::Begin)|Out-Null; $rd=New-Object byte[] 2; $disk.Read($rd,0,2)|Out-Null; if($rd[0] -eq 0x1f -and $rd[1] -eq 0x8b){Write-Host '? ramdisk gzip magic??'}else{Write-Host '? ramdisk??'}; $disk.Seek(222298112+1024+56,[IO.SeekOrigin]::Begin)|Out-Null; $ext4=New-Object byte[] 2; $disk.Read($ext4,0,2)|Out-Null; if($ext4[0] -eq 0x53 -and $ext4[1] -eq 0xef){Write-Host '? system.img ext4??'}else{Write-Host '? system.img??'}; $disk.Close(); Write-Host ''; Write-Host '====== ???? ======'; } catch { Write-Host \"??: $_\" }"

echo.
echo ??????...
pause >nul

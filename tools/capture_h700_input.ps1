[CmdletBinding()]
param(
    [string]$Adb = "adb",
    [string]$OutDir = "D:\Works\H700Android\out\input-capture",
    [int]$Seconds = 30
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

& $Adb get-state | Out-File (Join-Path $OutDir "adb-state.txt") -Encoding ascii
if ($LASTEXITCODE -ne 0) {
    throw "adb 未连接。先执行 adb devices，并确认 Android alpha 已启动。"
}

& $Adb shell getevent -lp | Out-File (Join-Path $OutDir "getevent-capabilities.txt") -Encoding utf8
& $Adb shell dumpsys input | Out-File (Join-Path $OutDir "dumpsys-input.txt") -Encoding utf8
$eventFile = Join-Path $OutDir "getevent-$Seconds-sec.txt"
$errFile = Join-Path $OutDir "getevent-$Seconds-sec.err.txt"
$proc = Start-Process -FilePath $Adb -ArgumentList @("shell", "getevent", "-t") -NoNewWindow `
    -RedirectStandardOutput $eventFile -RedirectStandardError $errFile -PassThru
Start-Sleep -Seconds $Seconds
if (-not $proc.HasExited) {
    $proc.Kill()
    $proc.WaitForExit()
}

@"
采集完成：$OutDir
请把实体键逐个按一遍后，再运行本脚本一次；不要修改 event 编号。
下一步根据设备 name、能力位和实际事件生成专用 .kl/.kcm。
"@ | Write-Host

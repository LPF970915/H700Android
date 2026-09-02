param([string]$Port='COM4',[int]$TimeoutSeconds=900)
$ErrorActionPreference='Stop'
$serial=[IO.Ports.SerialPort]::new($Port,115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$serial.Handshake='None';$serial.ReadTimeout=200;$serial.WriteTimeout=1000;$serial.DtrEnable=$false;$serial.RtsEnable=$false;$serial.Encoding=[Text.Encoding]::UTF8
$sb=[Text.StringBuilder]::new()
function Read-Chunk { $x=$serial.ReadExisting(); if($x.Length -gt 0){[void]$sb.Append($x);[Console]::Write($x)} }
function Send-Line([string]$line){$serial.Write($line+"`r")}
function Wait-Shell([int]$seconds=60){$deadline=(Get-Date).AddSeconds($seconds);$login=$false;$pass=$false;while((Get-Date)-lt $deadline){Read-Chunk;$t=$sb.ToString();if($t -match '(?im)login\s*:'){Send-Line 'root';$login=$true;Start-Sleep -Milliseconds 500}elseif($login -and -not $pass -and $t -match '(?im)password\s*[:>]?$'){Send-Line 'root';$pass=$true;Start-Sleep -Milliseconds 800}elseif($t -match '(?m)[#\$]\s*$'){return};Start-Sleep -Milliseconds 50};throw 'Linux shell prompt not reached'}
function Upload-Base64([string]$remote,[byte[]]$bytes){$b64=[Convert]::ToBase64String($bytes);Send-Line "stty -icanon min 1 time 0 -echo; base64 -d > $remote";Start-Sleep -Milliseconds 300;$chunk=8192;for($i=0;$i -lt $b64.Length;$i+=$chunk){$n=[Math]::Min($chunk,$b64.Length-$i);$serial.Write($b64.Substring($i,$n));Read-Chunk;Start-Sleep -Milliseconds 2};$serial.Write("`r");Start-Sleep -Milliseconds 100;$serial.BaseStream.Write([byte[]](4),0,1);Start-Sleep -Milliseconds 700;Read-Chunk;Send-Line 'stty sane';Start-Sleep -Milliseconds 700;Read-Chunk}
function Run-Command([string]$cmd,[int]$seconds=180){$token=[Guid]::NewGuid().ToString('N');$end="__CODEX_SERIAL_END_${token}__";$wire="printf '\n$end\n'; /bin/sh -c '"+$cmd.Replace("'","'`"'`"'")+"'; rc=`$?; printf '\n${end}:%s\n' `"`$rc`"";Send-Line $wire;$deadline=(Get-Date).AddSeconds($seconds);while((Get-Date)-lt $deadline){Read-Chunk;if($sb.ToString() -match ([regex]::Escape($end)+':\d+')){break};Start-Sleep -Milliseconds 50};$m=[regex]::Match($sb.ToString(),([regex]::Escape($end)+':(\d+)'));if(-not $m.Success){throw "command timeout: $cmd"};if([int]$m.Groups[1].Value -ne 0){throw "command failed: $cmd"}}
try{
  $serial.Open();Send-Line '';Start-Sleep -Milliseconds 700;Read-Chunk;Wait-Shell
  Upload-Base64 '/tmp/rgsp-services-fix45.jar' ([IO.File]::ReadAllBytes('work/fix44-tools/services-fix45.jar'))
  Upload-Base64 '/tmp/apply_rgsp_android_fix45_metrics_headless.sh' ([IO.File]::ReadAllBytes('device/apply_rgsp_android_fix45_metrics_headless.sh'))
  Run-Command "chmod 0755 /tmp/apply_rgsp_android_fix45_metrics_headless.sh; sha256sum /tmp/rgsp-services-fix45.jar; /bin/sh /tmp/apply_rgsp_android_fix45_metrics_headless.sh" 300
  Write-Host 'FIX45_SYSTEM_APPLY_OK'
} finally {if($serial.IsOpen){$serial.Close()};$serial.Dispose();[IO.File]::WriteAllText("out/logs/uart/rgsp/rgsp_serial_exec_fix45_$(Get-Date -Format yyyyMMdd_HHmmss)_115200.log",$sb.ToString(),[Text.Encoding]::UTF8)}

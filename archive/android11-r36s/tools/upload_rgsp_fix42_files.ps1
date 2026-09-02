param([string]$Port='COM4')
$ErrorActionPreference='Stop'
$serial=[IO.Ports.SerialPort]::new($Port,115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One);$serial.Handshake='None';$serial.ReadTimeout=200;$serial.WriteTimeout=1000;$serial.Encoding=[Text.Encoding]::UTF8
function Drain { $null=$serial.ReadExisting() }
function Send([string]$s){$serial.Write($s+"`r");Start-Sleep -Milliseconds 500;Drain}
function Upload([string]$remote,[byte[]]$bytes){
  $b64=[Convert]::ToBase64String($bytes)
  Send "stty -icanon min 1 time 0 -echo; base64 -d > $remote"
  $chunk=8192
  for($i=0;$i -lt $b64.Length;$i+=$chunk){$n=[Math]::Min($chunk,$b64.Length-$i);$serial.Write($b64.Substring($i,$n));Drain}
  $serial.BaseStream.Write([byte[]](4),0,1);Start-Sleep -Milliseconds 500;Drain
  Send 'stty sane'
}
try{$serial.Open();Start-Sleep -Milliseconds 500;Drain
 Upload '/tmp/apply_rgsp_android_fix42_watchdog.sh' ([IO.File]::ReadAllBytes('device/apply_rgsp_android_fix42_watchdog.sh'))
 Upload '/tmp/prepare_rgsp_android_fix42_test.sh' ([IO.File]::ReadAllBytes('device/prepare_rgsp_android_fix42_test.sh'))
 Upload '/mnt/sdcard/rgsp-services-watchdog-bypass.jar.gz' ([IO.File]::ReadAllBytes('work/fix42-tools/services-watchdog-bypass.jar.gz'))
 Write-Host 'UPLOAD_FIX42_OK'
} finally {if($serial.IsOpen){$serial.Close()};$serial.Dispose()}

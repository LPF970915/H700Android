$ErrorActionPreference='Stop'
$serial=[IO.Ports.SerialPort]::new('COM4',115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$serial.Handshake='None';$serial.ReadTimeout=200;$serial.WriteTimeout=1000;$serial.Encoding=[Text.Encoding]::ASCII
$log=[IO.Path]::GetFullPath("out/logs/uart/rgsp/rgsp_serial_exec_fix45_apply_$(Get-Date -Format yyyyMMdd_HHmmss)_115200.log")
$sb=[Text.StringBuilder]::new()
function Drain([int]$ms=500){$d=(Get-Date).AddMilliseconds($ms);while((Get-Date)-lt$d){$x=$serial.ReadExisting();if($x){[void]$sb.Append($x);[Console]::Write($x)};Start-Sleep -Milliseconds 50}}
function Send([string]$s){$serial.Write($s+"`r")}
function Run([string]$cmd,[int]$sec=300){
  $tok=[Guid]::NewGuid().ToString('N');$end="__END_${tok}__"
  Send "$cmd; rc=`$?; echo ${end}:`$rc"
  $d=(Get-Date).AddSeconds($sec)
  while((Get-Date)-lt$d){Drain 100;if($sb.ToString()-match([regex]::Escape($end)+':(\d+)')){break}}
  $m=[regex]::Match($sb.ToString(),([regex]::Escape($end)+':(\d+)'))
  if(-not$m.Success-or[int]$m.Groups[1].Value-ne0){throw "remote failed: $cmd"}
}
function PutText([string]$remote,[string]$local){
  $b64=[Convert]::ToBase64String([IO.File]::ReadAllBytes($local));$tmp="$remote.b64"
  Run "rm -f $tmp $remote" 30
  $chunk=2048
  for($i=0;$i-lt$b64.Length;$i+=$chunk){$n=[Math]::Min($chunk,$b64.Length-$i);Run "printf %s $($b64.Substring($i,$n)) >> $tmp" 30}
  Run "base64 -d $tmp > $remote && rm -f $tmp" 30
}
try{
  $serial.Open();$serial.BaseStream.Write([byte[]](3),0,1);Send '';Drain 1200
  if($sb.ToString()-match '(?im)login\s*:'){Send 'root';Drain 600;Send 'root';Drain 1400}
  PutText '/tmp/apply_rgsp_android_fix45_metrics_headless.sh' 'device/apply_rgsp_android_fix45_metrics_headless.sh'
  PutText '/tmp/prepare_rgsp_android_fix45_test.sh' 'device/prepare_rgsp_android_fix45_test.sh'
  Run "chmod 0755 /tmp/apply_rgsp_android_fix45_metrics_headless.sh /tmp/prepare_rgsp_android_fix45_test.sh" 30
  Run "sha256sum /tmp/rgsp-services-fix45.jar" 30
  Run "/bin/sh /tmp/apply_rgsp_android_fix45_metrics_headless.sh" 360
  Run "/bin/sh /tmp/prepare_rgsp_android_fix45_test.sh" 360
  Write-Host 'FIX45_APPLY_PREPARE_OK'
} finally {
  if($serial.IsOpen){$serial.Close()};$serial.Dispose()
  [IO.File]::WriteAllText($log,$sb.ToString(),[Text.Encoding]::UTF8)
  Write-Host "Log: $log"
}

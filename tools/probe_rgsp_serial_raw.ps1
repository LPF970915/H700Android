param([string]$Port='COM4')
$s=[IO.Ports.SerialPort]::new($Port,115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$s.Handshake='None';$s.ReadTimeout=200;$s.WriteTimeout=1000;$s.DtrEnable=$false;$s.RtsEnable=$false;$s.Encoding=[Text.Encoding]::UTF8
try{$s.Open();$s.BaseStream.Write([byte[]](13,10),0,2);Start-Sleep -Milliseconds 500;$end=(Get-Date).AddSeconds(5);while((Get-Date)-lt$end){$x=$s.ReadExisting();if($x){[Console]::Write($x)};Start-Sleep -Milliseconds 50}}finally{if($s.IsOpen){$s.Close()};$s.Dispose()}
